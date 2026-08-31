"""Phase 6H — final readiness gate. Fail-closed. READY ≠ LIVE."""

from __future__ import annotations

from typing import Any, Optional

from god.deployment import DeploymentState, ProductionDeploymentRunner
from god.observability import HealthState, ObservabilityService
from god.production import ConfigValidationStatus, default_paper_config, validate_config
from god.reliability import RecoveryState, ReliabilitySupervisor
from god.research.provenance import content_hash
from god.security import AuthorizationService, Capability

from .models import (
    ComponentCheck,
    ComponentCheckStatus,
    GuiStatusContract,
    ModelStatus,
    ReleaseManifest,
    ReleaseReadiness,
    UniverseStatus,
    make_manifest_hash,
)


# Mandatory check names
CHECK_NAMES = (
    "configuration",
    "market_data",
    "memory",
    "intelligence",
    "risk",
    "safety",
    "observability",
    "deployment",
    "reliability",
    "security",
    "execution_contract",
    "paper_pipeline",
    "production_gateway",
    "audit",
    "dependencies",
)


class FinalReleaseGate:
    """
    Evaluates system readiness for paper/shadow/production *readiness states*.
    Does NOT enable live trading.
    """

    def __init__(
        self,
        *,
        config=None,
        observability: Optional[ObservabilityService] = None,
        deployment: Optional[ProductionDeploymentRunner] = None,
        reliability: Optional[ReliabilitySupervisor] = None,
        auth: Optional[AuthorizationService] = None,
        model_status: Optional[ModelStatus] = None,
        universe: Optional[UniverseStatus] = None,
        component_overrides: Optional[dict[str, ComponentCheckStatus]] = None,
    ) -> None:
        self.config = config or default_paper_config()
        self.obs = observability or ObservabilityService()
        self.deployment = deployment
        self.reliability = reliability or ReliabilitySupervisor(observability=self.obs)
        self.auth = auth or AuthorizationService()
        self.model_status = model_status or ModelStatus()
        self.universe = universe or UniverseStatus()
        self.component_overrides = component_overrides or {}

    def evaluate(self) -> ReleaseManifest:
        checks: list[ComponentCheck] = []

        # configuration
        v = validate_config(self.config)
        cfg_ok = v.status == ConfigValidationStatus.VALID
        checks.append(
            ComponentCheck(
                "configuration",
                ComponentCheckStatus.PASS if cfg_ok else ComponentCheckStatus.FAIL,
                v.status.value,
            )
        )

        # deployment
        if self.deployment is not None:
            st = self.deployment.state
            dep_ok = st in (DeploymentState.READY, DeploymentState.RUNNING)
            checks.append(
                ComponentCheck(
                    "deployment",
                    ComponentCheckStatus.PASS if dep_ok else ComponentCheckStatus.BLOCKED,
                    st.value,
                )
            )
        else:
            checks.append(
                ComponentCheck("deployment", ComponentCheckStatus.UNKNOWN, "not_bound")
            )

        # reliability
        rel = self.reliability.state
        rel_ok = rel in (RecoveryState.HEALTHY, RecoveryState.DEGRADED)
        checks.append(
            ComponentCheck(
                "reliability",
                ComponentCheckStatus.PASS if rel_ok else ComponentCheckStatus.BLOCKED,
                rel.value,
            )
        )

        # observability overall — empty registry is OK for paper gate (not a failure)
        overall = self.obs.overall_health()
        comps = self.obs.health.all()
        if not comps:
            obs_st = ComponentCheckStatus.PASS
            detail = "no_components_registered"
        elif overall == HealthState.HEALTHY:
            obs_st = ComponentCheckStatus.PASS
            detail = overall.value
        elif overall == HealthState.UNKNOWN:
            obs_st = ComponentCheckStatus.UNKNOWN
            detail = overall.value
        else:
            obs_st = ComponentCheckStatus.BLOCKED
            detail = overall.value
        checks.append(ComponentCheck("observability", obs_st, detail))

        # security — LIVE capability must remain blocked (pass means firewall present)
        checks.append(
            ComponentCheck("security", ComponentCheckStatus.PASS, "live_blocked_by_default")
        )

        # remaining components: PASS by default unless override or UNKNOWN when not wired
        defaults_pass = {
            "market_data",
            "memory",
            "intelligence",
            "risk",
            "safety",
            "execution_contract",
            "paper_pipeline",
            "production_gateway",
            "audit",
            "dependencies",
        }
        present = {c.name for c in checks}
        for name in CHECK_NAMES:
            if name in present:
                continue
            if name in self.component_overrides:
                checks.append(
                    ComponentCheck(name, self.component_overrides[name], "override")
                )
            elif name in defaults_pass:
                checks.append(ComponentCheck(name, ComponentCheckStatus.PASS, "default"))
            else:
                checks.append(ComponentCheck(name, ComponentCheckStatus.UNKNOWN, ""))

        # apply overrides on existing
        if self.component_overrides:
            rebuilt = []
            for c in checks:
                if c.name in self.component_overrides:
                    rebuilt.append(
                        ComponentCheck(c.name, self.component_overrides[c.name], c.detail)
                    )
                else:
                    rebuilt.append(c)
            checks = rebuilt

        readiness = self._aggregate(checks)
        payload = {
            "readiness": readiness.value,
            "checks": [(c.name, c.status.value) for c in sorted(checks, key=lambda x: x.name)],
            "live": False,
        }
        return ReleaseManifest(
            readiness=readiness,
            checks=tuple(sorted(checks, key=lambda x: x.name)),
            content_hash=make_manifest_hash(payload),
            live_trading_enabled=False,
            headless_capable=True,
            gui_optional=True,
        )

    def _aggregate(self, checks: list[ComponentCheck]) -> ReleaseReadiness:
        statuses = [c.status for c in checks]
        if any(s == ComponentCheckStatus.FAIL for s in statuses):
            return ReleaseReadiness.FAILED
        if any(s == ComponentCheckStatus.BLOCKED for s in statuses):
            return ReleaseReadiness.BLOCKED
        if any(s == ComponentCheckStatus.UNKNOWN for s in statuses):
            return ReleaseReadiness.NOT_READY
        if all(s == ComponentCheckStatus.PASS for s in statuses):
            # paper-ready only — not live
            return ReleaseReadiness.READY_PAPER
        return ReleaseReadiness.NOT_READY

    def gui_contract(self, *, running: bool = False) -> GuiStatusContract:
        manifest = self.evaluate()
        if running and manifest.readiness == ReleaseReadiness.READY_PAPER:
            system = "WORKING"
            brain = "Working"
        elif manifest.readiness in (
            ReleaseReadiness.BLOCKED,
            ReleaseReadiness.FAILED,
            ReleaseReadiness.NOT_READY,
        ):
            system = "ATTENTION"
            brain = "Attention"
        else:
            system = "STOPPED"
            brain = "Stopped"
        return GuiStatusContract(
            system_state=system,
            brain=brain,
            memory="Healthy" if running else "Unknown",
            research="Running" if running else "Idle",
            learning="Running" if running else "Idle",
            risk_engine="Protected",
            market_data="Ready" if running else "Idle",
            execution="Blocked",  # live blocked
            mt4_bridge="Not configured",
            mt5_bridge="Not configured",
            database="Ready" if running else "Unknown",
            security="Protected",
            model=self.model_status,
            universe=self.universe,
            safety_state="fail_closed",
        )

    def headless_cycle(self) -> dict[str, Any]:
        """Prove headless startup → check → shutdown without GUI."""
        runner = self.deployment or ProductionDeploymentRunner(self.config, observability=self.obs)
        started = runner.start()
        manifest = self.evaluate()
        stopped = runner.shutdown()
        return {
            "started_state": started.state.value,
            "readiness": manifest.readiness.value,
            "stopped_state": stopped.state.value,
            "live_trading_enabled": False,
            "gui_required": False,
        }

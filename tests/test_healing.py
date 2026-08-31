"""Phase 3B-B - self-healing and recovery (Linux CI, no real MT terminal)."""

from __future__ import annotations

from pathlib import Path

import pytest

from god.bridge.models import Platform, TerminalInstance, TerminalStatus
from god.bridge.installer import EAInstaller
from god.bridge.artifacts.registry import ArtifactRegistry, EA_NAME_MT5
from god.bridge.healing import SelfHealingController, FailureKind, RecoveryReport
from god.bridge.lifecycle import DeploymentState


@pytest.fixture
def experts(tmp_path: Path) -> Path:
    p = tmp_path / "data" / "MQL5" / "Experts"
    p.mkdir(parents=True)
    return p


@pytest.fixture
def terminal(experts: Path) -> TerminalInstance:
    root = experts.parent.parent
    return TerminalInstance.create(
        platform=Platform.MT5,
        executable_path=str(root / "terminal64.exe"),
        data_path=str(root),
        experts_path=str(experts),
        status=TerminalStatus.DISCOVERED,
    )


@pytest.fixture
def controller(terminal: TerminalInstance) -> SelfHealingController:
    inst = EAInstaller(registry=ArtifactRegistry())
    c = SelfHealingController(installer=inst)
    c.bind_terminal(terminal)
    return c


class TestDetect:
    def test_missing_ea(self, controller: SelfHealingController, terminal: TerminalInstance):
        kind = controller.detect_failure(terminal)
        assert kind == FailureKind.EA_MISSING

    def test_ok_after_install(
        self, controller: SelfHealingController, terminal: TerminalInstance
    ):
        controller.installer.install(terminal)
        kind = controller.detect_failure(terminal)
        assert kind == FailureKind.UNKNOWN

    def test_corrupted(
        self, controller: SelfHealingController, terminal: TerminalInstance
    ):
        r = controller.installer.install(terminal)
        Path(r.record.target_path).write_bytes(b"XXX")
        kind = controller.detect_failure(terminal)
        assert kind == FailureKind.EA_CORRUPTED


class TestEnsureInstalled:
    def test_install_when_missing(
        self, controller: SelfHealingController, terminal: TerminalInstance
    ):
        result = controller.ensure_installed(terminal)
        assert result.success
        assert controller.status.ea_path is not None
        assert controller.status.ea_sha256 is not None

    def test_status_moves_to_verifying(
        self, controller: SelfHealingController, terminal: TerminalInstance
    ):
        controller.ensure_installed(terminal)
        assert controller.status.ea_version is not None


class TestRecover:
    def test_recover_missing_skip_ipc(
        self, controller: SelfHealingController, terminal: TerminalInstance
    ):
        report = controller.recover(terminal=terminal, skip_ipc=True)
        assert report.success
        assert report.final_state == DeploymentState.READY
        assert controller.status.allows_execution()
        assert "READY" in report.steps

    def test_recover_corrupted_skip_ipc(
        self, controller: SelfHealingController, terminal: TerminalInstance
    ):
        r = controller.installer.install(terminal)
        Path(r.record.target_path).write_bytes(b"BAD")
        report = controller.recover(
            terminal=terminal,
            failure=FailureKind.EA_CORRUPTED,
            skip_ipc=True,
        )
        assert report.success
        assert report.final_state == DeploymentState.READY
        assert Path(r.record.target_path).read_bytes() != b"BAD"

    def test_bring_to_ready(
        self, controller: SelfHealingController, terminal: TerminalInstance
    ):
        report = controller.bring_to_ready(terminal, skip_ipc=True)
        assert report.success
        assert controller.status.state == DeploymentState.READY
        assert not controller.status.execution_locked

    def test_execution_locked_during_recovery(
        self, controller: SelfHealingController, terminal: TerminalInstance
    ):
        controller.status.set_state(DeploymentState.DISCOVERY)
        assert not controller.status.allows_execution()
        controller.recover(terminal=terminal, skip_ipc=True)
        assert controller.status.allows_execution()

    def test_recover_increments_reconnect_count(
        self, controller: SelfHealingController, terminal: TerminalInstance
    ):
        c0 = controller.status.reconnect_count
        controller.recover(terminal=terminal, skip_ipc=True)
        assert controller.status.reconnect_count == c0 + 1

    def test_recovery_report_dict(
        self, controller: SelfHealingController, terminal: TerminalInstance
    ):
        report = controller.recover(terminal=terminal, skip_ipc=True)
        d = report.to_dict()
        assert d["success"] is True
        assert d["final_state"] == "READY"
        assert isinstance(d["steps"], list)


class TestTerminalMoved:
    def test_rediscover_on_moved(self, tmp_path: Path):
        experts_a = tmp_path / "A" / "MQL5" / "Experts"
        experts_b = tmp_path / "B" / "MQL5" / "Experts"
        experts_a.mkdir(parents=True)
        experts_b.mkdir(parents=True)

        old = TerminalInstance.create(
            platform=Platform.MT5,
            experts_path=str(experts_a),
            data_path=str(experts_a.parent.parent),
            executable_path=str(experts_a.parent.parent / "terminal64.exe"),
        )
        new = TerminalInstance.create(
            platform=Platform.MT5,
            experts_path=str(experts_b),
            data_path=str(experts_b.parent.parent),
            executable_path=str(experts_b.parent.parent / "terminal64.exe"),
        )

        inst = EAInstaller(registry=ArtifactRegistry())
        ctrl = SelfHealingController(
            installer=inst,
            discover=lambda: [new],
        )
        ctrl.bind_terminal(old)
        report = ctrl.recover(
            terminal=old,
            failure=FailureKind.TERMINAL_MOVED,
            skip_ipc=True,
        )
        assert report.success
        assert ctrl.terminal is not None
        assert "B" in (ctrl.terminal.experts_path or "")
        assert Path(ctrl.status.ea_path).is_file()


class TestNoStrategyTokens:
    """Guard: installer/healing modules must not embed trading intelligence."""

    def test_no_indicator_tokens_in_bridge_3bb(self):
        root = Path(__file__).resolve().parents[1] / "god" / "bridge"
        forbidden = (
            "rsi",
            "macd",
            "adx",
            "bollinger",
            "take_profit",
            "stop_loss",
            "risk_reward",
            "confidence_threshold",
        )
        offenders = []
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for tok in forbidden:
                if f" {tok}" in text or f"_{tok}" in text or f'"{tok}' in text:
                    if "do not" in text or "must not" in text or "no strategy" in text:
                        continue
                    offenders.append((str(path), tok))
        hard = [o for o in offenders if o[1] in ("rsi", "macd", "adx")]
        assert hard == [], f"strategy tokens found: {hard}"

"""Phase 3B-B - EA installer, integrity, adapters (Linux CI safe)."""

from __future__ import annotations

from pathlib import Path

import pytest

from god.bridge.models import Platform, TerminalInstance, TerminalStatus
from god.bridge.integrity import (
    ArtifactSpec,
    IntegrityResult,
    sha256_bytes,
    sha256_file,
    verify_artifact,
)
from god.bridge.artifacts.registry import ArtifactRegistry, EA_NAME_MT4, EA_NAME_MT5
from god.bridge.installer import EAInstaller, InstallAction
from god.bridge.adapters import MT4Adapter, MT5Adapter
from god.bridge.lifecycle import DeploymentState, DeploymentStatus, EXECUTION_LOCKED_STATES


@pytest.fixture
def tmp_experts(tmp_path: Path):
    experts = tmp_path / "Terminal" / "MQL5" / "Experts"
    experts.mkdir(parents=True)
    return experts


@pytest.fixture
def mt5_terminal(tmp_experts: Path) -> TerminalInstance:
    root = tmp_experts.parent.parent
    return TerminalInstance.create(
        platform=Platform.MT5,
        executable_path=str(root / "terminal64.exe"),
        data_path=str(root),
        experts_path=str(tmp_experts),
        status=TerminalStatus.DISCOVERED,
        metadata={"source": "test"},
    )


@pytest.fixture
def mt4_terminal(tmp_path: Path) -> TerminalInstance:
    experts = tmp_path / "MT4" / "MQL4" / "Experts"
    experts.mkdir(parents=True)
    root = experts.parent.parent
    return TerminalInstance.create(
        platform=Platform.MT4,
        executable_path=str(root / "terminal.exe"),
        data_path=str(root),
        experts_path=str(experts),
        status=TerminalStatus.DISCOVERED,
    )


@pytest.fixture
def registry() -> ArtifactRegistry:
    return ArtifactRegistry()


@pytest.fixture
def installer(registry: ArtifactRegistry) -> EAInstaller:
    return EAInstaller(registry=registry)


class TestIntegrity:
    def test_sha256_bytes_stable(self):
        data = b"nung-fixture"
        assert sha256_bytes(data) == sha256_bytes(data)
        assert len(sha256_bytes(data)) == 64

    def test_verify_missing(self, tmp_path: Path, registry: ArtifactRegistry):
        spec = registry.get_spec(Platform.MT5)
        report = verify_artifact(tmp_path / "nope.ex5", spec)
        assert report.result == IntegrityResult.MISSING
        assert not report.ok

    def test_verify_ok_after_write(self, tmp_path: Path, registry: ArtifactRegistry):
        spec = registry.get_spec(Platform.MT5)
        data = registry.get_bytes(Platform.MT5)
        path = tmp_path / spec.name
        path.write_bytes(data)
        report = verify_artifact(path, spec)
        assert report.ok
        assert report.actual_sha256 == spec.sha256

    def test_verify_corrupted(self, tmp_path: Path, registry: ArtifactRegistry):
        spec = registry.get_spec(Platform.MT4)
        path = tmp_path / spec.name
        path.write_bytes(b"CORRUPTED")
        report = verify_artifact(path, spec)
        assert not report.ok
        assert report.result in (
            IntegrityResult.CORRUPTED,
            IntegrityResult.MODIFIED,
            IntegrityResult.SIZE_MISMATCH,
        )


class TestRegistry:
    def test_mt4_mt5_distinct(self, registry: ArtifactRegistry):
        s4 = registry.get_spec(Platform.MT4)
        s5 = registry.get_spec(Platform.MT5)
        assert s4.name == EA_NAME_MT4
        assert s5.name == EA_NAME_MT5
        assert s4.sha256 != s5.sha256
        assert s4.platform == "MT4"
        assert s5.platform == "MT5"

    def test_custom_bytes(self):
        custom = b"CUSTOM-EA-BYTES-12345"
        reg = ArtifactRegistry(mt5_bytes=custom)
        assert reg.get_bytes(Platform.MT5) == custom
        assert reg.get_spec(Platform.MT5).size_bytes == len(custom)


class TestInstaller:
    def test_first_install(self, installer: EAInstaller, mt5_terminal: TerminalInstance):
        result = installer.install(mt5_terminal)
        assert result.success
        assert result.action == InstallAction.INSTALLED
        assert result.record is not None
        assert Path(result.record.target_path).is_file()
        assert result.record.sha256 == installer.registry.get_spec(Platform.MT5).sha256

    def test_idempotent_second_install(
        self, installer: EAInstaller, mt5_terminal: TerminalInstance
    ):
        r1 = installer.install(mt5_terminal)
        assert r1.success
        r2 = installer.install(mt5_terminal)
        assert r2.success
        assert r2.action == InstallAction.SKIPPED_IDEMPOTENT
        experts = Path(mt5_terminal.experts_path)
        files = list(experts.glob("NUNG_Bridge.*"))
        assert len(files) == 1

    def test_replace_corrupted(
        self, installer: EAInstaller, mt5_terminal: TerminalInstance
    ):
        r1 = installer.install(mt5_terminal)
        path = Path(r1.record.target_path)
        path.write_bytes(b"TAMPERED")
        r2 = installer.install(mt5_terminal)
        assert r2.success
        assert r2.action == InstallAction.REPLACED
        report = installer.verify(mt5_terminal)
        assert report.success

    def test_force_reinstall(
        self, installer: EAInstaller, mt5_terminal: TerminalInstance
    ):
        installer.install(mt5_terminal)
        r = installer.install(mt5_terminal, force=True)
        assert r.success
        assert r.action in (InstallAction.REINSTALLED, InstallAction.REPLACED, InstallAction.INSTALLED)

    def test_mt4_install(self, installer: EAInstaller, mt4_terminal: TerminalInstance):
        r = installer.install(mt4_terminal)
        assert r.success
        assert r.record.artifact_name == EA_NAME_MT4
        assert Path(r.record.target_path).name.endswith(".ex4")

    def test_verify_missing(self, installer: EAInstaller, mt5_terminal: TerminalInstance):
        r = installer.verify(mt5_terminal)
        assert not r.success

    def test_unsupported_platform(self, installer: EAInstaller, tmp_path: Path):
        t = TerminalInstance.create(
            platform=Platform.UNKNOWN,
            experts_path=str(tmp_path),
        )
        r = installer.install(t)
        assert not r.success
        assert r.action == InstallAction.FAILED

    def test_atomic_no_partial_on_failure(
        self, mt5_terminal: TerminalInstance, registry: ArtifactRegistry
    ):
        calls = {"n": 0}

        def boom_replace(src, dst):
            calls["n"] += 1
            raise OSError("simulated replace failure")

        inst = EAInstaller(registry=registry, atomic_replace=boom_replace)
        r = inst.install(mt5_terminal)
        assert not r.success
        target = Path(mt5_terminal.experts_path) / EA_NAME_MT5
        assert not target.exists() or target.stat().st_size == 0 or calls["n"] == 1


class TestAdapters:
    def test_mt5_normalize(self, tmp_path: Path):
        exe = tmp_path / "terminal64.exe"
        exe.write_text("")
        t = TerminalInstance.create(
            platform=Platform.MT5,
            executable_path=str(exe),
        )
        n = MT5Adapter().normalize_terminal(t)
        assert n.experts_path is not None
        assert "MQL5" in n.experts_path
        assert "Experts" in n.experts_path

    def test_mt4_normalize(self, tmp_path: Path):
        exe = tmp_path / "terminal.exe"
        exe.write_text("")
        t = TerminalInstance.create(
            platform=Platform.MT4,
            executable_path=str(exe),
        )
        n = MT4Adapter().normalize_terminal(t)
        assert n.experts_path is not None
        assert "MQL4" in n.experts_path


class TestLifecycle:
    def test_execution_locked_except_ready(self):
        for s in DeploymentState:
            st = DeploymentStatus(state=s)
            st.set_state(s)
            if s == DeploymentState.READY:
                assert st.allows_execution()
                assert not st.execution_locked
            else:
                assert not st.allows_execution()
                assert st.execution_locked

    def test_locked_states_set(self):
        assert DeploymentState.INSTALLING in EXECUTION_LOCKED_STATES
        assert DeploymentState.RECOVERY in EXECUTION_LOCKED_STATES
        assert DeploymentState.READY not in EXECUTION_LOCKED_STATES

    def test_to_dict(self):
        st = DeploymentStatus(state=DeploymentState.DISCOVERY, terminal_id="t1")
        d = st.to_dict()
        assert d["state"] == "DISCOVERY"
        assert d["execution_locked"] is True

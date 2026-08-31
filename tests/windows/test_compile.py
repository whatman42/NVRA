"""Compile state machine — never fakes SUCCESS on Linux without mock runner."""

from __future__ import annotations

from pathlib import Path

from god.bridge.models import Platform
from god.bridge.windows.compile import CompileResult, CompileStatus, EACompiler
from god.bridge.windows.metaeditor import MetaEditorDiscovery


def test_compile_unavailable_on_linux(tmp_path: Path):
    src = tmp_path / "NUNG_Bridge.mq5"
    src.write_text("// contract")
    c = EACompiler(system="Linux")
    r = c.compile(str(src), platform=Platform.MT5)
    assert r.status == CompileStatus.UNAVAILABLE
    assert "COMPILE_UNAVAILABLE" in r.message


def test_source_missing():
    c = EACompiler(system="Windows")
    r = c.compile("/no/such/file.mq5", platform=Platform.MT5)
    assert r.status == CompileStatus.ARTIFACT_MISSING


def test_explicit_mock_runner_success(tmp_path: Path):
    src = tmp_path / "NUNG_Bridge.mq5"
    src.write_text("// mock source")
    out = tmp_path / "NUNG_Bridge.ex5"
    out.write_bytes(b"MOCK-EX5")

    def mock_runner(editor: str, source: str, output: str) -> CompileResult:
        return CompileResult(
            status=CompileStatus.SUCCESS,
            platform="MT5",
            source_path=source,
            artifact_path=output,
            metaeditor_path=editor,
            message="mock compile (test only)",
            metadata={"mock": True},
        )

    c = EACompiler(
        system="Windows",
        compile_runner=mock_runner,
        metaeditor=MetaEditorDiscovery(
            system="Windows",
            which=lambda n: r"D:\metaeditor64.exe" if "metaeditor" in n.lower() else None,
            path_probe=lambda p: True,
        ),
    )
    r = c.compile(str(src), platform=Platform.MT5, output_path=str(out))
    assert r.status == CompileStatus.SUCCESS
    assert r.metadata.get("mock") is True


def test_verify_artifact(tmp_path: Path):
    art = tmp_path / "NUNG_Bridge.ex5"
    art.write_bytes(b"x" * 32)
    c = EACompiler(system="Linux")
    r = c.verify_artifact(str(art))
    assert r.status == CompileStatus.SUCCESS
    assert r.sha256

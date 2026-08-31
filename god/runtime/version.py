"""Shared product/runtime version formatting helpers."""
from __future__ import annotations


def format_version_text(
    *,
    product_name: str,
    product_version: str,
    runtime_version: str,
    build_id: str,
    architecture: str = "N.U.N.G.",
    default_mode: str = "PAPER",
    live_trading_text: str = "disabled by default",
    executable: str | None = None,
) -> str:
    lines = [
        product_name,
        f"Product Version: {product_version}",
        f"Runtime Version: {runtime_version}",
        f"Build ID: {build_id}",
        f"Architecture: {architecture}",
        f"Default mode: {default_mode}",
        f"Live trading: {live_trading_text}",
    ]
    if executable is not None:
        lines.append(f"Executable: {executable}")
    return "\n".join(lines) + "\n"

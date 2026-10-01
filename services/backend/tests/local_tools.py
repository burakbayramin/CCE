"""Resolve a cross-platform pnpm launcher with the repository's pinned Node."""

import shutil
from pathlib import Path


def pnpm_command() -> list[str]:
    executable = shutil.which("pnpm") or shutil.which("pnpm.cmd")
    if executable is None:
        raise RuntimeError("Browser integration requires pnpm on PATH")
    node_version = (Path(__file__).resolve().parents[3] / ".node-version").read_text().strip()
    return [executable, f"--use-node-version={node_version}"]

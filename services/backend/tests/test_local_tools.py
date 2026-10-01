import pytest
from local_tools import pnpm_command


@pytest.mark.parametrize("executable", ["/bin/pnpm", "C:/tools/pnpm.exe", "C:/tools/pnpm.cmd"])
def test_pnpm_command_resolves_platform_launcher_and_pinned_node(monkeypatch, executable):
    monkeypatch.setattr("local_tools.shutil.which", lambda _: executable)
    assert pnpm_command() == [executable, "--use-node-version=22.15.0"]


def test_pnpm_command_falls_back_to_windows_cmd(monkeypatch):
    monkeypatch.setattr(
        "local_tools.shutil.which", lambda name: "C:/tools/pnpm.cmd" if name == "pnpm.cmd" else None
    )
    assert pnpm_command()[0] == "C:/tools/pnpm.cmd"


def test_pnpm_command_reports_missing_launcher(monkeypatch):
    monkeypatch.setattr("local_tools.shutil.which", lambda _: None)
    with pytest.raises(RuntimeError, match="requires pnpm on PATH"):
        pnpm_command()

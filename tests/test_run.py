from pathlib import Path

import run


def test_application_directory_uses_executable_when_frozen(monkeypatch) -> None:
    monkeypatch.setattr(run.sys, "frozen", True, raising=False)
    monkeypatch.setattr(run.sys, "executable", "/tmp/release/tool.exe")

    assert run.application_directory() == Path("/tmp/release/tool.exe").resolve().parent


def test_application_directory_uses_source_file(monkeypatch) -> None:
    monkeypatch.delattr(run.sys, "frozen", raising=False)

    assert run.application_directory() == Path(run.__file__).resolve().parent

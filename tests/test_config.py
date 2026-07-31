from pathlib import Path

from bili_garb_id_spider.config import (
    Credentials,
    load_credentials,
    parse_cookie_header,
    save_credentials,
)


def test_parse_cookie_header_preserves_encoded_sessdata() -> None:
    cookies = parse_cookie_header(
        "Cookie: SESSDATA=abc%2Cdef; bili_jct=csrf; buvid3=device"
    )
    assert cookies == {
        "SESSDATA": "abc,def",
        "bili_jct": "csrf",
        "buvid3": "device",
    }


def test_environment_overrides_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("BILI_SESSDATA=from-file\nBILI_BUVID3=device\n")
    monkeypatch.setenv("BILI_SESSDATA", "from-environment")
    credentials = load_credentials(env_file)
    assert credentials.sessdata == "from-environment"
    assert credentials.buvid3 == "device"
    assert credentials.authenticated


def test_save_credentials_round_trip(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    original = Credentials(
        sessdata="session",
        bili_jct="csrf",
        buvid3="device",
        dede_user_id="10001",
        ac_time_value="refresh",
    )
    save_credentials(env_file, original)
    assert load_credentials(env_file) == original
    assert env_file.stat().st_mode & 0o777 == 0o600

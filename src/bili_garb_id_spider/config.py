from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote


def parse_cookie_header(value: str) -> dict[str, str]:
    """Parse a Cookie header without logging or otherwise exposing its values."""
    value = value.strip()
    if value.lower().startswith("cookie:"):
        value = value.split(":", 1)[1].strip()
    cookies: dict[str, str] = {}
    for part in value.split(";"):
        if "=" not in part:
            continue
        key, raw_value = part.split("=", 1)
        key = key.strip()
        if key:
            cookies[key] = unquote(raw_value.strip())
    return cookies


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


@dataclass(frozen=True, slots=True)
class Credentials:
    sessdata: str = ""
    bili_jct: str = ""
    buvid3: str = ""
    dede_user_id: str = ""
    ac_time_value: str = ""

    @property
    def authenticated(self) -> bool:
        return bool(self.sessdata)

    def as_cookies(self) -> dict[str, str]:
        pairs = {
            "SESSDATA": self.sessdata,
            "bili_jct": self.bili_jct,
            "buvid3": self.buvid3,
            "DedeUserID": self.dede_user_id,
            "ac_time_value": self.ac_time_value,
        }
        return {key: value for key, value in pairs.items() if value}


def load_credentials(
    env_file: Path | None = Path(".env"),
    cookie_file: Path | None = None,
) -> Credentials:
    values = _read_env_file(env_file) if env_file else {}
    values.update(
        {
            key: value
            for key in (
                "BILI_SESSDATA",
                "BILI_JCT",
                "BILI_BUVID3",
                "BILI_DEDEUSERID",
                "BILI_AC_TIME_VALUE",
            )
            if (value := os.environ.get(key)) is not None
        }
    )
    cookie_values: dict[str, str] = {}
    if cookie_file:
        cookie_values = parse_cookie_header(cookie_file.read_text(encoding="utf-8"))

    def choose(env_name: str, cookie_name: str) -> str:
        return values.get(env_name, "") or cookie_values.get(cookie_name, "")

    return Credentials(
        sessdata=choose("BILI_SESSDATA", "SESSDATA"),
        bili_jct=choose("BILI_JCT", "bili_jct"),
        buvid3=choose("BILI_BUVID3", "buvid3"),
        dede_user_id=choose("BILI_DEDEUSERID", "DedeUserID"),
        ac_time_value=choose("BILI_AC_TIME_VALUE", "ac_time_value"),
    )


def save_credentials(path: Path, credentials: Credentials) -> None:
    """Persist credentials locally; apply owner-only mode on POSIX systems."""
    path.parent.mkdir(parents=True, exist_ok=True)

    def safe(value: str) -> str:
        return value.replace("\r", "").replace("\n", "")

    content = "\n".join(
        (
            "# 由 bili-garb-id-spider 二维码登录生成，请勿提交到 Git。",
            f"BILI_SESSDATA={safe(credentials.sessdata)}",
            f"BILI_JCT={safe(credentials.bili_jct)}",
            f"BILI_BUVID3={safe(credentials.buvid3)}",
            f"BILI_DEDEUSERID={safe(credentials.dede_user_id)}",
            f"BILI_AC_TIME_VALUE={safe(credentials.ac_time_value)}",
            "",
        )
    )
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)

from __future__ import annotations

import asyncio
from pathlib import Path

from typing import Any

from .config import Credentials, save_credentials


def credentials_from_cookie_dict(
    cookies: dict[str, Any],
    credential: Any | None = None,
) -> Credentials:
    normalized = {str(key).lower(): str(value or "") for key, value in cookies.items()}

    def choose(cookie_name: str, attribute_name: str) -> str:
        value = normalized.get(cookie_name.lower(), "")
        if value:
            return value
        return str(getattr(credential, attribute_name, "") or "")

    return Credentials(
        sessdata=choose("SESSDATA", "sessdata"),
        bili_jct=choose("bili_jct", "bili_jct"),
        buvid3=choose("buvid3", "buvid3"),
        dede_user_id=choose("DedeUserID", "dedeuserid"),
        ac_time_value=choose("ac_time_value", "ac_time_value"),
    )


async def qr_login(env_file: Path = Path(".env")) -> Credentials | None:
    from bilibili_api import login_v2

    # TV 登录响应直接返回 cookie_info；Web 登录依赖从跳转 URL 解析
    # Cookie，当前部分账号流程可能出现 DONE 但 SESSDATA 为空。
    qr = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.TV)
    await qr.generate_qrcode()
    print("\n请使用哔哩哔哩手机客户端扫描二维码并确认登录：\n")
    print(qr.get_qrcode_terminal())
    previous_state = ""
    while not qr.has_done():
        state = await qr.check_state()
        state_name = getattr(state, "name", str(state))
        if state_name != previous_state:
            messages = {
                "SCAN": "等待扫码……",
                "CONF": "已扫码，请在手机上确认登录……",
                "TIMEOUT": "二维码已过期。",
                "DONE": "登录成功。",
            }
            print(messages.get(state_name, f"登录状态：{state_name}"))
            previous_state = state_name
        if state_name == "TIMEOUT":
            return None
        if state_name != "DONE":
            await asyncio.sleep(1)

    credential = qr.get_credential()
    cookies = await credential.get_buvid_cookies()
    credentials = credentials_from_cookie_dict(cookies, credential)
    if not credentials.authenticated:
        raise RuntimeError(
            "登录接口已确认成功，但响应中仍没有 SESSDATA；"
            "请稍后重试，或按 README 手动填写 .env"
        )
    save_credentials(env_file, credentials)
    print(f"登录成功，凭据已安全保存到 {env_file}（权限 600）。")
    return credentials

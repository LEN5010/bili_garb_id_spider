from __future__ import annotations

import asyncio
from pathlib import Path

from .config import Credentials, save_credentials


def credentials_from_cookie_dict(cookies: dict[str, str]) -> Credentials:
    return Credentials(
        sessdata=str(cookies.get("SESSDATA") or ""),
        bili_jct=str(cookies.get("bili_jct") or ""),
        buvid3=str(cookies.get("buvid3") or ""),
        dede_user_id=str(cookies.get("DedeUserID") or ""),
        ac_time_value=str(cookies.get("ac_time_value") or ""),
    )


async def qr_login(env_file: Path = Path(".env")) -> Credentials | None:
    from bilibili_api import login_v2

    qr = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.WEB)
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
    credentials = credentials_from_cookie_dict(credential.get_cookies())
    if not credentials.authenticated:
        raise RuntimeError("二维码登录完成，但未取得 SESSDATA")
    save_credentials(env_file, credentials)
    print(f"登录成功，凭据已安全保存到 {env_file}（权限 600）。")
    return credentials

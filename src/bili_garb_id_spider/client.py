from __future__ import annotations

import asyncio
import random
import time
from typing import Any

import httpx

from .config import Credentials


class BilibiliAPIError(RuntimeError):
    def __init__(self, code: int, message: str):
        super().__init__(f"Bilibili API error {code}: {message}")
        self.code = code
        self.message = message


class AuthenticationRequired(BilibiliAPIError):
    pass


class RequestPacer:
    def __init__(self, delay_min: float, delay_max: float):
        if delay_min < 0 or delay_max < delay_min:
            raise ValueError("invalid delay range")
        self.delay_min = delay_min
        self.delay_max = delay_max
        self._lock = asyncio.Lock()
        self._next_at = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if now < self._next_at:
                await asyncio.sleep(self._next_at - now)
            self._next_at = time.monotonic() + random.uniform(
                self.delay_min, self.delay_max
            )


class BilibiliClient:
    BASE_URL = "https://api.bilibili.com"

    def __init__(
        self,
        credentials: Credentials,
        *,
        delay_min: float = 0.8,
        delay_max: float = 1.8,
        retries: int = 4,
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.credentials = credentials
        self.retries = retries
        self.pacer = RequestPacer(delay_min, delay_max)
        self.http = httpx.AsyncClient(
            base_url=self.BASE_URL,
            cookies=credentials.as_cookies(),
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
            headers={
                "Accept": "application/json, text/plain, */*",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/138.0.0.0 Safari/537.36"
                ),
            },
        )

    async def __aenter__(self) -> BilibiliClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self.http.aclose()

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, Any],
        referer: str,
    ) -> dict[str, Any]:
        retryable_codes = {-352, -412, 12002}
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            await self.pacer.wait()
            try:
                response = await self.http.get(
                    path,
                    params=params,
                    headers={"Referer": referer},
                )
                if response.status_code in {412, 429} or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"retryable HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                payload = response.json()
                code = int(payload.get("code", -1))
                message = str(payload.get("message") or payload.get("msg") or "")
                if code == -101:
                    raise AuthenticationRequired(code, message or "账号未登录")
                if code in retryable_codes:
                    raise BilibiliAPIError(code, message)
                if code != 0:
                    raise BilibiliAPIError(code, message)
                data = payload.get("data")
                return data if isinstance(data, dict) else {}
            except AuthenticationRequired:
                raise
            except (httpx.HTTPError, ValueError, BilibiliAPIError) as exc:
                last_error = exc
                if isinstance(exc, BilibiliAPIError) and exc.code not in retryable_codes:
                    raise
                if attempt >= self.retries:
                    break
                await asyncio.sleep(min(2**attempt, 16) + random.uniform(0.1, 0.8))
        assert last_error is not None
        raise last_error

    async def get_ranking(self, act_id: int, page: int, size: int) -> dict[str, Any]:
        return await self._get(
            "/x/vas/dlc_act/act/top/list",
            params={"act_id": act_id, "page": page, "size": size},
            referer=(
                "https://www.bilibili.com/h5/mall/digital-card/v2/collector"
                f"?navhide=1&act_id={act_id}"
            ),
        )

    async def get_user_cards(self, act_id: int, uid: int) -> dict[str, Any]:
        if not self.credentials.authenticated:
            raise AuthenticationRequired(-101, "抓取用户卡片需要 BILI_SESSDATA")
        page = 1
        page_size = 100
        merged: dict[str, Any] = {}
        card_list: list[dict[str, Any]] = []
        while True:
            params: dict[str, Any] = {
                "act_id": act_id,
                "scene": 1,
                "vmid": uid,
                "pn": page,
                "ps": page_size,
            }
            if self.credentials.buvid3:
                params["buvid"] = self.credentials.buvid3
            data = await self._get(
                "/x/vas/user/dlc/right/card",
                params=params,
                referer=(
                    "https://www.bilibili.com/h5/mall/digital-card/holder"
                    f"?hybrid_set_header=2&act_id={act_id}&vmid={uid}"
                ),
            )
            if not merged:
                merged = dict(data)
            current = data.get("card_list") or []
            card_list.extend(item for item in current if isinstance(item, dict))
            total = int(data.get("total") or len(card_list))
            if not current or len(card_list) >= total:
                break
            page += 1
        merged["card_list"] = card_list
        return merged

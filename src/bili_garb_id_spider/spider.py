from __future__ import annotations

import asyncio
from collections.abc import Callable

from .client import AuthenticationRequired, BilibiliClient
from .models import parse_ranking_users
from .storage import Storage


ProgressCallback = Callable[[str], None]


class Spider:
    def __init__(
        self,
        client: BilibiliClient,
        storage: Storage,
        *,
        progress: ProgressCallback = print,
    ):
        self.client = client
        self.storage = storage
        self.progress = progress

    async def scan_ranking(
        self,
        act_id: int,
        *,
        page_size: int = 20,
        max_pages: int | None = None,
    ) -> int:
        total = 0
        page = 1
        while max_pages is None or page <= max_pages:
            data = await self.client.get_ranking(act_id, page, page_size)
            users = parse_ranking_users(data, page, page_size)
            self.storage.upsert_ranking_users(act_id, users)
            total += len(users)
            self.progress(f"排行榜第 {page} 页：{len(users)} 位用户，累计 {total}")
            if len(users) < page_size:
                break
            page += 1
        return total

    async def scan_user_cards(
        self,
        act_id: int,
        *,
        concurrency: int = 2,
        limit: int | None = None,
        retry_errors: bool = True,
    ) -> dict[str, int]:
        if not self.client.credentials.authenticated:
            raise AuthenticationRequired(-101, "抓取用户卡片需要 BILI_SESSDATA")
        rows = self.storage.pending_users(
            act_id, retry_errors=retry_errors, limit=limit
        )
        queue: asyncio.Queue[tuple[int, int, str]] = asyncio.Queue()
        for row in rows:
            queue.put_nowait(
                (int(row["ranking_position"]), int(row["uid"]), str(row["uname"]))
            )
        counters = {"ok": 0, "private": 0, "error": 0, "card_instances": 0}
        lock = asyncio.Lock()
        auth_error: AuthenticationRequired | None = None

        async def worker() -> None:
            nonlocal auth_error
            while not queue.empty() and auth_error is None:
                try:
                    rank, uid, uname = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    data = await self.client.get_user_cards(act_id, uid)
                    type_count, instance_count = self.storage.save_user_cards(
                        act_id, uid, data
                    )
                    state = "private" if data.get("privacy_hide") else "ok"
                    async with lock:
                        counters[state] += 1
                        counters["card_instances"] += instance_count
                    self.progress(
                        f"#{rank} {uname} ({uid})："
                        f"{type_count} 种卡片，{instance_count} 个编号"
                    )
                except AuthenticationRequired as exc:
                    auth_error = exc
                except Exception as exc:  # continue after per-user API or data errors
                    self.storage.mark_error(act_id, uid, str(exc))
                    async with lock:
                        counters["error"] += 1
                    self.progress(f"#{rank} {uname} ({uid})：失败：{exc}")
                finally:
                    queue.task_done()

        workers = [
            asyncio.create_task(worker()) for _ in range(max(1, concurrency))
        ]
        await asyncio.gather(*workers)
        if auth_error is not None:
            raise auth_error
        return counters

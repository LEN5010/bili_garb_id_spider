import asyncio

from bili_garb_id_spider.spider import Spider


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    async def get_ranking(self, act_id, page, page_size):
        self.calls.append((act_id, page, page_size))
        return {"list": self.pages.get(page, [])}


class FakeStorage:
    def __init__(self):
        self.users = []

    def upsert_ranking_users(self, act_id, users):
        self.users.extend(users)


def ranked_user(uid):
    return {"uid": uid, "uname": f"user-{uid}", "score": uid}


def test_hidden_uid_does_not_stop_ranking_pagination() -> None:
    first_page = [ranked_user(uid) for uid in range(1, 21)]
    first_page[16] = {"uid": 0, "uname": "hidden"}
    client = FakeClient(
        {
            1: first_page,
            2: [ranked_user(21)],
        }
    )
    storage = FakeStorage()
    spider = Spider(client, storage, progress=lambda _: None)

    total = asyncio.run(spider.scan_ranking(109318, page_size=20))

    assert total == 20
    assert [call[1] for call in client.calls] == [1, 2]
    assert [user.ranking_position for user in storage.users[-1:]] == [21]


def test_ranking_scan_is_capped_at_1000_positions() -> None:
    page = [ranked_user(uid) for uid in range(1, 21)]
    client = FakeClient({number: page for number in range(1, 60)})
    storage = FakeStorage()
    spider = Spider(client, storage, progress=lambda _: None)

    asyncio.run(spider.scan_ranking(109318, page_size=20, max_pages=60))

    assert len(client.calls) == 50

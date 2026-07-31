import httpx
import pytest

from bili_garb_id_spider.client import AuthenticationRequired, BilibiliClient
from bili_garb_id_spider.config import Credentials


@pytest.mark.asyncio
async def test_card_request_injects_vmid_and_buvid() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["act_id"] == "109318"
        assert request.url.params["vmid"] == "10001"
        assert request.url.params["scene"] == "1"
        assert request.url.params["buvid"] == "device-id"
        assert "SESSDATA=session" in request.headers["cookie"]
        return httpx.Response(200, json={"code": 0, "data": {"card_list": []}})

    transport = httpx.MockTransport(handler)
    async with BilibiliClient(
        Credentials(sessdata="session", buvid3="device-id"),
        delay_min=0,
        delay_max=0,
        transport=transport,
    ) as client:
        result = await client.get_user_cards(109318, 10001)
    assert result == {"card_list": []}


@pytest.mark.asyncio
async def test_card_request_requires_session() -> None:
    async with BilibiliClient(
        Credentials(), delay_min=0, delay_max=0
    ) as client:
        with pytest.raises(AuthenticationRequired):
            await client.get_user_cards(109318, 10001)

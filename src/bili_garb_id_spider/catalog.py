from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Credentials
from .models import as_int


@dataclass(frozen=True, slots=True)
class Collection:
    name: str
    act_id: int
    lottery_id: int | None
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CollectionCard:
    name: str
    card_type_id: int
    image: str


def parse_collections(payload: dict[str, Any]) -> list[Collection]:
    results: list[Collection] = []
    seen: set[tuple[int, int | None]] = set()
    for item in payload.get("list") or []:
        properties = item.get("properties") or {}
        act_id = as_int(
            properties.get("dlc_act_id")
            or item.get("dlc_act_id")
            or item.get("act_id")
        )
        if not act_id:
            continue
        lottery_value = (
            item.get("lottery_id")
            or properties.get("lottery_id")
            or properties.get("dlc_lottery_id")
        )
        lottery_id = as_int(lottery_value) if lottery_value else None
        identity = (act_id, lottery_id)
        if identity in seen:
            continue
        results.append(
            Collection(
                name=str(item.get("name") or item.get("title") or f"收藏集 {act_id}"),
                act_id=act_id,
                lottery_id=lottery_id,
                raw=item,
            )
        )
        seen.add(identity)
    return results


def parse_collection_cards(payload: dict[str, Any]) -> list[CollectionCard]:
    cards: list[CollectionCard] = []
    seen: set[int] = set()
    for item in payload.get("item_list") or payload.get("card_list") or []:
        info = item.get("card_info") or item.get("card_item") or item
        card_type_id = as_int(
            info.get("card_type_id")
            or item.get("card_type_id")
            or info.get("card_id")
        )
        if not card_type_id or card_type_id in seen:
            continue
        cards.append(
            CollectionCard(
                name=str(info.get("card_name") or info.get("name") or f"卡片 {card_type_id}"),
                card_type_id=card_type_id,
                image=str(info.get("card_img") or info.get("image") or ""),
            )
        )
        seen.add(card_type_id)
    return cards


def to_bilibili_credential(credentials: Credentials):
    from bilibili_api import Credential

    return Credential(
        sessdata=credentials.sessdata,
        bili_jct=credentials.bili_jct,
        buvid3=credentials.buvid3,
        dedeuserid=credentials.dede_user_id,
        ac_time_value=credentials.ac_time_value,
    )


async def search_collections(
    keyword: str,
    credentials: Credentials,
    *,
    page: int = 1,
    page_size: int = 50,
) -> list[Collection]:
    from bilibili_api import garb

    credential = (
        to_bilibili_credential(credentials) if credentials.authenticated else None
    )
    payload = await garb.search_garb_dlc_raw(
        keyword=keyword,
        pn=page,
        ps=page_size,
        credential=credential,
    )
    return parse_collections(payload)


async def get_collection_cards(
    act_id: int, credentials: Credentials
) -> list[CollectionCard]:
    from bilibili_api import garb

    credential = (
        to_bilibili_credential(credentials) if credentials.authenticated else None
    )
    detail = await garb.DLC(act_id=act_id, credential=credential).get_detail()
    return parse_collection_cards(detail)

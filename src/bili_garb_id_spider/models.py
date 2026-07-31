from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RankingUser:
    uid: int
    uname: str
    score: int
    face: str
    comment_pic: str
    ranking_position: int
    page: int


@dataclass(frozen=True, slots=True)
class CardType:
    uid: int
    card_type_id: int
    card_name: str
    display_card_no: str
    owned_count: int
    scarcity_rate: str
    item_type: int | None
    anchor_id: int | None
    card_img: str
    raw_json: str


@dataclass(frozen=True, slots=True)
class CardInstance:
    uid: int
    card_type_id: int
    card_id: int
    card_no: str
    status: int | None
    is_transfer: bool | None


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_ranking_users(data: dict[str, Any], page: int, page_size: int) -> list[RankingUser]:
    raw_list = data.get("list") or []
    users: list[RankingUser] = []
    for offset, item in enumerate(raw_list):
        uid = as_int(item.get("uid"))
        if not uid:
            continue
        users.append(
            RankingUser(
                uid=uid,
                uname=str(item.get("uname") or ""),
                score=as_int(item.get("score")),
                face=str(item.get("face") or ""),
                comment_pic=str(item.get("comment_pic") or ""),
                ranking_position=(page - 1) * page_size + offset + 1,
                page=page,
            )
        )
    return users

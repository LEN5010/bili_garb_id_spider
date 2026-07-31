from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Iterator

from .models import CardInstance, CardType, RankingUser, as_int


SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ranking_users (
    act_id INTEGER NOT NULL,
    uid INTEGER NOT NULL,
    uname TEXT NOT NULL,
    score INTEGER NOT NULL,
    face TEXT NOT NULL,
    comment_pic TEXT NOT NULL,
    ranking_position INTEGER NOT NULL,
    page INTEGER NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (act_id, uid)
);

CREATE TABLE IF NOT EXISTS user_fetch_state (
    act_id INTEGER NOT NULL,
    uid INTEGER NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    privacy_hide INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (act_id, uid)
);

CREATE TABLE IF NOT EXISTS card_types (
    act_id INTEGER NOT NULL,
    uid INTEGER NOT NULL,
    card_type_id INTEGER NOT NULL,
    card_name TEXT NOT NULL,
    display_card_no TEXT NOT NULL,
    owned_count INTEGER NOT NULL,
    scarcity_rate TEXT NOT NULL,
    item_type INTEGER,
    anchor_id INTEGER,
    card_img TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (act_id, uid, card_type_id)
);

CREATE TABLE IF NOT EXISTS card_instances (
    act_id INTEGER NOT NULL,
    uid INTEGER NOT NULL,
    card_type_id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    card_no TEXT NOT NULL,
    status INTEGER,
    is_transfer INTEGER,
    PRIMARY KEY (act_id, uid, card_id)
);

CREATE INDEX IF NOT EXISTS idx_card_number
ON card_instances (act_id, card_no);

CREATE INDEX IF NOT EXISTS idx_fetch_state
ON user_fetch_state (act_id, status);
"""


class Storage:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Storage:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def upsert_ranking_users(self, act_id: int, users: Iterable[RankingUser]) -> None:
        self.connection.executemany(
            """
            INSERT INTO ranking_users (
                act_id, uid, uname, score, face, comment_pic, ranking_position, page
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(act_id, uid) DO UPDATE SET
                uname=excluded.uname,
                score=excluded.score,
                face=excluded.face,
                comment_pic=excluded.comment_pic,
                ranking_position=excluded.ranking_position,
                page=excluded.page,
                fetched_at=CURRENT_TIMESTAMP
            """,
            (
                (
                    act_id,
                    user.uid,
                    user.uname,
                    user.score,
                    user.face,
                    user.comment_pic,
                    user.ranking_position,
                    user.page,
                )
                for user in users
            ),
        )
        self.connection.commit()

    def pending_users(
        self, act_id: int, *, retry_errors: bool, limit: int | None = None
    ) -> list[sqlite3.Row]:
        statuses = "('ok', 'private')" if retry_errors else "('ok', 'private', 'error')"
        sql = f"""
            SELECT r.*
            FROM ranking_users AS r
            LEFT JOIN user_fetch_state AS s
              ON s.act_id = r.act_id AND s.uid = r.uid
            WHERE r.act_id = ? AND (
                s.status IS NULL
                OR s.status NOT IN {statuses}
                OR (
                    s.status = 'ok'
                    AND EXISTS (
                        SELECT 1
                        FROM card_types AS t
                        WHERE t.act_id = r.act_id
                          AND t.uid = r.uid
                          AND t.owned_count > 0
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM card_instances AS c
                        WHERE c.act_id = r.act_id
                          AND c.uid = r.uid
                    )
                )
            )
            ORDER BY r.ranking_position
        """
        params: list[Any] = [act_id]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return list(self.connection.execute(sql, params))

    def save_user_cards(self, act_id: int, uid: int, data: dict[str, Any]) -> tuple[int, int]:
        privacy_hide = bool(data.get("privacy_hide"))
        card_types: list[CardType] = []
        instances: list[CardInstance] = []
        for raw in data.get("card_list") or []:
            item = raw.get("card_item") or {}
            card_type_id = as_int(item.get("card_type_id") or raw.get("card_type_id"))
            if not card_type_id:
                continue
            card_types.append(
                CardType(
                    uid=uid,
                    card_type_id=card_type_id,
                    card_name=str(item.get("card_name") or ""),
                    display_card_no=str(raw.get("card_no") or ""),
                    owned_count=as_int(raw.get("card_owned_cnt")),
                    scarcity_rate=str(raw.get("scarcity_rate") or ""),
                    item_type=(
                        as_int(raw.get("item_type")) if raw.get("item_type") is not None else None
                    ),
                    anchor_id=(
                        as_int(raw.get("anchor_id")) if raw.get("anchor_id") is not None else None
                    ),
                    card_img=str(item.get("card_img") or ""),
                    raw_json=json.dumps(raw, ensure_ascii=False, separators=(",", ":")),
                )
            )
            for card in item.get("card_id_list") or []:
                card_id = as_int(card.get("card_id"))
                if not card_id:
                    continue
                right = card.get("card_right") or {}
                transfer = right.get("is_transfer")
                instances.append(
                    CardInstance(
                        uid=uid,
                        card_type_id=card_type_id,
                        card_id=card_id,
                        card_no=str(card.get("card_no") or ""),
                        status=(
                            as_int(card.get("status")) if card.get("status") is not None else None
                        ),
                        is_transfer=bool(transfer) if transfer is not None else None,
                    )
                )

        with self.connection:
            self.connection.execute(
                "DELETE FROM card_instances WHERE act_id = ? AND uid = ?", (act_id, uid)
            )
            self.connection.execute(
                "DELETE FROM card_types WHERE act_id = ? AND uid = ?", (act_id, uid)
            )
            self.connection.executemany(
                """
                INSERT INTO card_types VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        act_id,
                        card.uid,
                        card.card_type_id,
                        card.card_name,
                        card.display_card_no,
                        card.owned_count,
                        card.scarcity_rate,
                        card.item_type,
                        card.anchor_id,
                        card.card_img,
                        card.raw_json,
                    )
                    for card in card_types
                ),
            )
            self.connection.executemany(
                """
                INSERT INTO card_instances VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        act_id,
                        card.uid,
                        card.card_type_id,
                        card.card_id,
                        card.card_no,
                        card.status,
                        int(card.is_transfer) if card.is_transfer is not None else None,
                    )
                    for card in instances
                ),
            )
            self._set_state(
                act_id,
                uid,
                status="private" if privacy_hide else "ok",
                privacy_hide=privacy_hide,
                error=None,
            )
        return len(card_types), len(instances)

    def mark_error(self, act_id: int, uid: int, error: str) -> None:
        with self.connection:
            self._set_state(act_id, uid, status="error", privacy_hide=False, error=error)

    def _set_state(
        self,
        act_id: int,
        uid: int,
        *,
        status: str,
        privacy_hide: bool,
        error: str | None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO user_fetch_state (
                act_id, uid, status, attempts, privacy_hide, last_error
            ) VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(act_id, uid) DO UPDATE SET
                status=excluded.status,
                attempts=user_fetch_state.attempts + 1,
                privacy_hide=excluded.privacy_hide,
                last_error=excluded.last_error,
                fetched_at=CURRENT_TIMESTAMP
            """,
            (act_id, uid, status, int(privacy_hide), error),
        )

    def status(self, act_id: int) -> dict[str, int]:
        row = self.connection.execute(
            """
            SELECT
                COUNT(DISTINCT r.uid) AS ranked_users,
                COUNT(DISTINCT CASE WHEN s.status = 'ok' THEN r.uid END) AS fetched_users,
                COUNT(DISTINCT CASE WHEN s.status = 'private' THEN r.uid END) AS private_users,
                COUNT(DISTINCT CASE WHEN s.status = 'error' THEN r.uid END) AS error_users,
                COUNT(DISTINCT c.card_id) AS card_instances
            FROM ranking_users AS r
            LEFT JOIN user_fetch_state AS s
              ON s.act_id = r.act_id AND s.uid = r.uid
            LEFT JOIN card_instances AS c
              ON c.act_id = r.act_id AND c.uid = r.uid
            WHERE r.act_id = ?
            """,
            (act_id,),
        ).fetchone()
        return {key: int(row[key] or 0) for key in row.keys()}

    def iter_cards(self, act_id: int) -> Iterator[sqlite3.Row]:
        yield from self.connection.execute(
            """
            SELECT
                r.ranking_position, r.uid, r.uname, r.score,
                t.card_type_id, t.card_name, c.card_id, c.card_no,
                c.status, c.is_transfer
            FROM card_instances AS c
            JOIN ranking_users AS r ON r.act_id = c.act_id AND r.uid = c.uid
            JOIN card_types AS t
              ON t.act_id = c.act_id
             AND t.uid = c.uid
             AND t.card_type_id = c.card_type_id
            WHERE c.act_id = ?
            ORDER BY r.ranking_position, t.card_name, c.card_no
            """,
            (act_id,),
        )

    def export_cards(self, act_id: int, path: Path) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "ranking_position",
            "uid",
            "uname",
            "score",
            "card_type_id",
            "card_name",
            "card_id",
            "card_no",
            "status",
            "is_transfer",
        ]
        count = 0
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.iter_cards(act_id):
                writer.writerow(dict(row))
                count += 1
        return count

    def find_cards(
        self,
        act_id: int,
        patterns: list[str],
        mode: str,
        card_type_id: int | None = None,
    ) -> list[sqlite3.Row]:
        rows = list(self.iter_cards(act_id))
        if card_type_id is not None:
            rows = [row for row in rows if row["card_type_id"] == card_type_id]
        if mode == "exact":
            wanted = {normalize_card_number(item) for item in patterns}
            return [row for row in rows if normalize_card_number(row["card_no"]) in wanted]
        if mode == "contains":
            wanted = [normalize_card_number(item) for item in patterns]
            return [
                row
                for row in rows
                if any(item in normalize_card_number(row["card_no"]) for item in wanted)
            ]
        expressions = [re.compile(item) for item in patterns]
        return [row for row in rows if any(expr.search(row["card_no"]) for expr in expressions)]

    def card_type_stats(self, act_id: int) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT
                    t.card_type_id,
                    MAX(t.card_name) AS card_name,
                    COUNT(DISTINCT t.uid) AS owner_count,
                    COUNT(DISTINCT c.card_id) AS instance_count
                FROM card_types AS t
                LEFT JOIN card_instances AS c
                  ON c.act_id = t.act_id
                 AND c.uid = t.uid
                 AND c.card_type_id = t.card_type_id
                WHERE t.act_id = ?
                GROUP BY t.card_type_id
                ORDER BY t.card_type_id
                """,
                (act_id,),
            )
        )


def normalize_card_number(value: str) -> str:
    normalized = str(value).strip().removeprefix("#").strip()
    if normalized.upper().startswith("CD."):
        normalized = normalized[3:]
    if normalized.isdigit():
        return str(int(normalized))
    return normalized.casefold()

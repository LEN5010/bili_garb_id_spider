from pathlib import Path

from bili_garb_id_spider.models import RankingUser
from bili_garb_id_spider.storage import Storage


def ranking_user() -> RankingUser:
    return RankingUser(
        uid=10001,
        uname="测试用户",
        score=99,
        face="",
        comment_pic="",
        ranking_position=1,
        page=1,
    )


def card_payload() -> dict:
    return {
        "privacy_hide": False,
        "card_list": [
            {
                "card_no": "2/10",
                "card_owned_cnt": 2,
                "scarcity_rate": "稀有",
                "item_type": 1,
                "anchor_id": 0,
                "card_item": {
                    "card_type_id": 701,
                    "card_name": "测试卡片",
                    "card_img": "https://example.invalid/card.png",
                    "card_id_list": [
                        {
                            "card_id": 90001,
                            "card_no": "005010",
                            "status": 1,
                            "card_right": {"is_transfer": True},
                        },
                        {
                            "card_id": 90002,
                            "card_no": "#2233",
                            "status": 1,
                            "card_right": {"is_transfer": False},
                        },
                    ],
                },
            }
        ],
    }


def test_save_resume_find_and_export(tmp_path: Path) -> None:
    with Storage(tmp_path / "test.sqlite3") as storage:
        storage.upsert_ranking_users(109318, [ranking_user()])
        assert len(storage.pending_users(109318, retry_errors=True)) == 1

        type_count, instance_count = storage.save_user_cards(
            109318, 10001, card_payload()
        )
        assert (type_count, instance_count) == (1, 2)
        assert storage.pending_users(109318, retry_errors=True) == []

        exact = storage.find_cards(109318, ["#005010"], "exact")
        exact_numeric = storage.find_cards(109318, ["5010"], "exact")
        contains = storage.find_cards(109318, ["22"], "contains")
        regex = storage.find_cards(109318, [r"^#?22\d\d$"], "regex")
        filtered = storage.find_cards(
            109318, ["005010"], "exact", card_type_id=999
        )
        assert [row["card_id"] for row in exact] == [90001]
        assert [row["card_id"] for row in exact_numeric] == [90001]
        assert [row["card_id"] for row in contains] == [90002]
        assert [row["card_id"] for row in regex] == [90002]
        assert filtered == []

        stats = storage.card_type_stats(109318)
        assert len(stats) == 1
        assert stats[0]["card_type_id"] == 701
        assert stats[0]["owner_count"] == 1
        assert stats[0]["instance_count"] == 2

        output = tmp_path / "cards.csv"
        assert storage.export_cards(109318, output) == 2
        assert "005010" in output.read_text(encoding="utf-8-sig")

        status = storage.status(109318)
        assert status["ranked_users"] == 1
        assert status["fetched_users"] == 1
        assert status["card_instances"] == 2


def test_error_retry_policy(tmp_path: Path) -> None:
    with Storage(tmp_path / "test.sqlite3") as storage:
        storage.upsert_ranking_users(109318, [ranking_user()])
        storage.mark_error(109318, 10001, "temporary error")
        assert len(storage.pending_users(109318, retry_errors=True)) == 1
        assert storage.pending_users(109318, retry_errors=False) == []


def test_summary_only_user_is_automatically_refetched(tmp_path: Path) -> None:
    summary_payload = {
        "card_list": [
            {
                "card_no": "CD.001107",
                "card_owned_cnt": 3,
                "card_item": {
                    "card_type_id": 701,
                    "card_name": "测试卡片",
                    "card_id_list": None,
                },
            }
        ]
    }
    with Storage(tmp_path / "test.sqlite3") as storage:
        storage.upsert_ranking_users(109318, [ranking_user()])
        storage.save_user_cards(109318, 10001, summary_payload)
        assert len(storage.pending_users(109318, retry_errors=True)) == 1

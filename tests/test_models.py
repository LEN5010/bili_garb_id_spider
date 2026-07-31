from bili_garb_id_spider.models import parse_ranking_users


def test_parse_ranking_users_computes_global_position() -> None:
    users = parse_ranking_users(
        {
            "list": [
                {
                    "uid": 10001,
                    "uname": "测试用户",
                    "score": 88,
                    "face": "https://example.invalid/avatar.jpg",
                    "comment_pic": "",
                }
            ]
        },
        page=3,
        page_size=20,
    )
    assert len(users) == 1
    assert users[0].uid == 10001
    assert users[0].ranking_position == 41

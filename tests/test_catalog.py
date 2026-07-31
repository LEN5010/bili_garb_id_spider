from bili_garb_id_spider.catalog import parse_collection_cards, parse_collections


def test_parse_collections_filters_regular_garbs() -> None:
    payload = {
        "list": [
            {
                "name": "测试收藏集",
                "item_id": 0,
                "properties": {"dlc_act_id": "109318"},
                "lottery_id": 113755,
            },
            {
                "name": "普通装扮",
                "item_id": 7788,
                "properties": {},
            },
        ]
    }
    collections = parse_collections(payload)
    assert len(collections) == 1
    assert collections[0].name == "测试收藏集"
    assert collections[0].act_id == 109318
    assert collections[0].lottery_id == 113755


def test_parse_collection_cards() -> None:
    payload = {
        "item_list": [
            {
                "card_info": {
                    "card_type_id": 701,
                    "card_name": "卡片 A",
                    "card_img": "https://example.invalid/a.png",
                }
            },
            {
                "card_info": {
                    "card_type_id": 702,
                    "card_name": "卡片 B",
                    "card_img": "https://example.invalid/b.png",
                }
            },
        ]
    }
    cards = parse_collection_cards(payload)
    assert [(card.card_type_id, card.name) for card in cards] == [
        (701, "卡片 A"),
        (702, "卡片 B"),
    ]

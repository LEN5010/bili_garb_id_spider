from __future__ import annotations

import asyncio
from pathlib import Path

from .catalog import Collection, CollectionCard, get_collection_cards, search_collections
from .client import BilibiliClient
from .cli import output_matches, print_status
from .config import Credentials, load_credentials
from .login import qr_login
from .spider import Spider
from .storage import Storage


ENV_FILE = Path(".env")
DB_FILE = Path("data/garb.sqlite3")


def ask_number(
    prompt: str,
    *,
    minimum: int,
    maximum: int,
    default: int | None = None,
) -> int:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        value = input(f"{prompt}{suffix}: ").strip()
        if not value and default is not None:
            return default
        try:
            number = int(value)
        except ValueError:
            print("请输入数字。")
            continue
        if minimum <= number <= maximum:
            return number
        print(f"请输入 {minimum} 到 {maximum} 之间的数字。")


def ask_optional_positive_int(prompt: str) -> int | None:
    while True:
        value = input(f"{prompt}（直接回车表示不限）: ").strip()
        if not value:
            return None
        try:
            number = int(value)
        except ValueError:
            print("请输入正整数。")
            continue
        if number > 0:
            return number
        print("请输入正整数。")


def choose_collection(collections: list[Collection]) -> Collection:
    print("\n搜索到以下收藏集：")
    for index, collection in enumerate(collections, 1):
        lottery = (
            f"，lottery_id={collection.lottery_id}"
            if collection.lottery_id is not None
            else ""
        )
        print(f"  [{index}] {collection.name}（act_id={collection.act_id}{lottery}）")
    choice = ask_number("请输入收藏集序号", minimum=1, maximum=len(collections))
    return collections[choice - 1]


def choose_card(cards: list[CollectionCard]) -> CollectionCard | None:
    if not cards:
        print("未能从收藏集详情中解析卡片列表，将抓取并统计全部卡片。")
        return None
    print("\n这个收藏集包含以下卡片：")
    print("  [0] 全部卡片")
    for index, card in enumerate(cards, 1):
        print(f"  [{index}] {card.name}（card_type_id={card.card_type_id}）")
    choice = ask_number("请选择重点查找的卡片", minimum=0, maximum=len(cards), default=0)
    return None if choice == 0 else cards[choice - 1]


def choose_scan_scope() -> tuple[int | None, int | None]:
    print("\n抓取范围：")
    print("  [1] 快速测试（1 页排行榜、3 位用户）")
    print("  [2] 完整抓取")
    print("  [3] 自定义")
    choice = ask_number("请选择", minimum=1, maximum=3, default=1)
    if choice == 1:
        return 1, 3
    if choice == 2:
        return None, None
    return (
        ask_optional_positive_int("最多抓取排行榜页数"),
        ask_optional_positive_int("最多抓取用户数"),
    )


async def ensure_login(credentials: Credentials) -> Credentials | None:
    if credentials.authenticated:
        return credentials
    print("当前未登录，用户卡片接口无法使用。")
    choice = ask_number("现在进行二维码登录？[1] 是 [0] 返回", minimum=0, maximum=1)
    if choice == 0:
        return None
    return await qr_login(ENV_FILE)


async def search_and_scan() -> None:
    credentials = load_credentials(ENV_FILE)
    keyword = input("请输入收藏集名称或关键词: ").strip()
    if not keyword:
        print("名称不能为空。")
        return
    print("正在搜索收藏集……")
    collections = await search_collections(keyword, credentials)
    if not collections:
        print("没有找到收藏集；搜索结果中的普通装扮已自动排除。")
        return
    collection = choose_collection(collections)
    print(f"正在读取《{collection.name}》的卡片列表……")
    cards = await get_collection_cards(collection.act_id, credentials)
    selected_card = choose_card(cards)
    credentials = await ensure_login(credentials)
    if credentials is None:
        return
    max_pages, limit_users = choose_scan_scope()

    focus = (
        f"重点卡片：{selected_card.name}（{selected_card.card_type_id}）"
        if selected_card
        else "统计全部卡片"
    )
    print(
        f"\n即将抓取《{collection.name}》，act_id={collection.act_id}；{focus}。\n"
        "用户卡片接口一次会返回该用户在收藏集内的全部卡片，"
        "因此工具会完整保存，再按所选卡片筛选结果。"
    )
    if ask_number("开始抓取？[1] 开始 [0] 返回", minimum=0, maximum=1, default=1) == 0:
        return

    with Storage(DB_FILE) as storage:
        async with BilibiliClient(credentials) as client:
            spider = Spider(client, storage)
            await spider.scan_ranking(
                collection.act_id,
                page_size=20,
                max_pages=max_pages,
            )
            result = await spider.scan_user_cards(
                collection.act_id,
                concurrency=2,
                limit=limit_users,
                retry_errors=True,
            )
        print(
            "\n抓取完成："
            f"成功 {result['ok']}，隐私隐藏 {result['private']}，"
            f"失败 {result['error']}，卡片编号 {result['card_instances']}。"
        )
        print("\n当前卡片统计：")
        for row in storage.card_type_stats(collection.act_id):
            marker = (
                "  ← 已选择"
                if selected_card
                and row["card_type_id"] == selected_card.card_type_id
                else ""
            )
            print(
                f"  {row['card_name']}（{row['card_type_id']}）："
                f"{row['owner_count']} 位持有者，{row['instance_count']} 个编号{marker}"
            )
        card_ids = input("\n输入要查找的 ID（多个用空格分隔，回车跳过）: ").split()
        if card_ids:
            rows = storage.find_cards(
                collection.act_id,
                card_ids,
                "exact",
                selected_card.card_type_id if selected_card else None,
            )
            output_matches(rows, None)


def show_status() -> None:
    act_id = ask_number("请输入 act_id", minimum=1, maximum=2**63 - 1)
    with Storage(DB_FILE) as storage:
        print_status(storage, act_id)
        for row in storage.card_type_stats(act_id):
            print(
                f"  {row['card_name']}（card_type_id={row['card_type_id']}）："
                f"{row['owner_count']} 位持有者，{row['instance_count']} 个编号"
            )


def find_id() -> None:
    act_id = ask_number("请输入 act_id", minimum=1, maximum=2**63 - 1)
    patterns = input("请输入要查找的 ID（多个用空格分隔）: ").split()
    if not patterns:
        print("未输入号码。")
        return
    mode_choice = ask_number(
        "匹配方式：[1] 精确 [2] 包含 [3] 正则",
        minimum=1,
        maximum=3,
        default=1,
    )
    mode = {1: "exact", 2: "contains", 3: "regex"}[mode_choice]
    with Storage(DB_FILE) as storage:
        stats = storage.card_type_stats(act_id)
        card_type_id: int | None = None
        if stats:
            print("  [0] 全部卡片")
            for index, row in enumerate(stats, 1):
                print(
                    f"  [{index}] {row['card_name']}（card_type_id={row['card_type_id']}）"
                )
            choice = ask_number(
                "限定卡片", minimum=0, maximum=len(stats), default=0
            )
            if choice:
                card_type_id = int(stats[choice - 1]["card_type_id"])
        rows = storage.find_cards(act_id, patterns, mode, card_type_id)
        output_matches(rows, None)


async def login_menu() -> None:
    await qr_login(ENV_FILE)


def print_menu() -> None:
    credentials = load_credentials(ENV_FILE)
    state = "已登录" if credentials.authenticated else "未登录"
    print("\n" + "=" * 56)
    print(f"Bilibili 收藏集卡片 ID 工具    当前状态：{state}")
    print("=" * 56)
    print("  [1] 二维码登录 / 更新登录")
    print("  [2] 按名称搜索收藏集并开始抓取")
    print("  [3] 查看抓取进度和卡片统计")
    print("  [4] 查找 ID")
    print("  [0] 退出")


async def interactive_main() -> None:
    try:
        from bilibili_api import select_client

        select_client("httpx")
    except Exception:
        pass
    while True:
        print_menu()
        choice = ask_number("请选择功能", minimum=0, maximum=4)
        try:
            if choice == 0:
                print("再见。")
                return
            if choice == 1:
                await login_menu()
            elif choice == 2:
                await search_and_scan()
            elif choice == 3:
                show_status()
            elif choice == 4:
                find_id()
        except KeyboardInterrupt:
            print("\n操作已取消，已保存的抓取数据不会丢失。")
        except Exception as exc:
            print(f"\n操作失败：{exc}")


def main() -> None:
    try:
        asyncio.run(interactive_main())
    except KeyboardInterrupt:
        print("\n已退出。")


if __name__ == "__main__":
    main()

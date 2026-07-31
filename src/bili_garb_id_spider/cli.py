from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path

import httpx

from .client import AuthenticationRequired, BilibiliAPIError, BilibiliClient
from .config import load_credentials
from .spider import Spider
from .storage import Storage


def positive_int(value: str) -> int:
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bili-garb-spider",
        description="遍历 Bilibili 数字卡片收藏排行榜并检索卡片编号",
    )
    parser.add_argument("--db", type=Path, default=Path("data/garb.sqlite3"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="抓取排行榜和用户卡片")
    scan.add_argument("--act-id", type=positive_int, required=True)
    scan.add_argument("--page-size", type=positive_int, default=20)
    scan.add_argument("--max-pages", type=positive_int)
    scan.add_argument("--limit-users", type=positive_int)
    scan.add_argument("--concurrency", type=positive_int, default=2)
    scan.add_argument("--delay-min", type=float, default=0.8)
    scan.add_argument("--delay-max", type=float, default=1.8)
    scan.add_argument("--ranking-only", action="store_true")
    scan.add_argument(
        "--no-retry-errors",
        action="store_true",
        help="断点续跑时跳过此前失败的用户",
    )
    scan.add_argument("--env-file", type=Path, default=Path(".env"))
    scan.add_argument(
        "--cookie-file",
        type=Path,
        help="包含原始 Cookie 请求头的本地文件；内容不会写入数据库",
    )

    status = subparsers.add_parser("status", help="查看当前抓取进度")
    status.add_argument("--act-id", type=positive_int, required=True)

    export = subparsers.add_parser("export", help="导出所有卡片实例 CSV")
    export.add_argument("--act-id", type=positive_int, required=True)
    export.add_argument("--out", type=Path, default=Path("output/cards.csv"))

    find = subparsers.add_parser("find", help="查找 ID")
    find.add_argument("--act-id", type=positive_int, required=True)
    find.add_argument("patterns", nargs="+", help="一个或多个号码/正则表达式")
    find.add_argument(
        "--mode", choices=("exact", "contains", "regex"), default="exact"
    )
    find.add_argument("--out", type=Path, help="可选：把匹配结果写入 CSV")
    return parser


async def run_scan(args: argparse.Namespace, storage: Storage) -> None:
    credentials = load_credentials(args.env_file, args.cookie_file)
    async with BilibiliClient(
        credentials,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
    ) as client:
        spider = Spider(client, storage)
        ranked = await spider.scan_ranking(
            args.act_id,
            page_size=args.page_size,
            max_pages=args.max_pages,
        )
        print(f"排行榜抓取完成：本轮读取 {ranked} 条")
        if args.ranking_only:
            return
        result = await spider.scan_user_cards(
            args.act_id,
            concurrency=args.concurrency,
            limit=args.limit_users,
            retry_errors=not args.no_retry_errors,
        )
        print(
            "用户卡片抓取完成："
            f"成功 {result['ok']}，隐私隐藏 {result['private']}，"
            f"失败 {result['error']}，卡片编号 {result['card_instances']}"
        )


def print_status(storage: Storage, act_id: int) -> None:
    values = storage.status(act_id)
    print(f"act_id: {act_id}")
    print(f"排行榜用户: {values['ranked_users']}")
    print(f"已抓取用户: {values['fetched_users']}")
    print(f"隐私隐藏: {values['private_users']}")
    print(f"失败用户: {values['error_users']}")
    print(f"卡片编号: {values['card_instances']}")


def output_matches(rows: list, out: Path | None) -> None:
    headers = [
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
    print(f"匹配到 {len(rows)} 个卡片 ID")
    for row in rows:
        print(
            f"#{row['ranking_position']} {row['uname']} ({row['uid']}) | "
            f"{row['card_name']} | 编号 {row['card_no']} | card_id={row['card_id']}"
        )
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(dict(row) for row in rows)
        print(f"已写入 {out}")


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        with Storage(args.db) as storage:
            if args.command == "scan":
                asyncio.run(run_scan(args, storage))
            elif args.command == "status":
                print_status(storage, args.act_id)
            elif args.command == "export":
                count = storage.export_cards(args.act_id, args.out)
                print(f"已导出 {count} 条卡片编号到 {args.out}")
            elif args.command == "find":
                rows = storage.find_cards(args.act_id, args.patterns, args.mode)
                output_matches(rows, args.out)
    except (AuthenticationRequired, BilibiliAPIError, httpx.HTTPError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except KeyboardInterrupt:
        print("\n已中断；当前进度已保存在 SQLite，可再次运行继续。")
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()

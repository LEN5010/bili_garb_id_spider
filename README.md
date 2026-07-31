# bili-garb-id-spider

遍历哔哩哔哩数字卡片收藏排行榜用户，保存其公开可见的卡片及编号，并按 ID 查找所属用户。

这个工具直接调用页面使用的 JSON 接口，不模拟点击，也不需要注入 JS Bridge：

- 排行榜：`/x/vas/dlc_act/act/top/list`
- 用户图鉴摘要：`/x/vas/user/dlc/card/list`
- 用户完整卡片编号：`/x/vas/user/dlc/right/card`

完整卡片编号接口需要已登录账号的 Cookie。工具不会把 Cookie 写进 SQLite 或 CSV，也不会在日志中打印 Cookie。

## 安装

需要 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)：

```bash
uv sync --dev --no-editable
uv run bili-garb-spider --help
```

使用 `--no-editable` 可以兼容会跳过隐藏 `.pth` 文件的新版 Python 运行时。

## 交互模式（推荐）

直接运行：

```bash
uv run python run.py
```

随后使用数字菜单即可完成：

1. 使用手机客户端扫描终端二维码登录；
2. 输入名称搜索收藏集；
3. 从搜索结果中输入数字选择收藏集；
4. 查看收藏集内的卡片名称和 `card_type_id`，选择全部或某张卡片；
5. 选择快速测试、完整抓取或自定义范围；
6. 抓取完成后直接输入 ID 查找所属用户。

用户卡片接口一次会返回该用户在当前收藏集内的全部卡片，因此即使选择某一张重点卡片，工具也会把其他卡片一起保存，不会增加请求次数。所选卡片用于限定 ID 查找结果。

## 配置登录凭据

复制示例配置：

```bash
cp .env.example .env
```

从已登录哔哩哔哩的浏览器中复制 `SESSDATA`、`bili_jct`、`buvid3` 和 `DedeUserID`。至少需要 `SESSDATA`，建议四项都填写。`.env` 已被 Git 忽略。

也可以把浏览器里复制出的完整 `Cookie:` 请求头放在项目外的文本文件中，并在扫描时使用 `--cookie-file /path/to/cookie.txt`。

Cookie 相当于登录凭据，请勿上传、提交或发给他人。

使用交互模式二维码登录后，凭据会自动保存到 `.env`，文件权限设为仅当前用户可读写。

二维码登录使用 TV 通道，因为该通道会在成功响应中直接返回 Cookie；Web 通道在部分账号流程中可能显示登录成功，却没有返回可解析的 `SESSDATA`。

## 抓取

先用少量用户验证登录和接口：

```bash
uv run bili-garb-spider scan \
  --act-id 109318 \
  --max-pages 1 \
  --limit-users 3
```

确认正常后抓取完整排行榜：

```bash
uv run bili-garb-spider scan --act-id 109318
```

默认全局请求间隔为 0.8–1.8 秒、并发数为 2。数据实时写入 `data/garb.sqlite3`，中断后执行同一命令会跳过已成功或隐私隐藏的用户，并重试失败用户。

只抓排行榜、不使用登录凭据：

```bash
uv run bili-garb-spider scan --act-id 109318 --ranking-only
```

降低请求频率：

```bash
uv run bili-garb-spider scan \
  --act-id 109318 \
  --concurrency 1 \
  --delay-min 1.5 \
  --delay-max 3
```

查看进度：

```bash
uv run bili-garb-spider status --act-id 109318
```

## 查找 ID

精确匹配会自动兼容 `1107`、`001107`、`#001107` 和 `CD.001107`
这几种输入形式；数据库与导出文件仍保留原始前导零：

```bash
uv run bili-garb-spider find --act-id 109318 005010 2233
```

包含匹配：

```bash
uv run bili-garb-spider find --act-id 109318 5010 --mode contains
```

正则匹配：

```bash
uv run bili-garb-spider find --act-id 109318 '^#?66[0-9]{2}$' --mode regex
```

匹配结果可附加 `--out output/id-matches.csv` 导出。所有卡片编号可直接导出：

```bash
uv run bili-garb-spider export \
  --act-id 109318 \
  --out output/all-cards.csv
```

## 注意事项

- 排行榜属于整个 `act_id`；示例页面中的 `lottery_id` 用于页面展示，不是排行榜接口的分页参数。
- 用户关闭收藏展示时会记录为 `private`，工具不会尝试绕过隐私设置。
- 接口是网页内部接口，可能随哔哩哔哩改版而变化。
- 请仅以合理频率处理公开可见数据，遵守平台规则，不要把结果用于骚扰、画像或其他侵害用户权益的用途。

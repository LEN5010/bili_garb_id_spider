# bili-garb-id-spider

用于遍历哔哩哔哩数字卡片收藏排行榜用户，保存其公开可见的卡片及编号，并按 ID 查找所属用户。

这个工具调用页面使用的 JSON 接口如下：

- 排行榜：`/x/vas/dlc_act/act/top/list`
- 用户图鉴摘要：`/x/vas/user/dlc/card/list`
- 用户完整卡片编号：`/x/vas/user/dlc/right/card`

## Windows 免安装版（推荐）

普通用户不需要安装 Python、uv 或 Git：

1. 打开 [Releases 下载页面](https://github.com/LEN5010/bili_garb_id_spider/releases/latest)；
2. 下载名称以 `windows-x64.zip` 结尾的文件；
3. **完整解压 ZIP**；
4. 双击 `启动工具.bat`；
5. 第一次使用请选择 `[1]`，用哔哩哔哩手机客户端扫码登录。

如果 Windows 显示“已保护你的电脑”，请确认文件来自上述官方项目页面，
然后点击“更多信息”→“仍要运行”。当前程序未购买代码签名证书，因此可能
出现这项提示。

程序会在解压目录生成 `.env` 和 `data/garb.sqlite3`。前者是登录凭据，
后者保存抓取进度；升级版本时请保留它们。不要将 `.env` 发送给其他人。

## 源码运行（macOS、Linux 和开发者）

需要 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)：

```bash
git clone https://github.com/LEN5010/bili_garb_id_spider.git
cd bili_garb_id_spider
uv sync --dev --no-editable
uv run python run.py
```

## 交互菜单

Windows 免安装版和源码版使用相同的数字菜单：

1. 使用手机客户端扫描终端二维码登录；
2. 输入名称搜索收藏集；
3. 从搜索结果中输入数字选择收藏集；
4. 查看收藏集内的卡片名称和 `card_type_id`，选择全部或某张卡片；
5. 选择快速测试、完整抓取或自定义范围；
6. 抓取完成后直接输入 ID 查找所属用户。

用户卡片接口一次会返回该用户在当前收藏集内的全部卡片，因此即使选择某一张重点卡片，工具也会把其他卡片一起保存，不会增加请求次数。所选卡片用于限定 ID 查找结果。

## 登录凭据

推荐直接在菜单中选择 `[1]` 扫码登录。凭据会自动保存到 `.env`，工具
不会要求输入账号密码。

如需手动配置，可以复制示例配置：


```bash
cp .env.example .env
```

从已登录哔哩哔哩的浏览器中复制 `SESSDATA`、`bili_jct`、`buvid3` 和 `DedeUserID`。至少需要 `SESSDATA`，建议四项都填写。`.env` 已被 Git 忽略。

也可以把浏览器里复制出的完整 `Cookie:` 请求头放在项目外的文本文件中，并在扫描时使用 `--cookie-file /path/to/cookie.txt`。

Cookie 相当于登录凭据，请勿上传、提交或发给他人。

使用交互模式二维码登录后，凭据会自动保存到 `.env`。macOS 和 Linux
会将文件权限设为仅当前用户可读写；Windows 用户也请勿共享该文件。

二维码登录使用 TV 通道，因为该通道会在成功响应中直接返回 Cookie；Web 通道在部分账号流程中可能显示登录成功，却没有返回可解析的 `SESSDATA`。

## 命令行模式（进阶）

先用少量用户验证登录和接口：

```bash
uv run bili-garb-spider scan \
  --act-id 109318 \
  --max-pages 1 \
  --limit-users 3
```

确认正常后抓取完整排行榜（接口最多展示前 1000 个榜位）：

```bash
uv run bili-garb-spider scan --act-id 109318
```

工具按排行榜原始榜位翻页，最多读取 50 页、1000 个榜位。隐藏 UID
的榜位无法继续查询卡片，会跳过但不会导致分页提前结束。

默认全局请求间隔为 0.8–1.8 秒、并发数为 2。完整抓取可能需要约
20–30 分钟。数据实时写入 `data/garb.sqlite3`，中断后执行同一命令会
跳过已成功或隐私隐藏的用户，并重试失败用户。

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

- 排行榜属于整个 `act_id`；示例页面中的 `lottery_id` 只用于页面展示。
- 用户关闭收藏展示时会记录为 `private`，工具不会尝试绕过隐私设置。
- 接口是网页内部接口，可能随哔哩哔哩改版而变化。
- 请仅以合理频率处理公开可见数据，遵守平台规则，不要把结果用于骚扰、画像或其他侵害用户权益的用途。

## 许可证

本项目采用 [GNU Affero General Public License v3.0](LICENSE)，
SPDX 标识为 `AGPL-3.0-only`。

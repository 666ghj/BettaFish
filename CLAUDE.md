# BettaFish 项目注意事项

## 爬虫平台兼容性问题

### 1. 抖音 (Douyin) — aweme_id/comment_id 类型不匹配
- **根因：** MediaCrawler 的 `database/models.py` 中 `aweme_id` / `comment_id` 定义为 `BigInteger`，但 API 返回的是字符串。`_store_impl.py` 做了 `int()` 转换用于 WHERE 查询，但**没有把 int 值写回 `content_item` 字典**，导致 `DouyinAweme(**content_item)` 传给 asyncpg 时仍是字符串，PostgreSQL 报 `invalid input for query argument: str object cannot be interpreted as an integer`。
- **影响范围：** PostgreSQL 环境下必现。MySQL 因隐式类型转换不会报错。
- **修复方案：** 在 `store/douyin/_store_impl.py` 中，`aweme_id = int(content_item.get("aweme_id"))` 后加一行 `content_item["aweme_id"] = aweme_id`；`comment_id` 同理。
- **建议：** 放弃抖音爬取，改用搜索 API Key（Tavily/Anspire）通过 QueryEngine/MediaEngine 获取实时数据。

### 2. 快手 (Kuaishou) — comment_id 类型不匹配
- **根因：** 同抖音，`kuaishou_video_comment.comment_id` 在数据库中是 `bigint`，但 store 层传入字符串，PostgreSQL 报 `operator does not exist: bigint = character varying`。
- **影响范围：** 视频数据可以正常爬取，评论写入失败。
- **修复方案：** 在 `store/kuaishou/_store_impl.py` 的 `store_comment` 方法中，`comment_id` 做 `int()` 转换并写回字典。
- **建议：** 放弃快手爬取。

### 3. 小红书 (Xiaohongshu) — humps.decamelize AttributeError
- **根因：** `pyhumps` 库版本不兼容。低版本和高版本的 API 不同，`extractor.py` 调用的 `humps.decamelize()` 在新版本中不存在。
- **修复方案：** `pip install pyhumps==3.8.0` 锁定兼容版本。
- **参考 Issue：** https://github.com/666ghj/BettaFish/issues/656

### 4. 知乎 (Zhihu) — 社区已知问题
- **参考 Issue：** https://github.com/666ghj/BettaFish/issues/389（分页重复爬取）
- **参考 Issue：** https://github.com/666ghj/BettaFish/issues/399（字段类型不匹配）

### 5. 贴吧 (Tieba) — 元素定位符失效 / 需要手动扫码登录
- **根因：** 贴吧登录流程中，`login.py` 使用 CSS 选择器 `"//li[@class='u_login']"` 定位登录按钮，该选择器在当前贴吧页面结构上无法匹配。同时 `"//img[@class='tang-pass-qrcode-img']"` 无法找到二维码图片，30 秒超时后失败。
- **影响范围：** 当前贴吧页面结构与爬虫代码中的定位符不匹配。
- **建议：** 放弃贴吧爬取。

### 6. 平台兼容性一览
- **✅ 可正常爬取：** 微博 (wb)、B站 (bili)
- **❌ 不可爬取：** 抖音 (dy)、快手 (ks)、小红书 (xhs)、知乎 (zhihu)、贴吧 (tieba)
- 不可爬取的平台数据可通过搜索 API Key（Tavily/Anspire）从前端界面获取实时数据。

## 部署注意事项

### PostgreSQL 与 asyncpg 版本
- `requirements.txt` 中 `asyncpg` 没有锁定版本，最新版 0.31.0 对类型检查更严格，会暴露字符串传 BigInteger 列的问题。
- Docker 镜像内置的 asyncpg 0.29.0 类型检查较宽松，不会报这个错。
- 宿主机 `uv run` 安装时会获取最新版，需注意版本差异。

### 数据库初始化
- **务必使用 Docker 容器内的代码初始化数据库**（通过 `docker exec bettafish python3 -c "from MindSpider.main import MindSpider; MindSpider().initialize_database()"`），因为容器内 `models_bigdata.py` 的 `aweme_id` 类型是 `BigInteger`，与 MediaCrawler 运行时模型一致。
- 不要在宿主机上通过 `uv run python main.py --setup` 初始化数据库，宿主机代码可能包含不同的模型定义。

### 运行爬虫
- 在宿主机用 `uv run python main.py --deep-sentiment` 运行爬虫，数据库指到 Docker 暴露的端口（`127.0.0.1:5444`）。
- 运行前确认 `.env` 文件配置正确，且 shell 环境变量中没有 `DB_HOST` 等覆盖变量（可用 `DB_HOST=127.0.0.1 DB_PORT=5444 uv run ...` 明确指定）。

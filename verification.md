# 溯源功能验证记录

最终验证日期：2026-10-18。分支：`maven/provenance-citations`。用户已审查中文日志并批准创建本地提交；本次不推送远程。运行日志、凭证和生成产物不随源码提交。

## 修复范围

| 问题 | 修复与覆盖 |
| --- | --- |
| 三个 Streamlit runner 调用不存在的 `_save_report()` | runner 与真实 Agent 共用 `save_engine_report()`，验证 Markdown/sidecar 保存成功后再发布 runtime result，覆盖失败路径。 |
| Insight 无日期平台检索丢失 lineage | 使用 `{"kind":"unbounded"}`，验证返回行、证据捕获及初始总结。 |
| Runtime 活跃任务突破容量上限 | 达到容量拒绝创建并返回 429；覆盖 TTL、终态回收、输入大小及轮次隔离。 |
| 报告可见内容或继承引用绕过主张门禁 | 富文本、标题、图表数值与标签逐项覆盖；清理继承引用；推断至少两条有效证据；索引与最终可渲染块一致。 |
| Forum 超过 200 条证据后丢失合法摘要 | 可信证据白名单不截断，保留单条消息引用数量限制。 |
| 原子保存失败遗留临时文件 | 覆盖写入/fsync 失败、旧文件保留及临时文件清理。 |
| Media 搜索异常日志暴露认证信息 | Bocha/Anspire 使用受控错误信息，增加脱敏回归。 |
| 报告章节断流导致整份重跑 | 在现有章节循环重试当前章，复用状态分类和尝试计数，保留前章，删除 Flask 整份重跑兜底；清空半截 raw 并关闭 SDK 流。 |
| 取消状态被晚到进度、保存或错误覆盖 | 取消为吸收终态；旧 worker 退出前保留资源占用，入口原子检查并返回 409，退出后释放。 |
| 取消等待模型下一片段或网络超时 | 每个报告任务绑定独立取消令牌，主动中断模型 HTTP 任务并唤醒重试退避；模板、章节、结构修复和图表修复共同透传取消。请求连接与线程清理完成后才释放 worker。 |
| 根 pytest 导入内嵌爬虫后包名冲突 | 默认测试范围包含主项目、Report 工具及爬虫独立进程桥接。爬虫测试补丁由父仓库携带，仅应用到临时副本，原子模块 clean，gitlink 未改。 |

持久化、状态恢复、身份校验、引用详情和主张筛选均复用公共入口。章节生成与装订共用 `sanitize_blocks()`，移除旧的重复 heading 过滤方法；网络重试复用已有 HTTP 状态判断，没有叠加整份重试层。

## 2026-10-18 自动化验证

环境：`D:\conda\envs\bettafish\python.exe`；pytest 9.0.2、pytest-asyncio 1.4.0、openpyxl 3.1.5。新增 `requirements-test.txt` 记录测试依赖，默认禁用 pytest cache，pytest basetemp 写入 `logs/`。

```powershell
& 'D:\conda\envs\bettafish\python.exe' -m pytest -q --tb=short
```

结果：**344 passed，51 subtests passed，25 warnings，退出码 0**，耗时 34.46 秒。无失败、无跳过。日志：`logs/pytest-final-cancellation-20261018.log`。警告来自 Pydantic、Pyparsing 和 Eventlet 的弃用接口。

默认测试中的爬虫桥接实际执行 **23 passed、16 条第三方警告、0 skipped**。344 包含桥接本身，不将 23 再累加成主测试数量。另有失败传播用例，启动故意断言失败的子测试，确认父 pytest 返回 1 并保留失败原因。

章节专项新增 18 项。断流成功用例使用真实 Agent、章节节点、存储、装订、HTML 渲染及正式保存，仅替换外部模型和规划响应；验证前章不重跑、本章 raw 不拼接、HTML/IR/state/sidecar 一致、Markdown 引用可追踪。覆盖预算耗尽、401/404/额度不足不重试、SDK 流释放、取消不重试、取消状态竞态和旧 worker 占用。独立复核运行章节、取消接口及重试工具三组：**44 passed**；重新注入 progress/persist/html_ready 三种取消时序，均为 cancelled、0 个 completed 事件、worker 已释放。

候选变更共 80 个文件，其中 71 个 Python 文件 AST 解析通过；UTF-8 无 BOM 检查通过；凭证模式检查 0 命中。`git diff --check` 通过，验证时暂存区为空，原 MediaCrawler 子模块无修改。测试补丁须保留匹配原文件的空白上下文，`.gitattributes` 仅对 `test_support/*.patch` 禁用空白报错，源码仍按原规则检查。历史日志、trace、`.env` 和生成报告不随源码提交。

### 主动取消与连接生命周期

每个 Flask 报告任务绑定独立 `CancellationToken`，通过任务作用域传给统一模型入口及临时修复客户端。作用域内的每次模型请求独占异步客户端、事件循环和请求线程；取消直接中断 HTTP 任务，重试等待通过令牌唤醒。响应和客户端在受保护的清理任务中关闭，主线程等待其完成并 join 请求线程，之后才释放报告 worker。没有令牌的原同步调用维持原路径。

新增 token、作用域、异常透传、网络和生命周期测试；网络与生命周期共 22 条，实际连接随机端口本机 HTTP 服务，不使用外部模型。覆盖等待响应头、首 token、后续片段、非流式响应体、真实 503 后退避、布局/章节阶段、预取消、并发任务隔离、提前关闭流、清理中取消及最终片段后的取消。阻塞网络用例要求调用退出和对端 EOF/reset 在共同 2 秒期限内完成。同一客户端和 Agent 在新令牌下可完成报告，HTML/IR/state/sidecar 正式保存一致。

公开接口集成从真实 Flask `/api/report/generate` 开始，经临时 Markdown/sidecar、真实 worker、ReportAgent 与 HTTP 请求，在章节首 delta 后调用 `/api/report/cancel/<task_id>`。确认取消状态不被完成/异常覆盖、没有最终报告、半截 raw 清空、socket 关闭、worker 释放，再经同一服务生成新报告并读取 `/result` 及四类产物。仅目录基线、日志清空、模板选择和字数规划使用固定离线输入。禁用网络取消或令牌信号的负对照均在 2 秒边界失败。

独立探针使用真实 `LLMClient`，HTTP/HTTPS 各覆盖等待响应头、首块和流中途，共 6 例。取消到对端 EOF 为 0.49–0.99 ms，调用方退出为 2.11–3.47 ms，每例只有 1 次请求；这是本机实测值，不是跨机器或网络时延保证。另给 keepalive 客户端关闭增加 200 ms 等待，正常成功与关闭中取消都在显式关闭连接后才返回。修复前/后记录为 `logs/cancel_llm_integration_before_cleanup_fix.json`、`logs/cancel_llm_integration_after_cleanup_fix.json`。

本轮红绿验证另抓到并修复两项真实竞态：首次取消发生在 `client.close()` 内会中断清理；流请求已经自然完成时，最后的 done 消息会吞掉刚到达的取消。对应正式用例修复前均失败，修复后通过。首轮全套中另有测试服务端发送完成与事件设置先后的调度竞态，已将瞬时检查改为有界等待，未放宽生产取消期限；最终重新运行根目录全套，结果如上。

## 真实检索与最新产物复核

2026-10-16 已实际执行“清华鹅腿阿姨”的三个研究引擎，经本机 callback、ReportEngine、HTML/JSON 结果接口、Markdown 导出完成全流程：

- provenance run：`a3c6355012824785a960f89ed1a2caf9`。
- 外层任务：`report_1792135268043484600_ef8eacf2`；内部报告：`report-eaa140a8`。当时结果 completed / 100%，HTML、JSON、Markdown 接口均实际返回 200。
- Query 71 个来源、89 条候选证据；Media 125 个原始来源、127 条候选证据；Insight 实际数据库无该主题记录，正文和证据为空，没有显示无证据占位文字。
- 当时首轮 Report 供应商断流，整份重试后成功。本次已用受控故障注入验证替换后的章节恢复路径，不再依赖该整份重试。

2026-10-18 使用上述真实六章数据，按最新代码重新装订、执行门禁、HTML/Markdown 渲染及正式保存；本次没有重新执行整轮外部检索或六章模型生成，不把数据重放称为新一轮真实研究。

- HTML：`final_reports/final_report_清华鹅腿阿姨_20261018_111141_664726_report-eaa140a8_1d495baa.html`。
- Markdown 与 `.provenance.json`：与 HTML 同 stem。
- IR：`final_reports/ir/report_ir_清华鹅腿阿姨_20261018_111141_664726_report-eaa140a8_1d495baa.json`。
- 195 个来源、215 条证据、60 项主张；HTML/Markdown 各 76 处引用，使用 24 条不同证据。IR/state/sidecar 的 bundle 完全相等，query/run_id 一致；无悬空引用、章节根节点 claim、单证据推断或无证据占位文字。

Playwright + Chrome 实际打开新 HTML，检查 76 处引用、来源链接匹配、悬浮详情包含来源及引用理由，页面脚本错误 0。截图：`output/playwright/provenance-review-tooltip-20261018.png`。审计结果：`logs/provenance_review_replay.json`、`logs/provenance_browser_review.json`。

## 当前服务与配置

主动取消修复和最终全套测试完成后，已再次重启 Flask 加载最新代码，通过 `/api/system/start` 启动完整组件。当前入口：`http://127.0.0.1:5000/`；Insight/Media/Query 使用本地 `.env` 的 `8651/8652/8653`。Forum running，ReportEngine initialized，当前无报告生成任务。三个 `/_stcore/health` 均返回 200。

浏览器实际打开主页面及三个 Streamlit 页面，搜索入口可用、页面端口映射正确、Streamlit 异常 0、主页面脚本错误 0。记录：`logs/runtime_browser_review_20261018.json`，截图：`output/playwright/runtime-ready-20261018.png`。

重新启动后的 Flask 和三个引擎日志检查：Traceback、ERROR 级日志和凭证模式均为 0。Insight 控制台仍有 Streamlit 1.28.1 文件监听器扫描 Transformers 可选模块的告警（340 条路径检查及 764 条 `__path__` 弃用提示），已确认来自开发监听而非研究失败。受控检查表明该版本即使 `fileWatcherType=none` 仍会扫描模块；本轮不引入无效配置、依赖升级或私有 API 补丁来隐藏这些日志。

取消修复后的再次启动已复查同一组页面和健康检查，结果一致；新日志审计保存为 `logs/service_log_audit_cancellation_20261018.json`，不将空 stdout 单独作为服务执行证据。本次取消故障测试使用本机可控 HTTP/HTTPS 服务，没有再次调用付费供应商进行整轮研究；此前真实检索及本轮数据重放的范围仍以上节记录为准。

启动曾在旧 8553 端口报 WinError 10013。已验证该端口当时 IPv4/IPv6、通配/回环绑定均被 Windows 拒绝，监听和排除列表不足以解释原因；改为实际验证过的 8651–8653 后成功。未将此问题归因于代码或某个未经证实的端口保留机制。

配置按服务地址、凭证、模型去重后实际调用三组接口，覆盖 Insight、Media、Query、Report、MindSpider、Forum Host、关键词优化七个角色，均返回成功；日志不输出密钥。Query 使用 `deepseek-reasoner`，其余本地角色使用 `deepseek-v4-pro`。公共 Moonshot 默认与模型保持上游配对，本地网关配置由 `.env` 覆盖。此前 `deepseek-v4-flash` 返回 503，未作为当前可用配置。

Playwright CLI 在先前会话因缓存/daemon 权限降级到已安装包的 Node API；本轮 Chrome 默认系统临时目录启动失败，改用项目 `logs/` 临时目录后通过，未修改系统权限。已有 Tavily 代理 EOF 的本机环境保留进程级 `NO_PROXY` 直连配置。

## 边界

- 模型 HTTP 请求与重试等待支持主动取消；资源清理完成前，新报告仍返回 409，避免同一 Agent 并发写入。客户端断开连接无法证明远端供应商停止计算或计费；进程重启后的自动续跑尚未实现。
- 默认离线套件不执行爬虫 `test/` 下真实 Mongo、Redis、代理供应商、外网或 schema 同步脚本，也不对外部服务永不失败作保证。
- Streamlit 1.28.1 的开发文件监听告警仍可能出现，当前页面和研究入口可用；可选 `torchvision` 模块告警不等于研究模型或溯源链路失败。
- 主张门禁检查引用完整性、文本覆盖与数字单位一致性，不能替代人工核实来源真实性或推断合理性。对缺少明确主张覆盖的图表和标签采取保守删除。
- `scripts/star_history.py` 有一项已有 Windows 符号链接兼容修改，与溯源无关，保留为单独本地提交。

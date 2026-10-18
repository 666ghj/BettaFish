# 报告溯源与引用

BettaFish 的报告溯源链分为 `SourceRecord`、`EvidenceRecord` 与
`ClaimRecord` 三层，定义位于 `common/provenance/`：

- `SourceRecord` 保存原始来源的标题、平台、作者、发布时间和 URL；
- `EvidenceRecord` 保存从原始结果提取的可引用片段、来源 ID 和检索范围；
- `ClaimRecord` 将报告中的事实、指标、推断、预测或建议绑定到证据 ID。

这三层分别回答“来自哪里”“引用了哪段原始内容”和“报告中的哪项结论使用了它”。
Query、Media 和 Insight 引擎会随各自结果保存 `.provenance.json` 审计文件。
网页工作流还会为每次搜索创建独立的 `run_id`，子引擎经本机回调提交本轮结果，报告端只消费该轮的证据，避免使用旧搜索遗留的报告或侧车文件。

## 报告行为

章节生成前会按章节主题选择有限的相关证据，而不是把全文引擎报告当作证据输入。装订阶段会再次执行来源和主张门禁：

- 事实和指标必须有有效证据 ID；结论中的数字及单位还必须能在证据片段或标准化值中找到；
- 推断至少需要两条有效证据才能输出；只有一条时仅在门禁诊断中记为“弱支持”，不进入报告；
- 预测和建议会与事实段落分开标记；
- 论坛讨论文本只作为上下文，不能直接作为证据；
- 图表数值、日期标签、提示框标题等可见内容也必须受到主张覆盖；没有覆盖时会移除。模板中的结构标题使用服务端白名单保留；
- 未找到可追溯证据的内容不会输出，也不会保留生成式结论或占位文本。

HTML 报告会在段落末尾显示引用上标。点击上标可打开原始 URL；悬浮详情包含来源标题、平台、发布时间、证据片段和“引用理由”。`Document IR` 还包含 `provenanceIndex` 和 `claimIndex`，便于审计、重渲染和程序化检查。

Insight 的数据库证据保留表名、记录 ID、查询时间、筛选条件、时间窗口、样本量、聚合方法及行 ID 等血缘信息。若其来源没有公网 URL，页面仍显示这些可审计的内部来源信息，但不能跳转到外部网页。

门禁检查引用完整性、文本覆盖和数字单位一致性；它不能替代对原始来源真实性、时效性或推断是否合理的人工核实。

## 章节断流与取消

报告按章节生成和保存。当前章节遭遇连接中断、超时或可重试的 HTTP 错误时，在 `CHAPTER_JSON_MAX_ATTEMPTS` 预算内重新生成该章，保留此前已完成的章节。网络失败与章节 JSON 校验共用尝试计数，不叠加整份报告重试。鉴权失败、模型不存在和额度不足不会触发网络重试，普通异常也不会仅凭报错文本被当作网络故障。

每次重试都会清空当前章节的半截流和 raw 文件，页面显示“正在重试”；只有通过校验并保存的章节才显示“已完成”。底层模型流在正常结束、异常和取消时都会关闭。

每个报告任务拥有独立的取消令牌。取消会中断该任务正在等待响应头、首字或后续片段的模型 HTTP 请求，也会唤醒重试退避；模板选择、章节生成、结构和图表修复都沿用同一取消作用域，不会因取消而继续重试或切换备用模型。请求使用独占连接和异步任务，响应、客户端及请求线程清理完成后才释放后台 worker，避免影响其他任务或提前复用同一个 Agent。取消终态不会被随后的保存或异常处理覆盖。

本机阻塞服务测试同时检查调用退出和服务端实际观察到连接关闭，使用共同的 2 秒断言期限；这不是任意机器和网络条件下的时延保证。客户端断开连接不能证明远端供应商停止计算或计费。进程重启后自动恢复未完成章节尚未实现。

## 本地运行

Flask 默认使用 `5000`，三个 Streamlit 引擎分别使用 `8501`、`8502`、`8503`。如果 Windows 的排除端口段占用了这些端口，可以在 `.env` 中设置 `INSIGHT_ENGINE_PORT=8551`、`MEDIA_ENGINE_PORT=8552`、`QUERY_ENGINE_PORT=8553`，重启主服务后，进程启动和页面 iframe 会共同使用新配置。

使用系统代理时应让本机 callback 直连。若 Tavily 经代理报 SSL EOF、但直连可用，可在启动进程的 PowerShell 中设置：

```powershell
$env:NO_PROXY = 'api.tavily.com,127.0.0.1,localhost'
python app.py
```

此处设置的是当前进程及其子进程的环境变量；仅把 `NO_PROXY` 写入 `.env` 不会自动改变 HTTP 客户端的代理环境。已有 `NO_PROXY` 项目应合并保留。

## 验证

确认已初始化 MediaCrawler 子模块、Git 在 PATH 中并安装项目依赖后，再安装测试依赖，从仓库根目录运行默认离线测试：

```powershell
conda run -n bettafish python -m pip install -r requirements-test.txt
conda run -n bettafish python -m pytest -q
```

默认范围包括主项目 `tests/`、ReportEngine 的工具测试，以及 MediaCrawler 离线测试桥接。内嵌爬虫与主项目均使用顶层 `tests` 和 `config` 包，桥接使用独立进程隔离导入环境。爬虫的测试兼容修正保存在主仓库 `test_support/mediacrawler-offline-tests.patch`，仅应用到临时测试副本，不修改子模块或生产模块。子测试失败会传递为主测试失败。pytest 夹具与爬虫测试副本默认写到 `logs/`，禁用 pytest cache；部分既有测试仍使用 Python 临时目录。

默认离线范围不包含爬虫 `test/` 下会连接真实 Mongo、Redis、外部服务或同步数据库 schema 的集成脚本。真实供应商与数据库链路需要另行验证，不能由离线测试通过推断。

也可以执行溯源专项回归：

```powershell
conda run -n bettafish python -m pytest -q `
  tests/test_provenance_models.py `
  tests/test_provenance_dedupe.py `
  tests/test_provenance_selector.py `
  tests/test_provenance_claim_gate.py `
  tests/test_provenance_runtime.py `
  tests/test_html_citations.py
```

这组测试覆盖模型兼容、去重、章节选择、主张门禁、运行态隔离、无 URL 外部证据的拒绝，以及从装订后的 IR 到可点击 HTML 引用的完整路径。章节断流、取消、真实渲染与落盘另由 `tests/test_report_chapter_retry.py` 覆盖。

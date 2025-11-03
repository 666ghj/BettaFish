# ReportEngine 404 错误修复

## 问题

验证服务时出现：
```
✗ ReportEngine 返回错误状态码: 404
```

访问 `http://localhost:8502/api/report/status` 返回 HTML 而不是 JSON。

## 原因

BettaFish 的 `app.py` 运行在 **端口 5000**，而不是 8502。

原来的启动方式会启动完整的 BettaFish 应用（包括 Streamlit），这不是我们需要的。

## 解决方案

已创建独立的 `report_engine_server.py`，它：
- ✅ 运行在端口 8502
- ✅ 只启动 ReportEngine API
- ✅ 不启动 Streamlit 界面
- ✅ 使用相同的 ReportEngine 核心逻辑

## 使用新的启动方式

### 关闭旧的服务

如果之前启动了服务，请关闭所有窗口。

### 启动新服务

```powershell
cd d:\myReact\BettaFish\NextJSAdapter
python start_all_services.py
```

这会打开两个新窗口：
1. **QueryEngine Service** (端口 8503)
2. **ReportEngine Service** (端口 8502)

### 验证服务

```powershell
python verify_services.py
```

应该看到：
```
✓ QueryEngine 运行正常
✓ ReportEngine 运行正常

所有服务运行正常！
```

## 手动测试

### 测试 ReportEngine

在浏览器或 PowerShell 中访问：

```powershell
# 方法 1: 浏览器
# 访问 http://localhost:8502/api/report/status

# 方法 2: PowerShell
Invoke-WebRequest -Uri "http://localhost:8502/api/report/status" -UseBasicParsing
```

应该返回 JSON：
```json
{
  "success": true,
  "initialized": true,
  "engines_ready": true
}
```

### 测试 QueryEngine

```powershell
Invoke-WebRequest -Uri "http://localhost:8503/api/status" -UseBasicParsing
```

应该返回 JSON：
```json
{
  "success": true,
  "initialized": true,
  "service": "QueryEngine"
}
```

## 架构变化

### 旧架构（有问题）
```
start_all_services.py
├── QueryEngine (8503) ✓
└── BettaFish app.py (5000) ✗ 端口错误
```

### 新架构（正确）
```
start_all_services.py
├── QueryEngine (8503) ✓
└── ReportEngine (8502) ✓
```

两个服务都是独立的 Flask 应用，专门为 Next.js API 设计。

## 常见问题

### Q1: 旧的 app.py 还能用吗？

可以！`app.py` 是 BettaFish 的完整应用（包括 Streamlit 界面），它运行在端口 5000。

如果您需要使用 BettaFish 的 Streamlit 界面，可以单独运行：
```powershell
cd d:\myReact\BettaFish
python app.py
```

但这与 Next.js 集成无关。

### Q2: 为什么不直接修改 app.py 的端口？

因为：
1. 不破坏原项目结构（设计原则）
2. `app.py` 包含很多 Streamlit 相关的代码，我们不需要
3. 独立的适配服务更清晰、更易维护

### Q3: 两个服务需要不同的配置吗？

不需要！它们都使用 BettaFish 根目录的 `config.py`。

### Q4: 端口冲突怎么办？

如果端口被占用：

```powershell
# 查看占用
netstat -ano | findstr "8502"
netstat -ano | findstr "8503"

# 结束进程
taskkill /PID <进程ID> /F
```

## 验证清单

启动后检查：

- [ ] 两个新窗口都已打开
- [ ] QueryEngine 窗口显示 "✓ 服务启动在端口 8503"
- [ ] ReportEngine 窗口显示 "✓ 服务启动在端口 8502"
- [ ] `verify_services.py` 显示两个服务都正常
- [ ] 浏览器访问返回 JSON 而不是 HTML
- [ ] Next.js 页面显示绿色 ✓

## 更新内容

### 新增文件
- `NextJSAdapter/report_engine_server.py` - ReportEngine 独立服务

### 修改文件
- `NextJSAdapter/start_all_services.py` - 使用新的 ReportEngine 服务

---

**修复时间**: 2025年11月6日  
**状态**: ✅ 已修复

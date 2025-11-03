# NextJSAdapter 测试和验证

## 安装额外依赖

```bash
pip install flask flask-cors colorama requests
```

## 验证服务

运行验证脚本：

```powershell
cd d:\myReact\BettaFish\NextJSAdapter
python verify_services.py
```

## 预期输出

### 成功情况

```
============================================================
Agent 服务验证工具
============================================================

检查 QueryEngine...
URL: http://localhost:8503/api/status
✓ QueryEngine 运行正常
  状态: {
    "success": true,
    "initialized": true,
    "service": "QueryEngine",
    "port": 8503
  }

检查 ReportEngine...
URL: http://localhost:8502/api/report/status
✓ ReportEngine 运行正常
  状态: {
    "success": true,
    "initialized": true,
    "engines_ready": true
  }

============================================================
验证结果:
============================================================
  QueryEngine: ✓ 正常
  ReportEngine: ✓ 正常

所有服务运行正常！

可以启动 Next.js 项目:
  cd d:\myReact\community
  npm run dev

然后访问: http://localhost:3000/report-generation
```

### 失败情况

```
============================================================
Agent 服务验证工具
============================================================

检查 QueryEngine...
URL: http://localhost:8503/api/status
✗ QueryEngine 无法连接
  服务可能未启动

检查 ReportEngine...
URL: http://localhost:8502/api/report/status
✗ ReportEngine 无法连接
  服务可能未启动

============================================================
验证结果:
============================================================
  QueryEngine: ✗ 异常
  ReportEngine: ✗ 异常

部分服务异常，请检查:

1. 确保服务已启动:
   cd d:\myReact\BettaFish\NextJSAdapter
   python start_all_services.py

2. 检查端口占用:
   netstat -ano | findstr "8503"
   netstat -ano | findstr "8502"

3. 查看服务日志中的错误信息
```

## 常见问题

### 返回 HTML 而不是 JSON

**问题**: 
```
✗ QueryEngine 返回了 HTML 而不是 JSON
  这意味着 API 路由未正确配置
```

**原因**: 
- 访问了错误的端点
- 使用了 BettaFish 原有的 app.py 而不是适配层

**解决**: 
确保使用 NextJSAdapter 的启动脚本

### 端口被占用

**问题**: 服务启动失败，提示端口已被占用

**解决**:
```powershell
# 查看占用
netstat -ano | findstr "8503"

# 结束进程（替换 PID）
taskkill /PID 12345 /F
```

### 模块导入错误

**问题**: `ModuleNotFoundError: No module named 'QueryEngine'`

**解决**:
```powershell
cd d:\myReact\BettaFish
pip install -r requirements.txt
```

## 手动测试 API

### 使用 curl

```bash
# QueryEngine 状态
curl http://localhost:8503/api/status

# ReportEngine 状态
curl http://localhost:8502/api/report/status

# QueryEngine 搜索
curl -X POST http://localhost:8503/api/search ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"人工智能\",\"toolName\":\"general_search\"}"
```

### 使用 PowerShell

```powershell
# QueryEngine 状态
Invoke-WebRequest -Uri "http://localhost:8503/api/status" -UseBasicParsing

# ReportEngine 状态
Invoke-WebRequest -Uri "http://localhost:8502/api/report/status" -UseBasicParsing

# QueryEngine 搜索
$body = @{
    query = "人工智能"
    toolName = "general_search"
    kwargs = @{}
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:8503/api/search" `
  -Method POST `
  -Body $body `
  -ContentType "application/json" `
  -UseBasicParsing
```

### 使用浏览器

直接在浏览器中访问：

- QueryEngine: http://localhost:8503/api/status
- ReportEngine: http://localhost:8502/api/report/status

应该看到 JSON 格式的响应。

## 性能测试

### 测试搜索功能

```python
import requests
import time

# 启动搜索
response = requests.post('http://localhost:8503/api/search', json={
    'query': '人工智能',
    'toolName': 'general_search'
})

result = response.json()
task_id = result['task_id']
print(f"任务ID: {task_id}")

# 轮询进度
while True:
    progress = requests.get(f'http://localhost:8503/api/progress/{task_id}')
    data = progress.json()
    task = data['task']
    
    print(f"进度: {task['progress']}% - {task['status']}")
    
    if task['status'] in ['completed', 'error']:
        break
    
    time.sleep(2)

# 获取结果
if task['status'] == 'completed':
    result = requests.get(f'http://localhost:8503/api/result/{task_id}')
    print(result.json())
```

## 集成测试清单

- [ ] QueryEngine 服务启动成功
- [ ] ReportEngine 服务启动成功
- [ ] API 端点返回 JSON 格式
- [ ] 搜索功能正常工作
- [ ] 进度追踪正常
- [ ] 报告生成正常
- [ ] Next.js API 代理正常
- [ ] 前端界面显示正常

---

**提示**: 在启动 Next.js 项目前，务必先验证两个 Agent 服务都正常运行！

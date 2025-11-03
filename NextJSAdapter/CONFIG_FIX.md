# QueryEngine 配置问题快速修复

## 问题

启动 QueryEngine 时出现：
```
QueryEngine 初始化失败: 未找到配置文件，请创建 config.py。
```

## 原因

QueryEngine 需要 `config.py` 配置文件来获取 API Key 和其他配置。

## 解决方案

### 步骤 1: 检查配置

运行配置检查工具：

```powershell
cd d:\myReact\BettaFish\NextJSAdapter
python check_config.py
```

### 步骤 2: 创建配置文件

如果没有 `config.py`，在 **BettaFish 根目录**（不是 NextJSAdapter）创建：

```powershell
cd d:\myReact\BettaFish
```

#### 方法 A: 使用模板（推荐）

```powershell
# 复制模板
copy config.py.template config.py

# 用编辑器打开并填入您的 API Key
notepad config.py
```

#### 方法 B: 手动创建

创建 `d:\myReact\BettaFish\config.py`，内容如下：

```python
# BettaFish 配置文件

# QueryEngine LLM 配置
QUERY_ENGINE_API_KEY = "sk-your-api-key-here"
QUERY_ENGINE_BASE_URL = "https://api.openai.com/v1"
QUERY_ENGINE_MODEL_NAME = "gpt-4"

# Tavily 搜索 API（必需）
TAVILY_API_KEY = "tvly-your-api-key-here"

# ReportEngine LLM 配置
REPORT_ENGINE_API_KEY = "sk-your-api-key-here"
REPORT_ENGINE_BASE_URL = "https://api.openai.com/v1"
REPORT_ENGINE_MODEL_NAME = "gpt-4"
```

### 步骤 3: 获取 API Key

#### OpenAI API Key
1. 访问 https://platform.openai.com/api-keys
2. 创建新的 API Key
3. 复制并保存到 `config.py`

#### Tavily API Key（搜索功能必需）
1. 访问 https://tavily.com/
2. 注册账号并登录
3. 获取 API Key
4. 复制并保存到 `config.py`

### 步骤 4: 验证配置

```powershell
cd d:\myReact\BettaFish\NextJSAdapter
python check_config.py
```

应该看到：
```
✓ config.py 存在
✓ QUERY_ENGINE_API_KEY: 已配置
✓ QUERY_ENGINE_MODEL_NAME: 已配置
✓ TAVILY_API_KEY: 已配置
```

### 步骤 5: 重新启动服务

```powershell
cd d:\myReact\BettaFish\NextJSAdapter
python start_all_services.py
```

这会同时启动两个新窗口：
1. **QueryEngine 窗口** - 应该看到：
   ```
   正在初始化 QueryEngine...
   当前工作目录: D:\myReact\BettaFish
   检查配置文件...
     ✓ 找到配置文件: config.py
   正在加载配置...
   正在初始化 DeepSearchAgent...
   ✓ QueryEngine 初始化成功
   ✓ 服务启动在端口 8503
   ```

2. **ReportEngine 窗口** - 应该看到：
   ```
   正在初始化 ReportEngine...
   ✓ ReportEngine Blueprint 已注册
   ✓ ReportEngine 初始化成功
   ✓ 服务启动在端口 8502
   ```

## 常见问题

### Q1: 如果使用的是其他 LLM 服务（如 Claude、通义千问等）？

修改 `config.py` 中的 `BASE_URL` 和 `MODEL_NAME`：

```python
# 示例：使用 Claude
QUERY_ENGINE_API_KEY = "sk-ant-your-key"
QUERY_ENGINE_BASE_URL = "https://api.anthropic.com/v1"
QUERY_ENGINE_MODEL_NAME = "claude-3-sonnet-20240229"

# 示例：使用国内中转服务
QUERY_ENGINE_API_KEY = "your-key"
QUERY_ENGINE_BASE_URL = "https://your-proxy-service.com/v1"
QUERY_ENGINE_MODEL_NAME = "gpt-4"
```

### Q2: 没有 Tavily API Key 怎么办？

Tavily 是必需的，因为它用于网络搜索。但您可以：

1. **使用免费版**: Tavily 提供免费套餐
2. **联系管理员**: 如果是团队项目，询问是否有共享 Key

### Q3: API Key 填入后仍然失败？

检查：
1. API Key 格式是否正确（没有多余空格）
2. API Key 是否有配额
3. 网络是否能访问 API 服务
4. 配置文件编码是否为 UTF-8

### Q4: 配置文件在哪个目录？

**重要**: 配置文件必须在 **BettaFish 根目录**：

```
d:\myReact\BettaFish\
├── config.py          ✓ 在这里
├── NextJSAdapter/
│   └── ...
└── ...
```

**不是**在这里：
```
d:\myReact\BettaFish\NextJSAdapter\
└── config.py          ✗ 错误位置
```

## 验证成功

当配置正确时，您应该看到：

1. **配置检查通过**:
   ```powershell
   python check_config.py
   # 输出：✓ 找到配置文件: config.py
   ```

2. **QueryEngine 启动成功**:
   ```
   ✓ QueryEngine 初始化成功
   ✓ 服务启动在端口 8503
   ```

3. **服务验证通过**:
   ```powershell
   python verify_services.py
   # 输出：✓ QueryEngine 运行正常
   ```

4. **Next.js 页面显示绿色 ✓**

## 需要帮助？

如果仍然有问题：

1. 查看完整错误信息
2. 运行 `python check_config.py` 获取诊断
3. 检查 `d:\myReact\BettaFish\config.py` 文件是否存在
4. 确认 API Key 格式正确

---

**更新时间**: 2025年11月6日

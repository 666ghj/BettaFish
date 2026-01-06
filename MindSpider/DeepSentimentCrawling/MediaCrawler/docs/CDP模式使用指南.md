# CDP模式使用指南

## 概述

CDP（Chrome DevTools Protocol）模式是一种高级的反检测爬虫技术，通过控制用户现有的Chrome/Edge浏览器来进行网页爬取。与传统的Playwright自动化相比，CDP模式具有以下优势：

### 🎯 主要优势

1. **真实浏览器环境**: 使用用户实际安装的浏览器，包含所有扩展、插件和个人设置
2. **更好的反检测能力**: 浏览器指纹更加真实，难以被网站检测为自动化工具
3. **保留用户状态**: 自动继承用户的登录状态、Cookie和浏览历史
4. **扩展支持**: 可以利用用户安装的广告拦截器、代理扩展等工具
5. **更自然的行为**: 浏览器行为模式更接近真实用户

## 快速开始

### 1. 启用CDP模式

CDP模式支持两种方式：
- **本地浏览器模式**: 使用本地安装的Chrome/Edge浏览器
- **wuying-agentbay-sdk模式**: 使用远程浏览器session（需要API Key）

#### 方式一：本地浏览器模式

在 `config/base_config.py` 中设置：

```python
# 启用CDP模式
ENABLE_CDP_MODE = True

# 使用本地浏览器（默认）
ENABLE_WUYING_CDP_MODE = False

# CDP调试端口（可选，默认9222）
CDP_DEBUG_PORT = 9222

# 是否在无头模式下运行（建议设为False以获得最佳反检测效果）
CDP_HEADLESS = False

# 程序结束时是否自动关闭浏览器
AUTO_CLOSE_BROWSER = True
```

#### 方式二：wuying-agentbay-sdk模式

1. **安装 wuying-agentbay-sdk**:
```bash
# 直接安装 PyPI 版本（推荐）
pip install wuying-agentbay-sdk
```
注意：代码已自动支持同步和异步两种版本的 SDK，会自动适配。

2. **配置API Key**:
```python
# 在 config/base_config.py 中设置
ENABLE_CDP_MODE = True
ENABLE_WUYING_CDP_MODE = True
AGENTBAY_API_KEY = "your_api_key_here"  # 或设置环境变量 AGENTBAY_API_KEY
AGENTBAY_IMAGE_ID = "browser_latest"  # 可选，默认为 browser_latest

# 无头模式配置（agentbay 模式下也支持）
CDP_HEADLESS = False  # 建议设为 False 以获得最佳反检测效果
```

或者使用环境变量：
```bash
export AGENTBAY_API_KEY="your_api_key_here"
```

3. **启用配置**:
```python
ENABLE_CDP_MODE = True
ENABLE_WUYING_CDP_MODE = True
```

### 2. 运行测试

```bash
# 运行CDP功能测试
python examples/cdp_example.py

# 运行小红书爬虫（CDP模式）
python main.py
```

## 配置选项详解

### 基础配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `ENABLE_CDP_MODE` | bool | False | 是否启用CDP模式 |
| `ENABLE_WUYING_CDP_MODE` | bool | False | 是否使用 wuying-agentbay-sdk 模式 |
| `CDP_DEBUG_PORT` | int | 9222 | CDP调试端口（仅本地浏览器模式） |
| `CDP_HEADLESS` | bool | False | CDP模式下的无头模式（本地浏览器模式和 agentbay 模式均支持） |
| `AUTO_CLOSE_BROWSER` | bool | True | 程序结束时是否关闭浏览器 |

### wuying-agentbay-sdk 配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `AGENTBAY_API_KEY` | str | "" | wuying-agentbay-sdk 的 API Key |
| `AGENTBAY_IMAGE_ID` | str | "browser_latest" | wuying-agentbay-sdk 的镜像 ID |

### 高级配置（仅本地浏览器模式）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `CUSTOM_BROWSER_PATH` | str | "" | 自定义浏览器路径 |
| `BROWSER_LAUNCH_TIMEOUT` | int | 30 | 浏览器启动超时时间（秒） |

### 自定义浏览器路径

如果系统自动检测失败，可以手动指定浏览器路径：

```python
# Windows示例
CUSTOM_BROWSER_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# macOS示例  
CUSTOM_BROWSER_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Linux示例
CUSTOM_BROWSER_PATH = "/usr/bin/google-chrome"
```

## 支持的浏览器

### Windows
- Google Chrome (稳定版、Beta、Dev、Canary)
- Microsoft Edge (稳定版、Beta、Dev、Canary)

### macOS
- Google Chrome (稳定版、Beta、Dev、Canary)
- Microsoft Edge (稳定版、Beta、Dev、Canary)

### Linux
- Google Chrome / Chromium
- Microsoft Edge

## 使用示例

### 基本使用

```python
import asyncio
from playwright.async_api import async_playwright
from tools.cdp_browser import CDPBrowserManager

async def main():
    cdp_manager = CDPBrowserManager()
    
    async with async_playwright() as playwright:
        # 启动CDP浏览器
        browser_context = await cdp_manager.launch_and_connect(
            playwright=playwright,
            user_agent="自定义User-Agent",
            headless=False
        )
        
        # 创建页面并访问网站
        page = await browser_context.new_page()
        await page.goto("https://example.com")
        
        # 执行爬取操作...
        
        # 清理资源
        await cdp_manager.cleanup()

asyncio.run(main())
```

### 在爬虫中使用

CDP模式已集成到所有平台爬虫中，只需启用配置即可：

```python
# 在config/base_config.py中
ENABLE_CDP_MODE = True

# 然后正常运行爬虫
python main.py
```

## 故障排除

### 常见问题

#### 1. wuying-agentbay-sdk 未安装
**错误**: `wuying-agentbay-sdk 未安装，将使用本地浏览器模式`

**解决方案**:
- 安装 wuying-agentbay-sdk: `pip install wuying-agentbay-sdk`
- 或者设置 `ENABLE_WUYING_CDP_MODE = False` 使用本地浏览器模式

#### 2. wuying-agentbay-sdk API Key 未设置
**错误**: `使用 wuying-agentbay-sdk 需要设置 AGENTBAY_API_KEY 配置项`

**解决方案**:
- 在配置文件中设置 `AGENTBAY_API_KEY = "your_api_key"`
- 或设置环境变量 `export AGENTBAY_API_KEY="your_api_key"`
- 或在 `.env` 文件中设置 `AGENTBAY_API_KEY=your_api_key`

#### 3. 浏览器检测失败（仅本地浏览器模式）
**错误**: `未找到可用的浏览器`

**解决方案**:
- 确保已安装Chrome或Edge浏览器
- 检查浏览器是否在标准路径下
- 使用`CUSTOM_BROWSER_PATH`指定浏览器路径

#### 4. 端口被占用（仅本地浏览器模式）
**错误**: `无法找到可用的端口`

**解决方案**:
- 关闭其他使用调试端口的程序
- 修改`CDP_DEBUG_PORT`为其他端口
- 系统会自动尝试下一个可用端口

#### 5. 浏览器启动超时（仅本地浏览器模式）
**错误**: `浏览器在30秒内未能启动`

**解决方案**:
- 增加`BROWSER_LAUNCH_TIMEOUT`值
- 检查系统资源是否充足
- 尝试关闭其他占用资源的程序

#### 6. CDP连接失败
**错误**: `CDP连接失败`

**解决方案**:
- 检查防火墙设置
- 确保localhost访问正常
- 尝试重启浏览器

### 调试技巧

#### 1. 启用详细日志
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### 2. 手动测试CDP连接
```bash
# 手动启动Chrome
chrome --remote-debugging-port=9222

# 访问调试页面
curl http://localhost:9222/json
```

#### 3. 检查浏览器进程
```bash
# Windows
tasklist | findstr chrome

# macOS/Linux  
ps aux | grep chrome
```

## 最佳实践

### 1. 反检测优化
- 保持`CDP_HEADLESS = False`以获得最佳反检测效果（本地浏览器模式和 agentbay 模式均适用）
- 在 agentbay 模式下，headless 模式通过 `cmd_args` 参数控制，代码会自动处理
- 使用真实的User-Agent字符串
- 避免过于频繁的请求

### 2. 性能优化
- 合理设置`AUTO_CLOSE_BROWSER`
- 复用浏览器实例而不是频繁重启
- 监控内存使用情况

### 3. 安全考虑
- 不要在生产环境中保存敏感Cookie
- 定期清理浏览器数据
- 注意用户隐私保护

### 4. 兼容性
- 测试不同浏览器版本的兼容性
- 准备回退方案（标准Playwright模式）
- 监控目标网站的反爬策略变化

## 技术原理

CDP模式的工作原理：

### 本地浏览器模式

1. **浏览器检测**: 自动扫描系统中的Chrome/Edge安装路径
2. **进程启动**: 使用`--remote-debugging-port`参数启动浏览器
3. **CDP连接**: 通过WebSocket连接到浏览器的调试接口
4. **Playwright集成**: 使用`connectOverCDP`方法接管浏览器控制
5. **上下文管理**: 创建或复用浏览器上下文进行操作

### wuying-agentbay-sdk 模式

1. **Session创建**: 通过 AgentBay SDK 创建远程浏览器 session
2. **浏览器初始化**: 使用 `BrowserOption` 配置浏览器参数（包括 headless 模式）
3. **CDP端点获取**: 从远程 session 获取 CDP WebSocket 端点 URL
4. **Playwright集成**: 使用`connectOverCDP`方法连接到远程浏览器
5. **上下文管理**: 创建或复用浏览器上下文进行操作
6. **资源清理**: 程序结束时自动删除远程 session

**Headless 模式控制**: 在 agentbay 模式下，通过 `BrowserOption` 的 `cmd_args` 参数传递 `--headless=new` 来控制无头模式，代码会根据 `CDP_HEADLESS` 配置自动处理。

这种方式绕过了传统WebDriver的检测机制，提供了更加隐蔽的自动化能力。

## 更新日志

### v1.1.0
- 新增 wuying-agentbay-sdk 支持
- 支持使用远程浏览器 session
- 自动回退到本地浏览器模式（如果 SDK 未安装）

### v1.0.0
- 初始版本发布
- 支持Windows和macOS的Chrome/Edge检测
- 集成到所有平台爬虫
- 提供完整的配置选项和错误处理

## 贡献

欢迎提交Issue和Pull Request来改进CDP模式功能。

## 许可证

本功能遵循项目的整体许可证条款，仅供学习和研究使用。

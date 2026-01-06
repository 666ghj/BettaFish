# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。


import os
import asyncio
import socket
import httpx
from typing import Optional, Dict, Any
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from playwright.async_api import Browser, BrowserContext, Playwright

import config
from tools.browser_launcher import BrowserLauncher
from tools import utils

# 计算 .env 优先级：优先当前工作目录，其次项目根目录（BettaFish）
# 复用 MindSpider/config.py 的配置加载逻辑
PROJECT_ROOT: Path = Path(__file__).resolve().parents[4]  # 从 MediaCrawler/tools/cdp_browser.py 向上4级到 BettaFish
CWD_ENV: Path = Path.cwd() / ".env"
ENV_FILE: str = str(CWD_ENV if CWD_ENV.exists() else (PROJECT_ROOT / ".env"))

class Settings(BaseSettings):
    """AgentBay 配置，优先从环境变量和.env加载，复用 MindSpider 的统一配置逻辑"""
    AGENTBAY_API_KEY: Optional[str] = Field(None, description="AgentBay API密钥，也可通过环境变量AGENTBAY_API_KEY设置")
    AGENTBAY_IMAGE_ID: Optional[str] = Field("browser_latest", description="Wuying镜像ID，可通过环境变量AGENTBAY_IMAGE_ID设置")

    class Config:
        env_file = ENV_FILE
        env_prefix = ""
        case_sensitive = False
        extra = "allow"

# 创建 settings 实例
settings = Settings()

# 注意：PyPI 安装的版本（0.12.0）只提供同步版本，没有异步版本
# 所有调用都需要通过 asyncio.run_in_executor 适配到异步环境


class CDPBrowserManager:
    """
    CDP浏览器管理器，负责启动和管理通过CDP连接的浏览器
    """

    # wuying-agentbay-sdk 相关类属性（所有实例共享）
    # 缓存导入结果，None 表示未尝试过，True/False 表示导入成功/失败
    _agentbay_import_result: Optional[bool] = None

    def __init__(self):
        self.launcher = BrowserLauncher()
        self.browser: Optional[Browser] = None
        self.browser_context: Optional[BrowserContext] = None
        self.debug_port: Optional[int] = None
        # wuying-agentbay-sdk 相关实例属性
        self.agentbay: Optional[Any] = None
        self.agentbay_session: Optional[Any] = None

    @classmethod
    def _try_import_agentbay(cls):
        """
        尝试导入 agentbay SDK（同步版本）

        注意：PyPI 安装的版本只提供同步版本（AgentBay），没有异步版本（AsyncAgentBay）
        所有同步调用都需要通过 asyncio.run_in_executor 适配到异步环境

        BrowserOption 类在 agentbay 模块中定义（直接从 agentbay 导入）

        无论成功还是失败，都只执行一次导入检查，后续调用直接返回缓存的结果。

        Returns:
            bool: 导入成功返回 True，失败返回 False
        """
        # 如果已经尝试过导入，直接返回缓存的结果
        if cls._agentbay_import_result is not None:
            return cls._agentbay_import_result

        # 第一次尝试导入
        try:
            from agentbay import AgentBay, CreateSessionParams
            cls._agentbay_import_result = True
            return True
        except ImportError as e:
            cls._agentbay_import_result = False
            # 检查是否已安装但导入失败，输出警告
            try:
                import pkg_resources
                dist = pkg_resources.get_distribution('wuying-agentbay-sdk')
                error_msg = (
                    f"[CDPBrowserManager] wuying-agentbay-sdk 已安装 (版本: {dist.version})，"
                    f"但无法导入必要的类。错误: {e}。"
                    f"请检查 SDK 文档或尝试重新安装: "
                    f"pip uninstall -y wuying-agentbay-sdk && pip install wuying-agentbay-sdk"
                )
                utils.logger.warning(error_msg)
            except Exception:
                # 包未安装，不输出警告（在需要时会提示）
                pass
            return False

    async def launch_and_connect(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict] = None,
        user_agent: Optional[str] = None,
        headless: bool = False,
    ) -> BrowserContext:
        """
        启动浏览器并通过CDP连接
        支持两种模式：
        1. 使用 wuying-agentbay-sdk 创建 session 并连接
        2. 使用本地浏览器通过 CDP 连接
        """
        try:
            # 检查是否使用 wuying-agentbay-sdk
            if config.ENABLE_WUYING_CDP_MODE:
                # 只有在配置使能时才尝试导入 SDK
                if self.__class__._try_import_agentbay():
                    utils.logger.info("[CDPBrowserManager] 使用 wuying-agentbay-sdk 模式")
                    return await self._launch_with_wuying(playwright, playwright_proxy, user_agent, headless)
                else:
                    utils.logger.warning(
                        "[CDPBrowserManager] 配置了使用 wuying-agentbay-sdk 但 SDK 未安装，"
                        "回退到本地浏览器模式"
                    )

            utils.logger.info("[CDPBrowserManager] 使用本地浏览器模式")
            return await self._launch_with_local_browser(playwright, playwright_proxy, user_agent, headless)

        except Exception as e:
            utils.logger.error(f"[CDPBrowserManager] CDP浏览器启动失败: {e}")
            await self.cleanup()
            raise

    async def _launch_with_wuying(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict] = None,
        user_agent: Optional[str] = None,
        headless: bool = False,
    ) -> BrowserContext:
        """
        使用 wuying-agentbay-sdk 创建 session 并连接浏览器
        支持异步和同步两种版本的 SDK
        """
        try:
            # 1. 初始化 AgentBay
            # 从 settings 读取 API Key（BaseSettings 已自动从环境变量和 .env 文件加载）
            api_key = settings.AGENTBAY_API_KEY

            if not api_key:
                raise ValueError(
                    "使用 wuying-agentbay-sdk 需要设置 AGENTBAY_API_KEY 配置项，"
                    "可在 .env 文件中设置 AGENTBAY_API_KEY 环境变量"
                )

            # 导入并使用 AgentBay（同步版本，通过 asyncio.run_in_executor 适配）
            # 如果导入失败，会抛出 ImportError，由调用者处理
            from agentbay import AgentBay
            self.agentbay = AgentBay(api_key=api_key)
            utils.logger.info("[CDPBrowserManager] AgentBay (同步版本) 初始化成功")

            # 2. 创建 session
            # 从 settings 读取镜像 ID（BaseSettings 已自动从环境变量和 .env 文件加载，默认值为 "browser_latest"）
            from agentbay import CreateSessionParams
            image_id = settings.AGENTBAY_IMAGE_ID
            params = CreateSessionParams(image_id=image_id)

            # 同步版本需要在线程池中运行
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.agentbay.create, params)

            self.agentbay_session = result.session
            utils.logger.info(f"[CDPBrowserManager] Session 创建成功: {self.agentbay_session.session_id}")

            # 3. 初始化浏览器
            # 根据 SDK 实现，browser.initialize() 需要一个 option 参数
            # 通过检查方法签名和 SDK 模块来确定正确的 option 类型
            # 注意：BrowserOption 没有直接的 headless 参数，需要通过 cmd_args 传递命令行参数
            try:
                # 检查是否有 initialize 方法
                if hasattr(self.agentbay_session.browser, 'initialize'):
                    # 创建 browser option
                    # 根据 headless 参数设置 cmd_args
                    # 如果 headless=True，传递 --headless=new；如果 headless=False，不传递 headless 参数（默认非 headless）
                    browser_option = None
                    try:
                        from agentbay import BrowserOption
                        cmd_args = []
                        if headless:
                            # 启用 headless 模式
                            cmd_args.append("--headless=new")
                            utils.logger.info(f"[CDPBrowserManager] 使用 BrowserOption 创建浏览器选项（headless 模式）")
                        else:
                            # 非 headless 模式，不传递 headless 参数（默认就是非 headless）
                            utils.logger.info(f"[CDPBrowserManager] 使用 BrowserOption 创建浏览器选项（非 headless 模式）")

                        browser_option = BrowserOption(cmd_args=cmd_args if cmd_args else None)
                    except (ImportError, Exception) as e:
                        # BrowserOption 类不存在或创建失败，传递 None 让 SDK 创建默认实例
                        utils.logger.debug(f"[CDPBrowserManager] 使用默认浏览器选项: {e}")
                        browser_option = None

                    utils.logger.info(f"[CDPBrowserManager] 准备初始化浏览器，option: {browser_option}")

                    # 同步版本需要在线程池中运行
                    loop = asyncio.get_event_loop()
                    try:
                        success = await loop.run_in_executor(
                            None,
                            self.agentbay_session.browser.initialize,
                            browser_option
                        )
                    except (TypeError, Exception) as e:
                        utils.logger.warning(f"[CDPBrowserManager] 浏览器初始化失败: {e}")
                        # 如果失败，尝试检查是否需要特定类型的对象
                        import inspect
                        try:
                            sig = inspect.signature(self.agentbay_session.browser.initialize)
                            param_info = sig.parameters.get('option', None)
                            if param_info:
                                param_type = param_info.annotation
                                if param_type != inspect.Parameter.empty:
                                    utils.logger.warning(f"[CDPBrowserManager] 需要的 option 类型: {param_type}")
                        except:
                            pass
                        success = False
                    if success:
                        utils.logger.info("[CDPBrowserManager] 浏览器初始化成功")
                    else:
                        utils.logger.warning("[CDPBrowserManager] 浏览器初始化返回 False，尝试继续获取 CDP URL")
                else:
                    utils.logger.info("[CDPBrowserManager] 浏览器对象没有 initialize 方法，跳过初始化步骤")
            except Exception as e:
                utils.logger.warning(f"[CDPBrowserManager] 浏览器初始化异常: {e}")
                # 继续执行，尝试获取 CDP URL

            # 4. 获取 CDP 链接
            # 如果浏览器未初始化，尝试直接获取 CDP URL（某些 SDK 版本可能不需要初始化）
            cdp_url = None
            try:
                # 同步版本需要在线程池中运行
                loop = asyncio.get_event_loop()
                cdp_url = await loop.run_in_executor(
                    None,
                    self.agentbay_session.browser.get_endpoint_url
                )
                utils.logger.info(f"[CDPBrowserManager] 获取到 CDP URL: {cdp_url[:100]}...")
            except Exception as e:
                error_msg = str(e).lower()
                if "not initialized" in error_msg or "cannot access" in error_msg:
                    # 浏览器未初始化，需要先初始化
                    utils.logger.error(f"[CDPBrowserManager] 无法获取 CDP URL，浏览器未初始化: {e}")
                    raise RuntimeError(
                        f"浏览器未初始化，无法获取 CDP URL。"
                        f"请检查 browser.initialize() 调用是否成功。"
                        f"错误: {e}"
                    )
                else:
                    raise

            # 5. 等待浏览器完全就绪（参考其他语言的实现，需要等待一段时间）
            # 从测试代码看，通常需要等待 5 秒左右
            utils.logger.info("[CDPBrowserManager] 等待浏览器完全就绪...")
            await asyncio.sleep(5)  # 等待浏览器完全启动

            # 6. 通过 CDP 连接，添加重试机制
            max_retries = 5  # 增加重试次数
            retry_delay = 3  # 初始延迟3秒
            last_error = None

            for attempt in range(max_retries):
                try:
                    utils.logger.info(f"[CDPBrowserManager] 尝试连接 CDP (第 {attempt + 1}/{max_retries} 次)...")
                    # 使用 timeout 参数（30秒超时）
                    self.browser = await playwright.chromium.connect_over_cdp(
                        cdp_url,
                        timeout=30000
                    )

                    if self.browser.is_connected():
                        utils.logger.info("[CDPBrowserManager] 成功通过 wuying-agentbay-sdk 连接到浏览器")
                        break
                    else:
                        raise RuntimeError("CDP连接失败：浏览器未连接")

                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()
                    # 检查是否是可重试的错误
                    retryable_keywords = ["ebadf", "connection", "timeout", "network", "websocket", "connect", "bad file"]
                    is_retryable = any(keyword in error_msg for keyword in retryable_keywords)

                    if attempt < max_retries - 1 and is_retryable:
                        utils.logger.warning(
                            f"[CDPBrowserManager] CDP连接失败 (可重试): {str(e)[:200]}，"
                            f"{retry_delay}秒后重试..."
                        )
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 1.5, 10)  # 指数退避，最多10秒
                    else:
                        utils.logger.error(f"[CDPBrowserManager] CDP连接失败: {e}")
                        if attempt == max_retries - 1:
                            # 最后一次失败，提供更详细的错误信息
                            raise RuntimeError(
                                f"CDP连接失败，已重试 {max_retries} 次。"
                                f"这可能是因为网络问题或浏览器未完全就绪。"
                                f"最后错误: {last_error}"
                            )
                        raise
            else:
                # 所有重试都失败了
                raise RuntimeError(
                    f"CDP连接失败，已重试 {max_retries} 次。"
                    f"这可能是因为网络问题或浏览器未完全就绪。"
                    f"最后错误: {last_error}"
                )

            # 6. 创建或获取浏览器上下文
            browser_context = await self._create_browser_context(
                playwright_proxy, user_agent
            )

            self.browser_context = browser_context
            return browser_context

        except Exception as e:
            utils.logger.error(f"[CDPBrowserManager] wuying-agentbay-sdk 模式启动失败: {e}")
            raise

    async def _launch_with_local_browser(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict] = None,
        user_agent: Optional[str] = None,
        headless: bool = False,
    ) -> BrowserContext:
        """
        使用本地浏览器通过 CDP 连接
        """
        # 1. 检测浏览器路径
        browser_path = await self._get_browser_path()

        # 2. 获取可用端口
        self.debug_port = self.launcher.find_available_port(config.CDP_DEBUG_PORT)

        # 3. 启动浏览器
        await self._launch_browser(browser_path, headless)

        # 4. 通过CDP连接
        await self._connect_via_cdp(playwright)

        # 5. 创建浏览器上下文
        browser_context = await self._create_browser_context(
            playwright_proxy, user_agent
        )

        self.browser_context = browser_context
        return browser_context

    async def _get_browser_path(self) -> str:
        """
        获取浏览器路径
        """
        # 优先使用用户自定义路径
        if config.CUSTOM_BROWSER_PATH and os.path.isfile(config.CUSTOM_BROWSER_PATH):
            utils.logger.info(
                f"[CDPBrowserManager] 使用自定义浏览器路径: {config.CUSTOM_BROWSER_PATH}"
            )
            return config.CUSTOM_BROWSER_PATH

        # 自动检测浏览器路径
        browser_paths = self.launcher.detect_browser_paths()

        if not browser_paths:
            raise RuntimeError(
                "未找到可用的浏览器。请确保已安装Chrome或Edge浏览器，"
                "或在配置文件中设置CUSTOM_BROWSER_PATH指定浏览器路径。"
            )

        browser_path = browser_paths[0]  # 使用第一个找到的浏览器
        browser_name, browser_version = self.launcher.get_browser_info(browser_path)

        utils.logger.info(
            f"[CDPBrowserManager] 检测到浏览器: {browser_name} ({browser_version})"
        )
        utils.logger.info(f"[CDPBrowserManager] 浏览器路径: {browser_path}")

        return browser_path

    async def _test_cdp_connection(self, debug_port: int) -> bool:
        """
        测试CDP连接是否可用
        """
        try:
            # 简单的socket连接测试
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                result = s.connect_ex(("localhost", debug_port))
                if result == 0:
                    utils.logger.info(
                        f"[CDPBrowserManager] CDP端口 {debug_port} 可访问"
                    )
                    return True
                else:
                    utils.logger.warning(
                        f"[CDPBrowserManager] CDP端口 {debug_port} 不可访问"
                    )
                    return False
        except Exception as e:
            utils.logger.warning(f"[CDPBrowserManager] CDP连接测试失败: {e}")
            return False

    async def _launch_browser(self, browser_path: str, headless: bool):
        """
        启动浏览器进程
        """
        # 设置用户数据目录（如果启用了保存登录状态）
        user_data_dir = None
        if config.SAVE_LOGIN_STATE:
            user_data_dir = os.path.join(
                os.getcwd(),
                "browser_data",
                f"cdp_{config.USER_DATA_DIR % config.PLATFORM}",
            )
            os.makedirs(user_data_dir, exist_ok=True)
            utils.logger.info(f"[CDPBrowserManager] 用户数据目录: {user_data_dir}")

        # 启动浏览器
        self.launcher.browser_process = self.launcher.launch_browser(
            browser_path=browser_path,
            debug_port=self.debug_port,
            headless=headless,
            user_data_dir=user_data_dir,
        )

        # 等待浏览器准备就绪
        if not self.launcher.wait_for_browser_ready(
            self.debug_port, config.BROWSER_LAUNCH_TIMEOUT
        ):
            raise RuntimeError(f"浏览器在 {config.BROWSER_LAUNCH_TIMEOUT} 秒内未能启动")

        # 额外等待一秒让CDP服务完全启动
        await asyncio.sleep(1)

        # 测试CDP连接
        if not await self._test_cdp_connection(self.debug_port):
            utils.logger.warning(
                "[CDPBrowserManager] CDP连接测试失败，但将继续尝试连接"
            )

    async def _get_browser_websocket_url(self, debug_port: int) -> str:
        """
        获取浏览器的WebSocket连接URL
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://localhost:{debug_port}/json/version", timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    ws_url = data.get("webSocketDebuggerUrl")
                    if ws_url:
                        utils.logger.info(
                            f"[CDPBrowserManager] 获取到浏览器WebSocket URL: {ws_url}"
                        )
                        return ws_url
                    else:
                        raise RuntimeError("未找到webSocketDebuggerUrl")
                else:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
        except Exception as e:
            utils.logger.error(f"[CDPBrowserManager] 获取WebSocket URL失败: {e}")
            raise

    async def _connect_via_cdp(self, playwright: Playwright):
        """
        通过CDP连接到浏览器
        """
        try:
            # 获取正确的WebSocket URL
            ws_url = await self._get_browser_websocket_url(self.debug_port)
            utils.logger.info(f"[CDPBrowserManager] 正在通过CDP连接到浏览器: {ws_url}")

            # 使用Playwright的connectOverCDP方法连接
            self.browser = await playwright.chromium.connect_over_cdp(ws_url)

            if self.browser.is_connected():
                utils.logger.info("[CDPBrowserManager] 成功连接到浏览器")
                utils.logger.info(
                    f"[CDPBrowserManager] 浏览器上下文数量: {len(self.browser.contexts)}"
                )
            else:
                raise RuntimeError("CDP连接失败")

        except Exception as e:
            utils.logger.error(f"[CDPBrowserManager] CDP连接失败: {e}")
            raise

    async def _create_browser_context(
        self, playwright_proxy: Optional[Dict] = None, user_agent: Optional[str] = None
    ) -> BrowserContext:
        """
        创建或获取浏览器上下文
        """
        if not self.browser:
            raise RuntimeError("浏览器未连接")

        # 获取现有上下文或创建新的上下文
        contexts = self.browser.contexts

        if contexts:
            # 使用现有的第一个上下文
            browser_context = contexts[0]
            utils.logger.info("[CDPBrowserManager] 使用现有的浏览器上下文")
        else:
            # 创建新的上下文
            context_options = {
                "viewport": {"width": 1920, "height": 1080},
                "accept_downloads": True,
            }

            # 设置用户代理
            if user_agent:
                context_options["user_agent"] = user_agent
                utils.logger.info(f"[CDPBrowserManager] 设置用户代理: {user_agent}")

            # 注意：CDP模式下代理设置可能不生效，因为浏览器已经启动
            if playwright_proxy:
                utils.logger.warning(
                    "[CDPBrowserManager] 警告: CDP模式下代理设置可能不生效，"
                    "建议在浏览器启动前配置系统代理或浏览器代理扩展"
                )

            browser_context = await self.browser.new_context(**context_options)
            utils.logger.info("[CDPBrowserManager] 创建新的浏览器上下文")

        return browser_context

    async def add_stealth_script(self, script_path: str = "libs/stealth.min.js"):
        """
        添加反检测脚本
        """
        if self.browser_context and os.path.exists(script_path):
            try:
                await self.browser_context.add_init_script(path=script_path)
                utils.logger.info(
                    f"[CDPBrowserManager] 已添加反检测脚本: {script_path}"
                )
            except Exception as e:
                utils.logger.warning(f"[CDPBrowserManager] 添加反检测脚本失败: {e}")

    async def add_cookies(self, cookies: list):
        """
        添加Cookie
        """
        if self.browser_context:
            try:
                await self.browser_context.add_cookies(cookies)
                utils.logger.info(f"[CDPBrowserManager] 已添加 {len(cookies)} 个Cookie")
            except Exception as e:
                utils.logger.warning(f"[CDPBrowserManager] 添加Cookie失败: {e}")

    async def get_cookies(self) -> list:
        """
        获取当前Cookie
        """
        if self.browser_context:
            try:
                cookies = await self.browser_context.cookies()
                return cookies
            except Exception as e:
                utils.logger.warning(f"[CDPBrowserManager] 获取Cookie失败: {e}")
                return []
        return []

    async def cleanup(self):
        """
        清理资源
        """
        try:
            # 关闭浏览器上下文
            if self.browser_context:
                try:
                    await self.browser_context.close()
                    utils.logger.info("[CDPBrowserManager] 浏览器上下文已关闭")
                except Exception as context_error:
                    utils.logger.warning(
                        f"[CDPBrowserManager] 关闭浏览器上下文失败: {context_error}"
                    )
                finally:
                    self.browser_context = None

            # 断开浏览器连接
            if self.browser:
                try:
                    await self.browser.close()
                    utils.logger.info("[CDPBrowserManager] 浏览器连接已断开")
                except Exception as browser_error:
                    utils.logger.warning(
                        f"[CDPBrowserManager] 关闭浏览器连接失败: {browser_error}"
                    )
                finally:
                    self.browser = None

            # 如果使用 wuying-agentbay-sdk，需要删除 session
            if self.agentbay_session:
                try:
                    # 同步版本需要在线程池中运行
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self.agentbay_session.delete)
                    utils.logger.info("[CDPBrowserManager] wuying session 已删除")
                except Exception as wuying_error:
                    utils.logger.warning(
                        f"[CDPBrowserManager] 删除 wuying session 失败: {wuying_error}"
                    )
                finally:
                    self.agentbay_session = None
                    self.agentbay = None
            else:
                # 使用本地浏览器，需要关闭浏览器进程（如果配置为自动关闭）
                if config.AUTO_CLOSE_BROWSER:
                    self.launcher.cleanup()
                else:
                    utils.logger.info(
                        "[CDPBrowserManager] 浏览器进程保持运行（AUTO_CLOSE_BROWSER=False）"
                    )

        except Exception as e:
            utils.logger.error(f"[CDPBrowserManager] 清理资源时出错: {e}")

    def is_connected(self) -> bool:
        """
        检查是否已连接到浏览器
        """
        return self.browser is not None and self.browser.is_connected()

    async def get_browser_info(self) -> Dict[str, Any]:
        """
        获取浏览器信息
        """
        if not self.browser:
            return {}

        try:
            version = self.browser.version
            contexts_count = len(self.browser.contexts)

            return {
                "version": version,
                "contexts_count": contexts_count,
                "debug_port": self.debug_port,
                "is_connected": self.is_connected(),
            }
        except Exception as e:
            utils.logger.warning(f"[CDPBrowserManager] 获取浏览器信息失败: {e}")
            return {}

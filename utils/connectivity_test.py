"""
API 连接测试模块
使用 openai SDK 测试 LLM 接口，使用 requests 测试外部服务。
"""
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List
from openai import OpenAI
import requests


class APIConnectivityTester:
    def __init__(self, settings, timeout: int = 15):
        self.settings = settings
        self.timeout = timeout

    def _collect_configs(self) -> List[Dict[str, Any]]:
        cfgs = []
        # LLM 类型服务
        llm_items = [
            ("Insight Engine", "INSIGHT_ENGINE_API_KEY", "INSIGHT_ENGINE_BASE_URL", "INSIGHT_ENGINE_MODEL_NAME"),
            ("Media Engine", "MEDIA_ENGINE_API_KEY", "MEDIA_ENGINE_BASE_URL", "MEDIA_ENGINE_MODEL_NAME"),
            ("Query Engine", "QUERY_ENGINE_API_KEY", "QUERY_ENGINE_BASE_URL", "QUERY_ENGINE_MODEL_NAME"),
            ("Report Engine", "REPORT_ENGINE_API_KEY", "REPORT_ENGINE_BASE_URL", "REPORT_ENGINE_MODEL_NAME"),
            ("Forum Host", "FORUM_HOST_API_KEY", "FORUM_HOST_BASE_URL", "FORUM_HOST_MODEL_NAME"),
            ("Keyword Optimizer", "KEYWORD_OPTIMIZER_API_KEY", "KEYWORD_OPTIMIZER_BASE_URL", "KEYWORD_OPTIMIZER_MODEL_NAME"),
        ]
        for name, key_attr, base_attr, model_attr in llm_items:
            cfgs.append({
                "name": name,
                "type": "llm",
                "api_key": getattr(self.settings, key_attr, "") or "",
                "base_url": getattr(self.settings, base_attr, "") or "",
                "model": getattr(self.settings, model_attr, "") or ""
            })

        # 外部搜索服务
        if getattr(self.settings, "TAVILY_API_KEY", ""):
            cfgs.append({
                "name": "Tavily Search",
                "type": "tavily",
                "api_key": getattr(self.settings, "TAVILY_API_KEY", ""),
                "test_url": "https://api.tavily.com/search"
            })
        if getattr(self.settings, "BOCHA_WEB_SEARCH_API_KEY", "") and getattr(self.settings, "BOCHA_BASE_URL", ""):
            cfgs.append({
                "name": "Bocha Search",
                "type": "bocha",
                "api_key": getattr(self.settings, "BOCHA_WEB_SEARCH_API_KEY", ""),
                "base_url": getattr(self.settings, "BOCHA_BASE_URL", "")
            })

        return cfgs

    def _test_llm(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        res = {"name": cfg["name"], "status": "unknown", "message": "", "response_time": 0, "details": {}}
        if not cfg["api_key"] or not cfg["base_url"] or not cfg["model"]:
            missing = []
            if not cfg["api_key"]: missing.append("API Key")
            if not cfg["base_url"]: missing.append("Base URL")
            if not cfg["model"]: missing.append("Model")
            res.update({"status": "error", "message": f"缺少配置: {', '.join(missing)}"})
            return res

        start = time.time()
        try:
            client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=self.timeout)
            # 仅做连通性校验：发送简短的 chat 请求
            response = client.chat.completions.create(
                model=cfg["model"],
                messages=[{"role": "user", "content": "连通性测试，请简单回复: 连接成功"}],
                max_tokens=8,
                temperature=0
            )
            elapsed = round((time.time() - start) * 1000, 2)
            res["response_time"] = elapsed

            # 基本判断响应是否合理
            choices = getattr(response, "choices", None)
            if choices and len(choices) > 0:
                # 尝试读取返回文本（尽量容错）
                text = ""
                try:
                    text = choices[0].message.content if getattr(choices[0], "message", None) else str(choices[0])
                except Exception:
                    text = str(choices[0])
                res.update({"status": "success", "message": "连接成功", "details": {"response_snippet": text[:200]}})
            else:
                res.update({"status": "warning", "message": "响应格式异常", "details": {"raw": str(response)[:200]}})
        except Exception as e:
            elapsed = round((time.time() - start) * 1000, 2)
            res["response_time"] = elapsed
            msg = str(e)
            lower = msg.lower()
            if "unauthorized" in lower or "401" in msg:
                res.update({"status": "error", "message": "API Key 无效或未授权", "details": {"error": msg}})
            elif "timed out" in lower or "timeout" in lower:
                res.update({"status": "error", "message": f"请求超时（{self.timeout}s）", "details": {"error": msg}})
            elif "name or service not known" in lower or "connection" in lower or "failed to establish" in lower:
                res.update({"status": "error", "message": "无法连接到 base_url", "details": {"error": msg}})
            else:
                res.update({"status": "error", "message": f"测试失败: {msg}", "details": {"error": msg}})
        return res

    def _test_tavily(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        res = {"name": cfg["name"], "status": "unknown", "message": "", "response_time": 0, "details": {}}
        if not cfg.get("api_key"):
            res.update({"status": "error", "message": "缺少 Tavily API Key"})
            return res
        start = time.time()
        try:
            payload = {"api_key": cfg["api_key"], "query": "test connection", "search_depth": "basic", "max_results": 1}
            r = requests.post(cfg["test_url"], json=payload, timeout=self.timeout)
            res["response_time"] = round((time.time() - start) * 1000, 2)
            if r.status_code == 200:
                res.update({"status": "success", "message": "连接成功"})
            else:
                res.update({"status": "error", "message": f"HTTP {r.status_code}", "details": {"text": r.text[:400]}})
        except Exception as e:
            res.update({"status": "error", "message": f"测试失败: {str(e)}", "details": {"error": str(e)}})
        return res

    def _test_bocha(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        res = {"name": cfg["name"], "status": "unknown", "message": "", "response_time": 0, "details": {}}
        if not cfg.get("api_key") or not cfg.get("base_url"):
            missing = []
            if not cfg.get("api_key"): missing.append("API Key")
            if not cfg.get("base_url"): missing.append("Base URL")
            res.update({"status": "error", "message": f"缺少配置: {', '.join(missing)}"})
            return res
        start = time.time()
        try:
            test_url = cfg["base_url"].rstrip("/")
            headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
            payload = {"query": "test connection", "max_results": 1}
            r = requests.post(test_url, headers=headers, json=payload, timeout=self.timeout)
            res["response_time"] = round((time.time() - start) * 1000, 2)
            if r.status_code == 200:
                res.update({"status": "success", "message": "连接成功"})
            else:
                res.update({"status": "error", "message": f"HTTP {r.status_code}", "details": {"text": r.text[:400]}})
        except Exception as e:
            res.update({"status": "error", "message": f"测试失败: {str(e)}", "details": {"error": str(e)}})
        return res

    def run_all(self) -> Dict[str, Any]:
        cfgs = self._collect_configs()
        results = []
        with ThreadPoolExecutor(max_workers=6) as ex:
            future_map = {}
            for c in cfgs:
                if c["type"] == "llm":
                    future_map[ex.submit(self._test_llm, c)] = c
                elif c["type"] == "tavily":
                    future_map[ex.submit(self._test_tavily, c)] = c
                elif c["type"] == "bocha":
                    future_map[ex.submit(self._test_bocha, c)] = c

            for fut in as_completed(future_map):
                try:
                    results.append(fut.result())
                except Exception as e:
                    cfg = future_map[fut]
                    results.append({"name": cfg.get("name", "unknown"), "status": "error", "message": f"测试异常: {str(e)}", "response_time": 0, "details": {"error": str(e)}})

        total = len(results)
        succ = len([r for r in results if r["status"] == "success"])
        warn = len([r for r in results if r["status"] == "warning"])
        fail = len([r for r in results if r["status"] == "error"])
        summary = {"total": total, "successful": succ, "warning": warn, "failed": fail, "success_rate": round((succ / total) * 100, 1) if total else 0.0}
        return {"success": True, "summary": summary, "results": results, "timestamp": time.time()}


def create_connectivity_tester(settings, timeout: int = 15) -> APIConnectivityTester:
    return APIConnectivityTester(settings, timeout=timeout)

if __name__ == "__main__":
    import os, sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        sys.path.append(project_root)

    from config import settings
    tester = create_connectivity_tester(settings, timeout=15)
    report = tester.run_all()
    print(json.dumps(report, indent=4, ensure_ascii=False))
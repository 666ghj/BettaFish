from typing import Set


class ModelCapabilityDiscriminator:
    """
    模型能力判别器。

    根据模型名称或动态探测结果，判定当前 LLM 是否具备"强模型"特质（超长上下文、复杂指令遵循）。
    用于在 ReportAgent 中切换"高速自适应通道"与"安全分治通道"。
    """

    # 强模型白名单（支持部分匹配）
    STRONG_MODEL_KEYWORDS = {
        "gpt-4",
        "claude-3-opus",
        "claude-3-5-sonnet",
        "gemini-1.5-pro",
        "qwen-max",
        "deepseek-chat"  # DeepSeek V3/R1 is strong enough
    }

    def __init__(self, model_name: str):
        self.model_name = model_name.lower()

    def is_strong_model(self) -> bool:
        """
        判断是否为强模型。

        目前采用静态规则匹配，未来可扩展动态探测逻辑。
        """
        for keyword in self.STRONG_MODEL_KEYWORDS:
            if keyword in self.model_name:
                return True
        return False


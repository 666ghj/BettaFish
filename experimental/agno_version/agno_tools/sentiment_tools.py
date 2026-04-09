# agno_tools/sentiment_tools.py
# 迁移自 BettaFish/InsightEngine/tools/sentiment_analyzer.py
# 多语言情感分析（基于 tabularisai/multilingual-sentiment-analysis 模型）

from __future__ import annotations
from typing import List, Dict, Any, Optional

# 懒加载状态
_torch = None
_tokenizer = None
_model = None
_device = None
_initialized = False
_disabled = False
_disable_reason: Optional[str] = None

SENTIMENT_LABELS = {
    0: "非常负面",
    1: "负面",
    2: "中性",
    3: "正面",
    4: "非常正面",
}


def _initialize() -> bool:
    """懒加载模型，首次调用时下载并加载到设备"""
    global _torch, _tokenizer, _model, _device, _initialized, _disabled, _disable_reason

    if _initialized:
        return True
    if _disabled:
        return False

    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        _torch = torch
    except ImportError as e:
        _disabled = True
        _disable_reason = f"依赖缺失: {e}（需要安装 torch 和 transformers）"
        return False

    try:
        model_name = "tabularisai/multilingual-sentiment-analysis"
        print(f"[sentiment] 正在加载模型 {model_name}...")
        _tokenizer = AutoTokenizer.from_pretrained(model_name)
        _model = AutoModelForSequenceClassification.from_pretrained(model_name)

        # 选择最佳设备
        if torch.cuda.is_available():
            _device = torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            _device = torch.device("mps")
        else:
            _device = torch.device("cpu")

        _model.to(_device)
        _model.eval()
        _initialized = True
        print(f"[sentiment] 模型加载完成，使用设备: {_device}")
        return True
    except Exception as e:
        _disabled = True
        _disable_reason = f"模型加载失败: {e}"
        print(f"[sentiment] {_disable_reason}")
        return False


def _analyze_one(text: str) -> Dict[str, Any]:
    """分析单条文本"""
    if not _initialize():
        return {"label": "未执行", "confidence": 0.0, "error": _disable_reason}

    text = (text or "").strip()
    if not text:
        return {"text": "", "label": "空文本", "confidence": 0.0}

    try:
        inputs = _tokenizer(
            text, max_length=512, padding=True, truncation=True, return_tensors="pt"
        )
        inputs = {k: v.to(_device) for k, v in inputs.items()}

        with _torch.no_grad():
            outputs = _model(**inputs)
            probs = _torch.softmax(outputs.logits, dim=1)
            pred = int(_torch.argmax(probs, dim=1).item())

        confidence = float(probs[0][pred].item())
        return {
            "text": text[:100],
            "label": SENTIMENT_LABELS[pred],
            "confidence": round(confidence, 4),
        }
    except Exception as e:
        return {"text": text[:100], "label": "分析失败", "confidence": 0.0, "error": str(e)}


def analyze_texts(texts: List[str]) -> str:
    """
    批量情感分析，返回格式化字符串供 LLM 消费
    """
    if not texts:
        return "情感分析: 无输入文本"

    if not _initialize():
        return f"情感分析未执行: {_disable_reason}"

    results = [_analyze_one(t) for t in texts]

    # 统计分布
    distribution = {}
    confidence_sum = 0.0
    success_count = 0
    for r in results:
        label = r.get("label", "未知")
        if label in SENTIMENT_LABELS.values():
            distribution[label] = distribution.get(label, 0) + 1
            confidence_sum += r.get("confidence", 0.0)
            success_count += 1

    avg_conf = confidence_sum / success_count if success_count else 0.0

    lines = [f"情感分析结果（共 {len(texts)} 条，成功 {success_count} 条）"]
    lines.append(f"平均置信度: {avg_conf:.4f}")
    lines.append("\n情感分布：")
    for label, count in sorted(distribution.items(), key=lambda x: -x[1]):
        pct = count / success_count * 100 if success_count else 0
        lines.append(f"  - {label}: {count} 条 ({pct:.1f}%)")

    lines.append("\n各条结果（最多前30条）：")
    for i, r in enumerate(results[:30], 1):
        text_preview = (r.get("text") or "")[:80]
        lines.append(f"{i}. [{r.get('label')}] (置信度 {r.get('confidence', 0):.3f}) {text_preview}")

    return "\n".join(lines)

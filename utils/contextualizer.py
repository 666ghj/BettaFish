"""
Structured context utilities for building timeline-aware inputs.

This module adds three core capabilities that multiple agents can share:

1. Token-level semantic labeling powered by lightweight prototypes so we can
   separate concepts such as `animal`, `game_title`, or `numeric_expression`
   without leaking the downstream query intent.
2. Event graph construction that groups raw search/database rows into
   chronological events with weights derived from label confidence.
3. Prompt decoration helpers that append the structured context back to the
   agents so LLMs receive explicit temporal + relational cues.
"""

from __future__ import annotations

import hashlib
import re
import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from loguru import logger

# --- Lightweight semantic prototypes ---------------------------------------------------------

DEFAULT_PROTOTYPES: Dict[str, List[str]] = {
    "animal": [
        "animal",
        "wildlife",
        "bear",
        "penguin",
        "polar",
        "猫",
        "狗",
        "动物",
        "北极熊",
        "企鹅",
        "野生",
    ],
    "game_company": [
        "studio",
        "developer",
        "publisher",
        "company",
        "米哈游",
        "霍格沃茨",
        "hoYoverse",
        "游戏公司",
        "腾讯",
        "网易",
    ],
    "game_title": [
        "game",
        "title",
        "原神",
        "崩坏",
        "绝区零",
        "star rail",
        "honkai",
        "Genshin",
        "手游",
        "MMO",
        "RPG",
        "剧情",
        "动作",
        "冒险",
    ],
    "content_creator": [
        "主播",
        "直播",
        "up主",
        "creator",
        "streamer",
        "平台",
        "b站",
        "douyin",
        "tiktok",
        "快手",
        "youtube",
    ],
    "monetization": [
        "充值",
        "氪金",
        "648",
        "顶级礼包",
        "抽卡",
        "付费",
        "purchase",
        "in-app",
        "销售",
        "售价",
        "金额",
    ],
    "geography": [
        "city",
        "country",
        "地区",
        "省份",
        "海外",
        "国内",
        "north",
        "south",
        "东部",
        "西部",
        "global",
        "国际",
    ],
    "organization": [
        "organization",
        "协会",
        "联盟",
        "group",
        "team",
        "committee",
        "机构",
        "官方",
    ],
    "platform": [
        "platform",
        "社交",
        "社区",
        "论坛",
        "微博",
        "知乎",
        "reddit",
        "discord",
        "快手",
        "抖音",
    ],
    "legal": [
        "law",
        "regulation",
        "法规",
        "法律",
        "政策",
        "compliance",
        "诉讼",
        "仲裁",
    ],
    "sentiment": [
        "支持",
        "反对",
        "正面",
        "负面",
        "controversy",
        "舆论",
        "声量",
        "热度",
    ],
    "technology": [
        "技术",
        "科技",
        "engine",
        "unity",
        "unreal",
        "算法",
        "云",
        "server",
        "AI",
        "模型",
        "渲染",
        "工具链",
    ],
    "financial_metric": [
        "营收",
        "收入",
        "profit",
        "利润",
        "亏损",
        "gmv",
        "估值",
        "现金流",
        "dau",
        "mau",
    ],
    "esports": [
        "战队",
        "联赛",
        "赛事",
        "冠军",
        "选手",
        "杯赛",
        "锦标赛",
        "赛季",
    ],
    "hardware": [
        "主机",
        "硬件",
        "显卡",
        "设备",
        "手柄",
        "耳机",
        "cpu",
        "gpu",
        "终端",
    ],
    "release_milestone": [
        "上线",
        "发布",
        "开测",
        "公测",
        "内测",
        "预约",
        "beta",
        "上市",
        "roadmap",
    ],
    "character": [
        "角色",
        "英雄",
        "npc",
        "boss",
        "角色名",
        "cv",
        "皮肤",
    ],
    "issue_or_bug": [
        "bug",
        "问题",
        "崩溃",
        "报错",
        "故障",
        "卡顿",
        "延迟",
        "漏洞",
    ],
    "community": [
        "玩家",
        "粉丝",
        "社区",
        "社群",
        "论坛",
        "discord",
        "群",
        "讨论",
        "口碑",
    ],
}

STOPWORDS = {
    "and",
    "or",
    "the",
    "of",
    "to",
    "with",
    "for",
    "在",
    "以及",
    "的",
    "了",
    "是",
    "一个",
    "我们",
    "他们",
    "这些",
}


@dataclass
class LabelConfidence:
    label: str
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return {"label": self.label, "score": round(self.score, 4)}


class SemanticPrototypeLabeler:
    """Assigns coarse-grained semantic labels without requiring task context."""

    token_pattern = re.compile(r"[\u4e00-\u9fa5]{2,8}|[A-Za-z0-9_\-:#\./]+")

    def __init__(
        self,
        prototypes: Optional[Dict[str, List[str]]] = None,
        min_confidence: float = 0.18,
        max_labels: int = 4,
    ):
        self.prototypes = prototypes or DEFAULT_PROTOTYPES
        self.min_confidence = min_confidence
        self.max_labels = max_labels

    def tokenize(self, text: str) -> List[str]:
        tokens = []
        for match in self.token_pattern.findall(text or ""):
            token = match.strip()
            token_lower = token.lower()
            if not token or len(token) <= 1:
                continue
            if token_lower in STOPWORDS:
                continue
            tokens.append(token)
        return tokens

    def label_token(self, token: str, context: str = "") -> List[LabelConfidence]:
        blob = f"{token} {context}".lower()
        raw_scores: Dict[str, float] = {}

        for label, keywords in self.prototypes.items():
            score = self._keyword_score(blob, token.lower(), keywords)
            if score > 0:
                raw_scores[label] = max(raw_scores.get(label, 0.0), score)

        numeric_score = self._numeric_score(token)
        if numeric_score:
            raw_scores["numeric_expression"] = max(
                raw_scores.get("numeric_expression", 0.0), numeric_score
            )

        if self._looks_like_time(token):
            raw_scores["temporal_reference"] = max(
                raw_scores.get("temporal_reference", 0.0), 0.45
            )

        if "-" in token or "/" in token:
            raw_scores["composite_term"] = max(
                raw_scores.get("composite_term", 0.0), 0.3
            )

        if not raw_scores:
            raw_scores["unknown"] = 0.2

        return self._normalize_scores(raw_scores)

    # ---- private helpers ------------------------------------------------------------------

    def _keyword_score(
        self, blob: str, token_lower: str, keywords: Iterable[str]
    ) -> float:
        if not keywords:
            return 0.0
        matches = 0.0
        blob = blob.lower()
        for kw in keywords:
            lowered = kw.lower()
            if lowered in blob:
                matches += 1.0
                continue
            similarity = self._ratio(token_lower, lowered)
            if similarity >= 0.82:
                matches += similarity * 0.8
        if matches == 0:
            return 0.0
        return min(1.0, matches / len(list(keywords)))

    @staticmethod
    def _ratio(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        matches = sum((1 for ch in a if ch in b))
        return matches / max(len(a), len(b))

    @staticmethod
    def _numeric_score(token: str) -> float:
        if any(char.isdigit() for char in token):
            # Boost when包含货币或单位
            if any(symbol in token for symbol in ["$", "¥", "元", "刀", "%"]):
                return 0.75
            return 0.55
        return 0.0

    @staticmethod
    def _looks_like_time(token: str) -> bool:
        return bool(re.match(r"\d{1,2}[:：]\d{2}", token)) or "年" in token or "月" in token

    def _normalize_scores(self, raw_scores: Dict[str, float]) -> List[LabelConfidence]:
        total = sum(raw_scores.values())
        if total == 0:
            total = 1.0
        normalized = []
        for label, value in sorted(
            raw_scores.items(), key=lambda item: item[1], reverse=True
        ):
            score = round(value / total, 4)
            if score < self.min_confidence and label != "unknown":
                continue
            normalized.append(LabelConfidence(label=label, score=score))
            if len(normalized) >= self.max_labels:
                break
        return normalized


# --- Structured context builder --------------------------------------------------------------


class StructuredContextBuilder:
    """Transforms raw search/database rows into a deterministic context payload."""

    def __init__(
        self,
        agent_name: str = "generic",
        labeler: Optional[SemanticPrototypeLabeler] = None,
        max_tokens_per_event: int = 8,
        keyword_labeler: Optional[Any] = None,
        keyword_labeler_max_snippets: int = 3,
        adaptive_pruning: bool = True,
        min_events_per_stage: int = 2,
        max_events_per_stage: int = 15,
        stage_retention_defaults: Optional[Dict[str, float]] = None,
        relevance_min_label_overlap: int = 1,
        relevance_min_keyword_overlap: int = 1,
    ):
        self.agent_name = agent_name
        self.labeler = labeler or SemanticPrototypeLabeler()
        self.max_tokens_per_event = max_tokens_per_event
        self.keyword_labeler = keyword_labeler
        self.keyword_labeler_max_snippets = keyword_labeler_max_snippets
        self.adaptive_pruning = adaptive_pruning
        self.min_events_per_stage = max(1, min_events_per_stage)
        self.max_events_per_stage = max(self.min_events_per_stage, max_events_per_stage)
        self.stage_retention_defaults = stage_retention_defaults or {
            "initial": 0.65,
            "reflection": 0.45,
            "default": 0.55,
        }
        self.relevance_min_label_overlap = max(0, relevance_min_label_overlap)
        self.relevance_min_keyword_overlap = max(0, relevance_min_keyword_overlap)

    # Public API ---------------------------------------------------------------------------

    def empty_context(self) -> Dict[str, Any]:
        return {
            "events": {},
            "relations": [],
            "timeline": [],
            "token_statistics": {},
            "metadata": {
                "agent": self.agent_name,
                "created_at": datetime.utcnow().isoformat(),
                "origin_event_id": None,
                "origin_query": None,
                "origin_labels": [],
                "origin_dominant_labels": [],
                "suppressed_events": [],
                "weight_retention_profile": {},
            },
        }

    def enrich_with_search_results(
        self,
        search_results: List[Dict[str, Any]],
        *,
        query: str,
        paragraph_title: str,
        stage: str,
        origin_query: Optional[str] = None,
        existing_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        context = existing_context or self.empty_context()
        if origin_query:
            context = self._ensure_origin_node(origin_query, context)

        if not search_results:
            return search_results, context

        origin_meta = context.get("metadata", {})
        origin_labels = set(origin_meta.get("origin_dominant_labels") or [])
        origin_tokens = origin_meta.get("_origin_tokens_cache")
        if origin_tokens is None:
            origin_tokens = {
                token.lower()
                for token in re.findall(r"[\w\u4e00-\u9fff]+", origin_meta.get("origin_query", "") or "")
                if len(token) >= 2
            }
            origin_meta["_origin_tokens_cache"] = origin_tokens
            context["metadata"] = origin_meta

        origin_event = None
        origin_event_id = origin_meta.get("origin_event_id")
        if origin_event_id:
            origin_event = context.get("events", {}).get(origin_event_id)

        relations_index = {
            tuple(sorted((rel["source_event"], rel["target_event"])))
            for rel in context.get("relations", [])
        }

        candidates = []
        similarity_scores = []
        for idx, result in enumerate(search_results):
            event = self._build_event(
                result,
                query=query,
                paragraph_title=paragraph_title,
                stage=stage,
                ordinal=idx,
            )
            if origin_event:
                similarity = self._label_similarity(
                    event.get("label_distribution"),
                    origin_event.get("label_distribution"),
                )
                event["origin_similarity"] = similarity
                similarity_scores.append(similarity)
            candidates.append((event, result))

        similarity_average = None
        if similarity_scores:
            similarity_average = statistics.mean(similarity_scores)

        decorated_results = []
        dropped = 0
        for event, result in candidates:
            if similarity_average is not None:
                if event.get("origin_similarity", 0.0) < similarity_average:
                    dropped += 1
                    continue
            elif not self._is_relevant_to_origin(event, origin_labels, origin_tokens):
                dropped += 1
                continue
            context["events"][event["event_id"]] = event
            self._update_token_statistics(context, event)
            self._update_relations(context, event, relations_index)
            self._update_origin_relation(context, event, relations_index)
            decorated_results.append(self._decorate_result(result, event))

        if dropped:
            if similarity_average is not None:
                logger.info(
                    f"[{self.agent_name}] 基于标签相似度均值 {similarity_average:.3f} 屏蔽 {dropped}/{len(search_results)} 条 (stage={stage})"
                )
            else:
                logger.info(
                    f"[{self.agent_name}] 过滤 {dropped}/{len(search_results)} 条与主题无关的内容 (stage={stage})"
                )

        self._refresh_views(context)
        context["metadata"].update(
            {
                "last_query": query,
                "last_stage": stage,
                "paragraph_title": paragraph_title,
                "updated_at": datetime.utcnow().isoformat(),
            }
        )
        if similarity_average is not None:
            context["metadata"]["last_similarity_average"] = round(similarity_average, 4)
        return decorated_results, context

    def ensure_origin_context(
        self,
        origin_query: str,
        existing_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ensure the structured context已经包含原点节点。
        """
        context = existing_context or self.empty_context()
        return self._ensure_origin_node(origin_query, context)

    def apply_weight_compaction(
        self,
        context: Dict[str, Any],
        stage: str,
        candidate_event_ids: Optional[Sequence[str]] = None,
    ) -> Optional[Set[str]]:
        """
        根据当前阶段的权重分布动态裁剪事件，返回保留的事件ID集合。
        """
        if not self.adaptive_pruning:
            return None
        return self._prune_stage_events(context, stage, candidate_event_ids)

    # Internal helpers --------------------------------------------------------------------

    def _ensure_origin_node(
        self, origin_query: Optional[str], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not origin_query:
            return context
        origin_query = origin_query.strip()
        if not origin_query:
            return context

        metadata = context.setdefault("metadata", {})
        events = context.setdefault("events", {})
        current_origin_id = metadata.get("origin_event_id")

        if current_origin_id and current_origin_id in events:
            if origin_query == metadata.get("origin_query"):
                return context
            events.pop(current_origin_id, None)
            context["relations"] = [
                rel
                for rel in context.get("relations", [])
                if current_origin_id
                not in (rel.get("source_event"), rel.get("target_event"))
            ]

        origin_event = self._build_origin_event(origin_query)
        events[origin_event["event_id"]] = origin_event
        metadata.update(
            {
                "origin_event_id": origin_event["event_id"],
                "origin_query": origin_query,
                "origin_labels": origin_event.get("label_distribution", []),
                "origin_dominant_labels": origin_event.get("dominant_labels", []),
                "origin_updated_at": datetime.utcnow().isoformat(),
            }
        )
        self._update_token_statistics(context, origin_event)
        return context

    def _prune_stage_events(
        self,
        context: Dict[str, Any],
        stage: str,
        candidate_event_ids: Optional[Sequence[str]] = None,
    ) -> Optional[Set[str]]:
        events = context.get("events", {})
        stage_key = self._stage_key(stage)
        active_events = [
            event
            for event in events.values()
            if not event.get("is_origin")
            and self._stage_key(event.get("stage")) == stage_key
        ]
        if len(active_events) <= self.min_events_per_stage:
            return None

        retention_ratio = self._stage_retention_ratio(stage_key)
        keep_count = max(
            self.min_events_per_stage,
            int(round(len(active_events) * retention_ratio)),
        )
        keep_count = min(len(active_events), keep_count, self.max_events_per_stage)
        if keep_count >= len(active_events):
            return None

        ranked_events = sorted(
            active_events,
            key=lambda ev: ev.get("weight", ev.get("intrinsic_weight", 0.0)),
            reverse=True,
        )
        weights = [ev.get("weight", 0.0) for ev in ranked_events]
        percentile_index = max(0, min(len(weights) - 1, keep_count - 1))
        percentile_weight = weights[percentile_index]
        median_weight = statistics.median(weights)
        adaptive_cutoff = max(percentile_weight, median_weight * 0.85)

        keep_ids = {
            ev["event_id"]
            for ev in ranked_events[:keep_count]
        }
        keep_ids.update(
            ev["event_id"]
            for ev in ranked_events
            if ev.get("weight", 0.0) >= adaptive_cutoff
        )

        newly_suppressed = []
        changed = False
        for event in active_events:
            previous_state = event.get("suppressed", False)
            suppressed = event["event_id"] not in keep_ids
            event["suppressed"] = suppressed
            if suppressed != previous_state:
                changed = True
            if suppressed and not previous_state:
                newly_suppressed.append(
                    {
                        "event_id": event["event_id"],
                        "stage": stage_key,
                        "weight": round(event.get("weight", 0.0), 3),
                        "cutoff": round(adaptive_cutoff, 3),
                    }
                )

        if newly_suppressed:
            metadata = context.setdefault("metadata", {})
            metadata.setdefault("suppressed_events", []).extend(newly_suppressed)
            metadata.setdefault("weight_retention_profile", {}).update(
                {
                    stage_key: {
                        "total": len(active_events),
                        "kept": len(keep_ids),
                        "cutoff": round(adaptive_cutoff, 3),
                    }
                }
            )

        if changed:
            self._refresh_views(context)

        if candidate_event_ids:
            candidate_set = {event_id for event_id in candidate_event_ids if event_id}
            if candidate_set:
                return keep_ids.intersection(candidate_set)
        return keep_ids

    def _refresh_views(self, context: Dict[str, Any]) -> None:
        events = context.get("events", {})
        context["timeline"] = sorted(
            [
                event
                for event in events.values()
                if not event.get("suppressed")
            ],
            key=lambda ev: ev.get("timestamp") or "",
        )
        context["token_statistics"] = {}
        for event in context["timeline"]:
            self._update_token_statistics(context, event)
        context["relations"] = [
            relation
            for relation in context.get("relations", [])
            if not self._is_suppressed(events, relation.get("source_event"))
            and not self._is_suppressed(events, relation.get("target_event"))
        ]

    def _stage_retention_ratio(self, stage_key: str) -> float:
        base = self.stage_retention_defaults.get(
            stage_key, self.stage_retention_defaults.get("default", 0.55)
        )
        return max(0.2, min(0.95, base))

    @staticmethod
    def _stage_key(stage: Optional[str]) -> str:
        if not stage:
            return "default"
        stage_lower = stage.lower()
        if stage_lower.startswith("reflection"):
            return "reflection"
        return stage_lower

    @staticmethod
    def _is_suppressed(events: Dict[str, Any], event_id: Optional[str]) -> bool:
        if not event_id:
            return False
        event = events.get(event_id)
        return bool(event and event.get("suppressed"))

    def _build_event(
        self,
        result: Dict[str, Any],
        *,
        query: str,
        paragraph_title: str,
        stage: str,
        ordinal: int,
    ) -> Dict[str, Any]:
        source_url = result.get("url") or f"{self.agent_name.lower()}://local/{ordinal}"
        timestamp = self._normalize_timestamp(result.get("published_date"))
        text_blob = " ".join(
            filter(
                None,
                [
                    result.get("title", ""),
                    result.get("raw_content") or result.get("content") or "",
                ],
            )
        )
        tokens = self._token_annotations(text_blob, source_url, timestamp)
        label_distribution = self._aggregate_labels(tokens)
        dominant = [
            lbl["label"]
            for lbl in label_distribution[:3]
            if lbl["score"] >= 0.18
        ]
        event_id = self._event_id(source_url, timestamp, ordinal)
        summary = (result.get("content") or result.get("title") or "")[:400]
        weight = self._estimate_weight(tokens, label_distribution)
        return {
            "event_id": event_id,
            "timestamp": timestamp,
            "source": source_url,
            "weight": weight,
            "intrinsic_weight": weight,
            "summary": summary,
            "query": query,
            "paragraph": paragraph_title,
            "stage": stage,
            "tokens": tokens,
            "label_distribution": label_distribution,
            "top_labels": label_distribution[:3],
            "dominant_labels": dominant,
            "suppressed": False,
            "is_origin": False,
        }

    def _is_relevant_to_origin(
        self,
        event: Dict[str, Any],
        origin_labels: Set[str],
        origin_tokens: Set[str],
    ) -> bool:
        """
        粗过滤：若与原始主题几乎无标签/关键词重叠，则视为无关内容。
        """
        if not origin_labels and not origin_tokens:
            return True

        event_labels = set(event.get("dominant_labels") or [])
        if origin_labels and len(event_labels.intersection(origin_labels)) >= self.relevance_min_label_overlap:
            return True

        summary_text = f"{event.get('summary', '')} {event.get('query', '')}".lower()
        event_tokens = {
            token
            for token in re.findall(r"[\w\u4e00-\u9fff]+", summary_text)
            if len(token) >= 2
        }
        if origin_tokens:
            overlap = len(event_tokens.intersection(origin_tokens))
            if overlap >= self.relevance_min_keyword_overlap:
                return True

        return False

    def _build_origin_event(self, origin_query: str) -> Dict[str, Any]:
        timestamp = datetime.utcnow().isoformat()
        source_url = f"{self.agent_name.lower()}://origin"
        tokens = self._token_annotations(origin_query, source_url, timestamp)
        label_distribution = self._aggregate_labels(tokens)
        dominant = [
            lbl["label"] for lbl in label_distribution[:3] if lbl["score"] >= 0.15
        ]
        event_id = f"origin-{hashlib.sha1(origin_query.encode('utf-8')).hexdigest()[:12]}"
        weight = max(1.0, self._estimate_weight(tokens, label_distribution))
        return {
            "event_id": event_id,
            "timestamp": timestamp,
            "source": source_url,
            "weight": weight,
            "intrinsic_weight": weight,
            "summary": origin_query[:400],
            "query": origin_query,
            "paragraph": "origin",
            "stage": "origin",
            "tokens": tokens,
            "label_distribution": label_distribution,
            "top_labels": label_distribution[:3],
            "dominant_labels": dominant,
            "origin_similarity": 1.0,
            "origin_shared_labels": dominant,
            "suppressed": False,
            "is_origin": True,
        }

    def _token_annotations(
        self, text_blob: str, source_url: str, timestamp: str
    ) -> List[Dict[str, Any]]:
        annotations: List[Dict[str, Any]] = []
        seen_terms = set()

        for annotation in self._keyword_labeler_annotations(
            text_blob, source_url, timestamp
        ):
            annotations.append(annotation)
            seen_terms.add(annotation["text"].lower())

        for token in self.labeler.tokenize(text_blob)[: self.max_tokens_per_event]:
            token_lower = token.lower()
            if token_lower in seen_terms:
                continue
            context_snippet = self._context_snippet(text_blob, token)
            labels = [label.to_dict() for label in self.labeler.label_token(token, context_snippet)]
            annotations.append(
                {
                    "text": token,
                    "context": context_snippet,
                    "labels": labels,
                    "source": source_url,
                    "timestamp": timestamp,
                }
            )
            seen_terms.add(token_lower)
        return annotations

    def _keyword_labeler_annotations(
        self, text_blob: str, source_url: str, timestamp: str
    ) -> List[Dict[str, Any]]:
        if not self.keyword_labeler:
            return []
        snippets = self._slice_text_for_labeler(text_blob)
        annotations: List[Dict[str, Any]] = []
        for snippet in snippets:
            try:
                suggestions = self.keyword_labeler.label_terms(
                    snippet,
                    topic=self.agent_name,
                    max_terms=self.max_tokens_per_event,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning(f"关键词标签器调用失败: {exc}")
                break

            for item in suggestions or []:
                term = item.get("term") or item.get("text")
                if not term:
                    continue
                labels = item.get("labels") or []
                normalized = []
                for label in labels:
                    name = label.get("label") or label.get("name")
                    if not name:
                        continue
                    score = float(label.get("score") or label.get("confidence") or 0.5)
                    normalized.append(
                        {"label": name, "score": max(0.0, min(1.0, score))}
                    )
                if not normalized:
                    normalized.append({"label": "other", "score": 0.5})
                annotations.append(
                    {
                        "text": term.strip(),
                        "context": snippet[:200],
                        "labels": normalized,
                        "source": source_url,
                        "timestamp": timestamp,
                    }
                )
        return annotations

    def _slice_text_for_labeler(self, text_blob: str) -> List[str]:
        if not text_blob:
            return []
        import re

        raw_sentences = re.split(r'(?<=[。！？!?])\s+|\n+', text_blob)
        sentences = [
            sentence.strip()
            for sentence in raw_sentences
            if len(sentence.strip()) >= 4
        ]
        selected = sentences[: self.keyword_labeler_max_snippets]
        if not selected:
            selected = [text_blob[:240]]
        return [sentence[:400] for sentence in selected]

    def _aggregate_labels(self, tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        scores: Dict[str, float] = {}
        for token in tokens:
            for label in token.get("labels", []):
                scores[label["label"]] = scores.get(label["label"], 0.0) + label["score"]
        total = sum(scores.values()) or 1.0
        aggregated = [
            {"label": label, "score": round(value / total, 4)}
            for label, value in scores.items()
        ]
        return sorted(aggregated, key=lambda item: item["score"], reverse=True)

    @staticmethod
    def _estimate_weight(
        tokens: List[Dict[str, Any]], label_distribution: List[Dict[str, Any]]
    ) -> float:
        if not tokens:
            return 0.0
        score = sum(label["score"] for label in label_distribution[:3])
        weight = len(tokens) * score
        return round(weight, 3)

    @staticmethod
    def _context_snippet(text: str, token: str, window: int = 32) -> str:
        lower = text.lower()
        token_lower = token.lower()
        idx = lower.find(token_lower)
        if idx == -1:
            idx = 0
        start = max(0, idx - window)
        end = min(len(text), idx + len(token) + window)
        snippet = text[start:end].strip()
        return re.sub(r"\s+", " ", snippet)

    @staticmethod
    def _normalize_timestamp(value: Optional[str]) -> str:
        if not value:
            return datetime.utcnow().isoformat()
        value = value.strip()
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(value).isoformat()
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).isoformat()
            except ValueError:
                continue
        return datetime.utcnow().isoformat()

    @staticmethod
    def _event_id(source: str, timestamp: str, ordinal: int) -> str:
        raw = f"{source}-{timestamp}-{ordinal}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    def _update_token_statistics(
        self, context: Dict[str, Any], event: Dict[str, Any]
    ) -> None:
        stats = context.setdefault("token_statistics", {})
        for token in event.get("tokens", []):
            key = token["text"].lower()
            record = stats.setdefault(
                key,
                {
                    "token": token["text"],
                    "count": 0,
                    "labels": {},
                    "examples": [],
                    "sources": [],
                    "last_seen": None,
                    "weight": 0.0,
                },
            )
            record["count"] += 1
            record["last_seen"] = event["timestamp"]
            for label in token.get("labels", []):
                record["labels"][label["label"]] = max(
                    record["labels"].get(label["label"], 0.0), label["score"]
                )
            if len(record["examples"]) < 5:
                record["examples"].append(token["context"])
            if token["source"] and token["source"] not in record["sources"]:
                record["sources"].append(token["source"])
            max_label = max(record["labels"].values(), default=0.1)
            record["weight"] = round(record["count"] * max_label, 3)

    def _update_relations(
        self,
        context: Dict[str, Any],
        event: Dict[str, Any],
        relation_index: set,
    ) -> None:
        if not event.get("dominant_labels") or event.get("suppressed"):
            return
        events = context.get("events", {})
        for other_id, other in events.items():
            if other_id == event["event_id"]:
                continue
            if other.get("suppressed"):
                continue
            shared = set(event["dominant_labels"]).intersection(
                other.get("dominant_labels", [])
            )
            if not shared:
                continue
            pair = tuple(sorted((event["event_id"], other_id)))
            if pair in relation_index:
                continue
            relation = {
                "source_event": pair[0],
                "target_event": pair[1],
                "shared_labels": sorted(shared),
                "weight": len(shared),
            }
            context.setdefault("relations", []).append(relation)
            relation_index.add(pair)

    def _update_origin_relation(
        self,
        context: Dict[str, Any],
        event: Dict[str, Any],
        relation_index: set,
    ) -> None:
        if event.get("suppressed"):
            return
        metadata = context.get("metadata", {})
        origin_id = metadata.get("origin_event_id")
        if not origin_id or origin_id == event["event_id"]:
            return
        origin_event = context.get("events", {}).get(origin_id)
        if not origin_event:
            return

        similarity = self._label_similarity(
            event.get("label_distribution"),
            origin_event.get("label_distribution"),
        )
        shared = sorted(
            set(event.get("dominant_labels", [])).intersection(
                origin_event.get("dominant_labels", [])
            )
        )

        pair = tuple(sorted((origin_id, event["event_id"])))
        if pair not in relation_index:
            relation_index.add(pair)
            context.setdefault("relations", []).insert(
                0,
                {
                    "source_event": origin_id,
                    "target_event": event["event_id"],
                    "shared_labels": shared,
                    "weight": round(similarity, 4),
                    "type": "origin_link",
                },
            )

        event["origin_similarity"] = similarity
        event["origin_shared_labels"] = shared
        intrinsic = event.get("intrinsic_weight", event.get("weight", 0.0))
        event["weight"] = round(max(intrinsic, similarity * 10), 3)

    def _decorate_result(self, result: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
        annotated = dict(result)
        annotation = self._render_annotation(event)
        content = annotated.get("content") or ""
        annotated["content"] = f"{content}\n\n[structured_context]\n{annotation}".strip()
        annotated["structured_event_id"] = event["event_id"]
        return annotated

    @staticmethod
    def _label_similarity(
        primary: Optional[List[Dict[str, Any]]],
        secondary: Optional[List[Dict[str, Any]]],
    ) -> float:
        if not primary or not secondary:
            return 0.0
        reference = {item["label"]: item["score"] for item in secondary}
        overlap = 0.0
        for item in primary:
            label = item.get("label")
            if label in reference:
                overlap += min(item.get("score", 0.0), reference[label])
        return round(overlap, 4)

    @staticmethod
    def _render_annotation(event: Dict[str, Any]) -> str:
        label_line = ", ".join(
            f"{lbl['label']}({lbl['score']:.2f})" for lbl in event.get("top_labels", [])
        )
        token_lines = []
        for token in event.get("tokens", [])[:5]:
            labels = ", ".join(
                f"{lbl['label']}:{lbl['score']:.2f}" for lbl in token.get("labels", [])
            )
            token_lines.append(f"- {token['text']}: {labels}")
        token_section = "\n".join(token_lines)
        origin_lines = ""
        if event.get("origin_similarity") is not None:
            shared = ",".join(event.get("origin_shared_labels", []))
            shared_str = f"\nORIGIN_SHARED_LABELS={shared}" if shared else ""
            origin_lines = (
                f"\nORIGIN_SIMILARITY={event['origin_similarity']:.3f}{shared_str}"
            )
        return (
            f"EVENT_ID={event['event_id']}\n"
            f"TIMESTAMP={event['timestamp']}\n"
            f"PARAGRAPH={event.get('paragraph')}\n"
            f"STAGE={event.get('stage')}\n"
            f"WEIGHT={event.get('weight')}\n"
            f"LABELS={label_line}\n"
            f"TOKENS:\n{token_section}"
            f"{origin_lines}"
        )

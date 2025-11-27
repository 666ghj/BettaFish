"""
图表验证和修复工具。

提供对Chart.js图表数据的验证和修复能力：
1. 验证图表数据格式是否符合Chart.js要求
2. 本地规则修复常见问题
3. LLM API辅助修复复杂问题
4. 遵循"宁愿不改，也不要改错"的原则

支持的图表类型：
- line (折线图)
- bar (柱状图)
- pie (饼图)
- doughnut (圆环图)
- radar (雷达图)
- polarArea (极地区域图)
- scatter (散点图)
"""

from __future__ import annotations

import copy
import json
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
from loguru import logger


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]

    def has_critical_errors(self) -> bool:
        """是否有严重错误（会导致渲染失败）"""
        return not self.is_valid and len(self.errors) > 0


@dataclass
class RepairResult:
    """修复结果"""
    success: bool
    repaired_block: Optional[Dict[str, Any]]
    method: str  # 'none', 'local', 'api'
    changes: List[str]

    def has_changes(self) -> bool:
        """是否有修改"""
        return len(self.changes) > 0


class ChartValidator:
    """
    图表验证器 - 验证Chart.js图表数据格式是否正确。

    验证规则：
    1. 基本结构验证：widgetType, props, data字段
    2. 图表类型验证：支持的图表类型
    3. 数据格式验证：labels和datasets结构
    4. 数据一致性验证：labels和datasets长度匹配
    5. 数值类型验证：数据值类型正确
    """

    # 支持的图表类型
    SUPPORTED_CHART_TYPES = {
        'line', 'bar', 'pie', 'doughnut', 'radar', 'polarArea', 'scatter',
        'bubble', 'horizontalBar'
    }

    # 需要labels的图表类型
    LABEL_REQUIRED_TYPES = {
        'line', 'bar', 'radar', 'polarArea', 'pie', 'doughnut'
    }

    # 需要数值数据的图表类型
    NUMERIC_DATA_TYPES = {
        'line', 'bar', 'radar', 'polarArea', 'pie', 'doughnut'
    }

    # 需要特殊数据格式的图表类型
    SPECIAL_DATA_TYPES = {
        'scatter': {'x', 'y'},
        'bubble': {'x', 'y', 'r'}
    }

    def __init__(self):
        """初始化验证器并预留缓存结构，便于后续复用验证/修复结果"""

    def validate(self, widget_block: Dict[str, Any]) -> ValidationResult:
        """
        验证图表格式。

        Args:
            widget_block: widget类型的block，包含widgetId/widgetType/props/data

        Returns:
            ValidationResult: 验证结果
        """
        errors = []
        warnings = []

        # 1. 基本结构验证
        if not isinstance(widget_block, dict):
            errors.append("widget_block必须是字典类型")
            return ValidationResult(False, errors, warnings)

        # 2. 检查widgetType
        widget_type = widget_block.get('widgetType', '')
        if not widget_type or not isinstance(widget_type, str):
            errors.append("缺少widgetType字段或类型不正确")
            return ValidationResult(False, errors, warnings)

        # 检查是否是chart.js类型
        if not widget_type.startswith('chart.js'):
            # 不是图表类型，跳过验证
            return ValidationResult(True, errors, warnings)

        # 3. 提取图表类型
        chart_type = self._extract_chart_type(widget_block)
        if not chart_type:
            errors.append("无法确定图表类型")
            return ValidationResult(False, errors, warnings)

        # 4. 检查是否支持该图表类型
        if chart_type not in self.SUPPORTED_CHART_TYPES:
            warnings.append(f"图表类型 '{chart_type}' 可能不被支持，将尝试降级渲染")

        # 5. 验证数据结构
        data = widget_block.get('data')
        if not isinstance(data, dict):
            errors.append("data字段必须是字典类型")
            return ValidationResult(False, errors, warnings)

        # 检测是否使用了{x, y}形式的数据点（通常用于时间轴/散点）
        def contains_object_points(ds_list: List[Any] | None) -> bool:
            """检查数据集中是否包含以x/y键表示的对象点，用于切换验证分支"""
            if not isinstance(ds_list, list):
                return False
            for point in ds_list:
                if isinstance(point, dict) and any(key in point for key in ('x', 'y', 't')):
                    return True
            return False

        datasets_for_detection = data.get('datasets') or []
        uses_object_points = any(
            isinstance(ds, dict) and contains_object_points(ds.get('data'))
            for ds in datasets_for_detection
        )

        # 6. 根据图表类型验证数据
        if chart_type in self.SPECIAL_DATA_TYPES:
            # 特殊数据格式（scatter, bubble）
            self._validate_special_data(data, chart_type, errors, warnings)
        else:
            # 标准数据格式（labels + datasets）
            self._validate_standard_data(data, chart_type, errors, warnings, uses_object_points)

        # 7. 验证props
        props = widget_block.get('props')
        if props is not None and not isinstance(props, dict):
            warnings.append("props字段应该是字典类型")

        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings)

    def _extract_chart_type(self, widget_block: Dict[str, Any]) -> Optional[str]:
        """
        提取图表类型。

        优先级：
        1. props.type
        2. widgetType中的类型（chart.js/bar -> bar）
        3. data.type
        """
        # 1. 从props中获取
        props = widget_block.get('props') or {}
        if isinstance(props, dict):
            chart_type = props.get('type')
            if chart_type and isinstance(chart_type, str):
                return chart_type.lower()

        # 2. 从widgetType中提取
        widget_type = widget_block.get('widgetType', '')
        if '/' in widget_type:
            chart_type = widget_type.split('/')[-1]
            if chart_type:
                return chart_type.lower()

        # 3. 从data中获取
        data = widget_block.get('data') or {}
        if isinstance(data, dict):
            chart_type = data.get('type')
            if chart_type and isinstance(chart_type, str):
                return chart_type.lower()

        return None

    def _validate_standard_data(
        self,
        data: Dict[str, Any],
        chart_type: str,
        errors: List[str],
        warnings: List[str],
        uses_object_points: bool = False
    ):
        """验证标准数据格式（labels + datasets）"""
        labels = data.get('labels')
        datasets = data.get('datasets')

        # 验证labels
        if chart_type in self.LABEL_REQUIRED_TYPES:
            if not labels:
                if uses_object_points:
                    warnings.append(
                        f"{chart_type}类型图表缺少labels，已根据数据点渲染（使用x值）"
                    )
                else:
                    errors.append(f"{chart_type}类型图表必须包含labels字段")
            elif not isinstance(labels, list):
                errors.append("labels必须是数组类型")
            elif len(labels) == 0:
                warnings.append("labels数组为空，图表可能无法正常显示")

        # 验证datasets
        if datasets is None:
            errors.append("缺少datasets字段")
            return

        if not isinstance(datasets, list):
            errors.append("datasets必须是数组类型")
            return

        if len(datasets) == 0:
            errors.append("datasets数组为空")
            return

        # 验证每个dataset
        for idx, dataset in enumerate(datasets):
            if not isinstance(dataset, dict):
                errors.append(f"datasets[{idx}]必须是对象类型")
                continue

            # 验证data字段
            ds_data = dataset.get('data')
            if ds_data is None:
                errors.append(f"datasets[{idx}]缺少data字段")
                continue

            if not isinstance(ds_data, list):
                errors.append(f"datasets[{idx}].data必须是数组类型")
                continue

            if len(ds_data) == 0:
                warnings.append(f"datasets[{idx}].data数组为空")
                continue

            # 如果是{x, y}对象形式的数据点，默认允许跳过labels长度和数值校验
            object_points = any(
                isinstance(value, dict) and any(key in value for key in ('x', 'y', 't'))
                for value in ds_data
            )

            # 验证数据长度一致性
            if labels and isinstance(labels, list) and not object_points:
                if len(ds_data) != len(labels):
                    warnings.append(
                        f"datasets[{idx}].data长度({len(ds_data)})与labels长度({len(labels)})不匹配"
                    )

            # 验证数值类型
            if chart_type in self.NUMERIC_DATA_TYPES and not object_points:
                for data_idx, value in enumerate(ds_data):
                    if value is not None and not isinstance(value, (int, float)):
                        errors.append(
                            f"datasets[{idx}].data[{data_idx}]的值'{value}'不是有效的数值类型"
                        )
                        break  # 只报告第一个错误

    def _validate_special_data(
        self,
        data: Dict[str, Any],
        chart_type: str,
        errors: List[str],
        warnings: List[str]
    ):
        """验证特殊数据格式（scatter, bubble）"""
        datasets = data.get('datasets')

        if not datasets:
            errors.append("缺少datasets字段")
            return

        if not isinstance(datasets, list):
            errors.append("datasets必须是数组类型")
            return

        if len(datasets) == 0:
            errors.append("datasets数组为空")
            return

        required_keys = self.SPECIAL_DATA_TYPES.get(chart_type, set())

        # 验证每个dataset
        for idx, dataset in enumerate(datasets):
            if not isinstance(dataset, dict):
                errors.append(f"datasets[{idx}]必须是对象类型")
                continue

            ds_data = dataset.get('data')
            if ds_data is None:
                errors.append(f"datasets[{idx}]缺少data字段")
                continue

            if not isinstance(ds_data, list):
                errors.append(f"datasets[{idx}].data必须是数组类型")
                continue

            if len(ds_data) == 0:
                warnings.append(f"datasets[{idx}].data数组为空")
                continue

            # 验证数据点格式
            for data_idx, point in enumerate(ds_data):
                if not isinstance(point, dict):
                    errors.append(
                        f"datasets[{idx}].data[{data_idx}]必须是对象类型（包含{required_keys}字段）"
                    )
                    break

                # 检查必需的键
                missing_keys = required_keys - set(point.keys())
                if missing_keys:
                    errors.append(
                        f"datasets[{idx}].data[{data_idx}]缺少必需字段: {missing_keys}"
                    )
                    break

                # 验证数值类型
                for key in required_keys:
                    value = point.get(key)
                    if value is not None and not isinstance(value, (int, float)):
                        errors.append(
                            f"datasets[{idx}].data[{data_idx}].{key}的值'{value}'不是有效的数值类型"
                        )
                        break

    def can_render(self, widget_block: Dict[str, Any]) -> bool:
        """
        判断图表是否能正常渲染（快速检查）。

        Args:
            widget_block: widget类型的block

        Returns:
            bool: 是否能正常渲染
        """
        result = self.validate(widget_block)
        return result.is_valid


class ChartRepairer:
    """
    图表修复器 - 尝试修复图表数据。

    修复策略：
    1. 本地规则修复：修复常见问题
    2. API修复：使用LLM修复复杂问题
    3. 验证修复结果：确保修复后能正常渲染
    """

    def __init__(
        self,
        validator: ChartValidator,
        llm_repair_fns: Optional[List[Callable]] = None
    ):
        """
        初始化修复器。

        Args:
            validator: 图表验证器实例
            llm_repair_fns: LLM修复函数列表（对应4个Engine）
        """
        self.validator = validator
        self.llm_repair_fns = llm_repair_fns or []
        # 缓存修复结果，避免同一个图表在多处被重复调用LLM
        self._result_cache: Dict[str, RepairResult] = {}

    def build_cache_key(self, widget_block: Dict[str, Any]) -> str:
        """
        为图表生成稳定的缓存key，保证同样的数据不会重复触发修复。

        - 优先使用widgetId；
        - 结合数据内容的哈希，避免同ID但内容变化时误用旧结果。
        """
        widget_id = ""
        if isinstance(widget_block, dict):
            widget_id = widget_block.get('widgetId') or widget_block.get('id') or ""
        try:
            serialized = json.dumps(
                widget_block,
                ensure_ascii=False,
                sort_keys=True,
                default=str
            )
        except Exception:
            serialized = repr(widget_block)
        digest = hashlib.md5(serialized.encode('utf-8', errors='ignore')).hexdigest()
        return f"{widget_id}:{digest}"

    def repair(
        self,
        widget_block: Dict[str, Any],
        validation_result: Optional[ValidationResult] = None
    ) -> RepairResult:
        """
        尝试修复图表数据。

        Args:
            widget_block: widget类型的block
            validation_result: 验证结果（可选，如果没有会先进行验证）

        Returns:
            RepairResult: 修复结果
        """
        cache_key = self.build_cache_key(widget_block)

        cached = self._result_cache.get(cache_key)
        if cached:
            # 返回缓存的深拷贝，避免外部修改影响缓存
            return copy.deepcopy(cached)

        def _cache_and_return(res: RepairResult) -> RepairResult:
            """写入修复结果缓存并返回，避免重复调用下游修复逻辑"""
            try:
                self._result_cache[cache_key] = copy.deepcopy(res)
            except Exception:
                self._result_cache[cache_key] = res
            return res

        # 1. 如果没有验证结果，先验证
        if validation_result is None:
            validation_result = self.validator.validate(widget_block)

        # 2. 尝试本地修复（即使验证通过也尝试，因为可能有警告）
        logger.info(f"尝试本地修复图表")
        local_result = self.repair_locally(widget_block, validation_result)

        # 3. 验证修复结果
        if local_result.has_changes():
            repaired_validation = self.validator.validate(local_result.repaired_block)
            if repaired_validation.is_valid:
                logger.info(f"本地修复成功: {local_result.changes}")
                return _cache_and_return(
                    RepairResult(True, local_result.repaired_block, 'local', local_result.changes)
                )
            else:
                logger.warning(f"本地修复后仍然无效: {repaired_validation.errors}")

        # 4. 如果本地修复失败且有严重错误，尝试API修复
        if validation_result.has_critical_errors() and len(self.llm_repair_fns) > 0:
            logger.info("本地修复失败，尝试API修复")
            api_result = self.repair_with_api(widget_block, validation_result)

            if api_result.success:
                # 验证修复结果
                repaired_validation = self.validator.validate(api_result.repaired_block)
                if repaired_validation.is_valid:
                    logger.info(f"API修复成功: {api_result.changes}")
                    return _cache_and_return(api_result)
                else:
                    logger.warning(f"API修复后仍然无效: {repaired_validation.errors}")

        # 5. 如果验证通过，返回原始或修复后的数据
        if validation_result.is_valid:
            if local_result.has_changes():
                return _cache_and_return(
                    RepairResult(True, local_result.repaired_block, 'local', local_result.changes)
                )
            else:
                return _cache_and_return(RepairResult(True, widget_block, 'none', []))

        # 6. 所有修复都失败，返回原始数据
        logger.warning("所有修复尝试失败，保持原始数据")
        return _cache_and_return(RepairResult(False, widget_block, 'none', []))

    def repair_locally(
        self,
        widget_block: Dict[str, Any],
        validation_result: ValidationResult
    ) -> RepairResult:
        """
        使用本地规则修复。

        修复规则：
        1. 补全缺失的基本字段
        2. 修复数据类型错误
        3. 修复数据长度不匹配
        4. 清理无效数据
        5. 添加默认值
        """
        repaired = copy.deepcopy(widget_block)
        changes = []

        # 1. 确保基本结构存在
        if 'props' not in repaired or not isinstance(repaired.get('props'), dict):
            repaired['props'] = {}
            changes.append("添加缺失的props字段")

        if 'data' not in repaired or not isinstance(repaired.get('data'), dict):
            repaired['data'] = {}
            changes.append("添加缺失的data字段")

        # 2. 确保图表类型存在
        chart_type = self.validator._extract_chart_type(repaired)
        props = repaired['props']

        if not chart_type:
            # 尝试从widgetType推断
            widget_type = repaired.get('widgetType', '')
            if '/' in widget_type:
                chart_type = widget_type.split('/')[-1].lower()
                props['type'] = chart_type
                changes.append(f"从widgetType推断图表类型: {chart_type}")
            else:
                # 默认使用bar类型
                chart_type = 'bar'
                props['type'] = chart_type
                changes.append("设置默认图表类型: bar")
        elif 'type' not in props or not props['type']:
            # chart_type存在但props中没有type字段，需要添加
            props['type'] = chart_type
            changes.append(f"将推断的图表类型添加到props: {chart_type}")

        # 3. 修复数据结构
        data = repaired['data']

        # 确保datasets存在
        if 'datasets' not in data or not isinstance(data.get('datasets'), list):
            data['datasets'] = []
            changes.append("添加缺失的datasets字段")

        # 如果datasets为空但data中有其他数据，尝试构造datasets
        if len(data['datasets']) == 0:
            constructed = self._try_construct_datasets(data, chart_type)
            if constructed:
                data['datasets'] = constructed
                changes.append("从data中构造datasets")
            elif 'labels' in data and isinstance(data.get('labels'), list) and len(data['labels']) > 0:
                # 如果有labels但没有数据，创建一个空dataset
                data['datasets'] = [{
                    'label': '数据',
                    'data': [0] * len(data['labels'])
                }]
                changes.append("根据labels创建默认dataset（使用零值）")

        # 确保labels存在（如果需要）
        if chart_type in ChartValidator.LABEL_REQUIRED_TYPES:
            if 'labels' not in data or not isinstance(data.get('labels'), list):
                # 尝试根据datasets长度生成labels
                if data['datasets'] and len(data['datasets']) > 0:
                    first_ds = data['datasets'][0]
                    if isinstance(first_ds, dict) and isinstance(first_ds.get('data'), list):
                        data_len = len(first_ds['data'])
                        data['labels'] = [f"项目 {i+1}" for i in range(data_len)]
                        changes.append(f"生成{data_len}个默认labels")

        # 4. 修复datasets中的数据
        for idx, dataset in enumerate(data.get('datasets', [])):
            if not isinstance(dataset, dict):
                continue

            # 确保有data字段
            if 'data' not in dataset or not isinstance(dataset.get('data'), list):
                dataset['data'] = []
                changes.append(f"为datasets[{idx}]添加空data数组")

            # 确保有label
            if 'label' not in dataset:
                dataset['label'] = f"系列 {idx + 1}"
                changes.append(f"为datasets[{idx}]添加默认label")

            # 修复数据长度不匹配
            labels = data.get('labels', [])
            ds_data = dataset.get('data', [])
            if isinstance(labels, list) and isinstance(ds_data, list):
                if len(ds_data) < len(labels):
                    # 数据不够，补null
                    dataset['data'] = ds_data + [None] * (len(labels) - len(ds_data))
                    changes.append(f"datasets[{idx}]数据长度不足，补充null")
                elif len(ds_data) > len(labels):
                    # 数据过多，截断
                    dataset['data'] = ds_data[:len(labels)]
                    changes.append(f"datasets[{idx}]数据长度过长，截断")

            # 转换非数值数据为数值（如果可能）
            if chart_type in ChartValidator.NUMERIC_DATA_TYPES:
                ds_data = dataset.get('data', [])
                converted = False
                for i, value in enumerate(ds_data):
                    if value is None:
                        continue
                    if not isinstance(value, (int, float)):
                        # 尝试转换
                        try:
                            if isinstance(value, str):
                                # 尝试转换字符串
                                ds_data[i] = float(value)
                                converted = True
                        except (ValueError, TypeError):
                            # 转换失败，设为null
                            ds_data[i] = None
                            converted = True
                if converted:
                    changes.append(f"datasets[{idx}]包含非数值数据，已尝试转换")

        # 5. 验证修复结果
        success = len(changes) > 0

        return RepairResult(success, repaired, 'local', changes)

    def _try_construct_datasets(
        self,
        data: Dict[str, Any],
        chart_type: str
    ) -> Optional[List[Dict[str, Any]]]:
        """尝试从data中构造datasets"""
        # 如果data直接包含数据数组，尝试构造
        if 'values' in data and isinstance(data['values'], list):
            return [{
                'label': '数据',
                'data': data['values']
            }]

        # 如果data包含series字段
        if 'series' in data and isinstance(data['series'], list):
            datasets = []
            for idx, series in enumerate(data['series']):
                if isinstance(series, dict):
                    datasets.append({
                        'label': series.get('name', f'系列 {idx + 1}'),
                        'data': series.get('data', [])
                    })
                elif isinstance(series, list):
                    datasets.append({
                        'label': f'系列 {idx + 1}',
                        'data': series
                    })
            if datasets:
                return datasets

        return None

    def repair_with_api(
        self,
        widget_block: Dict[str, Any],
        validation_result: ValidationResult
    ) -> RepairResult:
        """
        使用API修复（调用4个Engine的LLM）。

        策略：按顺序尝试不同的Engine，直到修复成功
        """
        if not self.llm_repair_fns:
            return RepairResult(False, None, 'api', [])

        for idx, repair_fn in enumerate(self.llm_repair_fns):
            try:
                logger.info(f"尝试使用Engine {idx + 1}修复图表")
                repaired = repair_fn(widget_block, validation_result.errors)

                if repaired and isinstance(repaired, dict):
                    # 验证修复结果
                    repaired_validation = self.validator.validate(repaired)
                    if repaired_validation.is_valid:
                        return RepairResult(
                            True,
                            repaired,
                            'api',
                            [f"使用Engine {idx + 1}修复成功"]
                        )
            except Exception as e:
                logger.error(f"Engine {idx + 1}修复失败: {e}")
                continue

        return RepairResult(False, None, 'api', [])


def create_chart_validator() -> ChartValidator:
    """创建图表验证器实例"""
    return ChartValidator()


def create_chart_repairer(
    validator: Optional[ChartValidator] = None,
    llm_repair_fns: Optional[List[Callable]] = None
) -> ChartRepairer:
    """创建图表修复器实例"""
    if validator is None:
        validator = create_chart_validator()
    return ChartRepairer(validator, llm_repair_fns)

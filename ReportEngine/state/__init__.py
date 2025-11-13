"""
Report Engine状态管理模块。

导出 ReportState/ReportMetadata，供Agent与Flask接口共享。
"""

from .state import ReportState, ReportMetadata

__all__ = ["ReportState", "ReportMetadata"]

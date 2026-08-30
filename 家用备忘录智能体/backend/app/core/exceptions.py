# -*- coding: utf-8 -*-
"""
全局异常处理。
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger


class AppException(Exception):
    """业务异常基类"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code


async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.code,
        content={"detail": exc.message},
    )


async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},
    )
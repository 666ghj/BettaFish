# -*- coding: utf-8 -*-
"""
FastAPI 应用入口。
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.database import async_engine, Base
from app.core.exceptions import AppException, app_exception_handler, global_exception_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info(f"启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    # 启动时检查数据库连接
    try:
        async with async_engine.connect() as conn:
            logger.info("数据库连接成功")
    except Exception as e:
        logger.warning(f"数据库连接失败: {e}")

    # 启动提醒调度 worker
    from app.services.reminder import reminder_service
    await reminder_service.start_worker()

    yield

    # 关闭时清理
    await reminder_service.stop_worker()
    await async_engine.dispose()
    logger.info("应用已关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 异常处理
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)


# 健康检查
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


# 导入并注册路由 —— 后续各模块添加
from app.api.auth import router as auth_router
from app.api.family import router as family_router
from app.api.chat import router as chat_router
from app.api.payment import router as payment_router
from app.api.shopping import router as shopping_router
from app.api.finance import router as finance_router
from app.api.vehicle import router as vehicle_router
from app.api.anniversary import router as anniversary_router

app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(family_router, prefix="/api/family", tags=["家庭空间"])
app.include_router(chat_router, prefix="/api/chat", tags=["对话"])
app.include_router(payment_router, prefix="/api/payment", tags=["缴费"])
app.include_router(shopping_router, prefix="/api/shopping", tags=["购物清单"])
app.include_router(finance_router, prefix="/api/finance", tags=["收支记录"])
app.include_router(vehicle_router, prefix="/api/vehicle", tags=["车辆管理"])
app.include_router(anniversary_router, prefix="/api/anniversary", tags=["纪念日"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
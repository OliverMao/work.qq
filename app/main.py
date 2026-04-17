"""
FastAPI 主应用 - 企业微信消息接收
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database import init_db
from app.router import router as api_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    init_db()
    yield
    # 关闭时执行（如果有需要清理的资源，可在这里添加）

app = FastAPI(title="WeCom Message Receiver", lifespan=lifespan)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


app.include_router(api_router)



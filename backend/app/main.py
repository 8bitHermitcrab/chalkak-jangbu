import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import documents, ledger

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    # 작은 프로젝트라 마이그레이션 도구 없이 테이블을 바로 만든다. 스키마가 자주 바뀌면 Alembic 도입.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="찰칵장부 API",
    description="영수증·거래명세서 사진을 찍으면 AI가 읽어서 장부(분개)와 엑셀로 정리해 주는 서비스",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}


app.include_router(documents.router)
app.include_router(ledger.router)

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/chalkak.db"
    upload_dir: Path = Path("./data/uploads")
    max_upload_mb: int = 15
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # 추출기: auto(키가 있으면 Claude, 없으면 Tesseract) | claude | tesseract
    extractor: str = "auto"
    anthropic_api_key: str | None = None
    claude_model: str = "claude-sonnet-5-5"
    tesseract_lang: str = "kor+eng"

    # 우리 가게 정보. 거래명세서의 '공급받는자'를 거래처로 착각하지 않게 하는 데 쓴다.
    own_business_name: str | None = None
    own_business_no: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

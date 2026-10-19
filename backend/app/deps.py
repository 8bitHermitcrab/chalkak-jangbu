from functools import lru_cache

from app.config import get_settings
from app.services.extraction import ExtractionService, build_extraction_service


@lru_cache
def get_extraction_service() -> ExtractionService:
    """앱 전체에서 하나만 만든다. 테스트에서는 dependency_overrides 로 가짜 추출기를 끼운다."""
    return build_extraction_service(get_settings())

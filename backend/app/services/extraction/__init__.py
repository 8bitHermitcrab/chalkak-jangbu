"""추출 파이프라인: 사진 → (Claude 비전 또는 Tesseract) → 금액 맞추기·검증 → ExtractionResult."""
from __future__ import annotations

import logging
from typing import Protocol

from app.domain import DocType, ExtractionResult
from app.services.accounting import reconcile_amounts
from app.services.classifier import normalize_account

log = logging.getLogger(__name__)


class Extractor(Protocol):
    name: str

    def extract(self, jpeg: bytes, doc_type_hint: DocType | None = None) -> ExtractionResult: ...


class ExtractionService:
    """주 추출기가 실패하면 대체 추출기로 넘어간다. 어느 쪽이든 결과는 같은 모양."""

    def __init__(self, primary: Extractor, fallback: Extractor | None = None):
        self.primary = primary
        self.fallback = fallback

    def run(self, jpeg: bytes, doc_type_hint: DocType | None = None) -> ExtractionResult:
        notes: list[str] = []
        try:
            result = self.primary.extract(jpeg, doc_type_hint)
        except Exception as exc:  # noqa: BLE001 - 어떤 실패든 사진은 남기고 사람이 입력할 수 있어야 한다
            log.exception("primary extractor %s failed", self.primary.name)
            if self.fallback is None:
                result = ExtractionResult(doc_type=doc_type_hint or DocType.RECEIPT, extractor="manual")
                notes.append(f"자동 인식에 실패했습니다({exc.__class__.__name__}). 사진을 보고 직접 입력해 주세요.")
            else:
                notes.append(f"AI 인식에 실패해 기본 OCR로 읽었습니다({exc.__class__.__name__}). 꼼꼼히 확인해 주세요.")
                try:
                    result = self.fallback.extract(jpeg, doc_type_hint)
                except Exception as exc2:  # noqa: BLE001
                    log.exception("fallback extractor failed")
                    result = ExtractionResult(doc_type=doc_type_hint or DocType.RECEIPT, extractor="manual")
                    notes.append(f"기본 OCR도 실패했습니다({exc2.__class__.__name__}). 직접 입력해 주세요.")
        return finalize(result, notes)


def finalize(result: ExtractionResult, notes: list[str] | None = None) -> ExtractionResult:
    """추출기 종류와 상관없이 공통으로 하는 마무리: 계정 보정, 금액 채우기."""
    result.doc_type = result.doc_type or DocType.RECEIPT
    for item in result.items:
        item.account = normalize_account(item.account, item.name, result.doc_type)
    if result.total_amount is not None or result.supply_amount is not None:
        supply, vat, total, warns = reconcile_amounts(result.supply_amount, result.vat_amount, result.total_amount)
        result.supply_amount, result.vat_amount, result.total_amount = supply, vat, total
        result.warnings.extend(warns)
    if result.confidence < 0.5 and result.extractor != "manual":
        result.warnings.append("인식 신뢰도가 낮습니다. 사진과 하나씩 대조해 주세요.")
    result.warnings = (notes or []) + result.warnings
    return result


def build_extraction_service(settings) -> ExtractionService:
    from app.services.extraction.claude_vision import ClaudeVisionExtractor
    from app.services.extraction.tesseract_ocr import TesseractExtractor

    tesseract = TesseractExtractor(settings.tesseract_lang, settings.own_business_no)
    mode = settings.extractor
    if mode == "tesseract" or (mode == "auto" and not settings.anthropic_api_key):
        return ExtractionService(tesseract)
    claude = ClaudeVisionExtractor(
        settings.anthropic_api_key, settings.claude_model, settings.own_business_name, settings.own_business_no
    )
    return ExtractionService(claude, tesseract)

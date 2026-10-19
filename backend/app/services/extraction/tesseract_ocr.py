"""Tesseract OCR(한국어) + 규칙 파서. API 키 없이도 돌아가는 대체 추출기."""
from __future__ import annotations

from app.domain import DocType, ExtractionResult
from app.services.extraction.image_utils import prepare_for_ocr
from app.services.extraction.text_parser import parse_text


class TesseractExtractor:
    name = "tesseract"

    def __init__(self, lang: str = "kor+eng", own_biz_no: str | None = None):
        self.lang = lang
        self.own_biz_no = own_biz_no

    def extract(self, jpeg: bytes, doc_type_hint: DocType | None = None) -> ExtractionResult:
        import pytesseract

        # psm 6: 한 덩어리 텍스트로 보고 줄 단위로 읽는다. 영수증처럼 표가 단순한 문서에 잘 맞는다.
        text = pytesseract.image_to_string(prepare_for_ocr(jpeg), lang=self.lang, config="--psm 6")
        result = parse_text(text, doc_type_hint, self.own_biz_no)
        result.extractor = "tesseract"
        return result

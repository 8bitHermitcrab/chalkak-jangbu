from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.domain import DocStatus, DocType, JournalLine, LineItem, PaymentMethod


class DocumentUpdate(BaseModel):
    """검토 화면에서 사람이 고친 내용. items 는 통째로 교체한다."""
    doc_type: DocType
    vendor_name: str | None = None
    vendor_biz_no: str | None = None
    issue_date: date | None = None
    payment_method: PaymentMethod | None = None
    supply_amount: int = Field(0, ge=0)
    vat_amount: int = 0
    total_amount: int = Field(0, ge=0)
    memo: str | None = None
    items: list[LineItem] = Field(default_factory=list)


class DocumentOut(DocumentUpdate):
    id: int
    status: DocStatus
    image_url: str
    original_filename: str | None
    raw_text: str
    extractor: str
    confidence: float
    extraction_notes: list[str]      # 추출 당시 AI/OCR이 남긴 확인 요청
    warnings: list[str]              # 지금 내용 기준 검증 경고 (금액 불일치 등)
    journal: list[JournalLine]
    created_at: datetime | None
    confirmed_at: datetime | None


class DocumentSummary(BaseModel):
    id: int
    doc_type: DocType
    status: DocStatus
    vendor_name: str | None
    issue_date: date | None
    payment_method: PaymentMethod | None
    total_amount: int
    item_summary: str
    confidence: float
    warning_count: int
    image_url: str
    created_at: datetime | None


class UploadFailure(BaseModel):
    filename: str
    error: str


class UploadResponse(BaseModel):
    documents: list[DocumentOut]
    failures: list[UploadFailure]


class GroupTotal(BaseModel):
    key: str
    count: int
    supply_amount: int
    vat_amount: int
    total_amount: int


class LedgerSummary(BaseModel):
    pending_count: int
    confirmed_count: int
    total_amount: int
    by_month: list[GroupTotal]
    by_vendor: list[GroupTotal]
    by_account: list[GroupTotal]


class MetaOut(BaseModel):
    accounts: list[str]
    extractor: str
    own_business_name: str | None

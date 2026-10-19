"""DB·웹 프레임워크와 무관한 도메인 모델.

추출(OCR/AI) → 검토 → 분개 → 엑셀 로 이어지는 흐름의 데이터는 모두 여기 정의된
형태로 오간다. 그래서 서비스 로직은 FastAPI나 SQLAlchemy 없이도 단위 테스트할 수 있다.
"""
from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class DocType(str, Enum):
    RECEIPT = "receipt"          # 영수증 (카드/현금 영수증)
    STATEMENT = "statement"      # 거래명세서 (식자재 납품 시 받는 명세서)


class PaymentMethod(str, Enum):
    CASH = "cash"          # 현금
    CARD = "card"          # 카드
    TRANSFER = "transfer"  # 계좌이체
    CREDIT = "credit"      # 외상 (월말 결제 등)


class DocStatus(str, Enum):
    PENDING = "pending"        # 검토 필요
    CONFIRMED = "confirmed"    # 확정 (분개 완료)


DOC_TYPE_LABEL = {DocType.RECEIPT: "영수증", DocType.STATEMENT: "거래명세서"}
PAYMENT_LABEL = {
    PaymentMethod.CASH: "현금",
    PaymentMethod.CARD: "카드",
    PaymentMethod.TRANSFER: "계좌이체",
    PaymentMethod.CREDIT: "외상",
}
STATUS_LABEL = {DocStatus.PENDING: "검토 필요", DocStatus.CONFIRMED: "확정"}


class LineItem(BaseModel):
    name: str
    spec: str | None = None              # 규격 (예: 1kg, 1박스)
    quantity: float | None = None
    unit_price: int | None = None
    supply_amount: int | None = None     # 공급가액
    vat_amount: int | None = None        # 세액
    amount: int | None = None            # 금액 (공급가액+세액 또는 표기된 금액)
    account: str | None = None           # 계정과목


class ExtractionResult(BaseModel):
    """사진 한 장에서 뽑아낸 내용. 아직 사람이 확인하기 전 상태."""
    doc_type: DocType | None = None
    vendor_name: str | None = None
    vendor_biz_no: str | None = None
    issue_date: date | None = None
    payment_method: PaymentMethod | None = None
    supply_amount: int | None = None
    vat_amount: int | None = None
    total_amount: int | None = None
    items: list[LineItem] = Field(default_factory=list)
    raw_text: str = ""
    extractor: str = "manual"
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class DocumentData(BaseModel):
    """분개·엑셀 생성에 쓰는 확정 가능한 문서 내용."""
    id: int | None = None
    doc_type: DocType
    status: DocStatus = DocStatus.PENDING
    vendor_name: str | None = None
    vendor_biz_no: str | None = None
    issue_date: date | None = None
    payment_method: PaymentMethod | None = None
    supply_amount: int = 0
    vat_amount: int = 0
    total_amount: int = 0
    memo: str | None = None
    items: list[LineItem] = Field(default_factory=list)


class JournalLine(BaseModel):
    entry_date: date
    account: str
    debit: int = 0
    credit: int = 0
    description: str = ""
    document_id: int | None = None

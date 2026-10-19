from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.domain import DocStatus, DocType, DocumentData, JournalLine, LineItem, PaymentMethod


class Document(Base):
    """사진 한 장 = 문서 한 건 (영수증 또는 거래명세서)."""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=DocStatus.PENDING.value, index=True)
    image_path: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str | None] = mapped_column(String(255))

    vendor_name: Mapped[str | None] = mapped_column(String(100), index=True)
    vendor_biz_no: Mapped[str | None] = mapped_column(String(20))
    issue_date: Mapped[date | None] = mapped_column(Date, index=True)
    payment_method: Mapped[str | None] = mapped_column(String(20))
    supply_amount: Mapped[int] = mapped_column(Integer, default=0)
    vat_amount: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[int] = mapped_column(Integer, default=0)
    memo: Mapped[str | None] = mapped_column(Text)

    raw_text: Mapped[str] = mapped_column(Text, default="")
    extractor: Mapped[str] = mapped_column(String(60), default="manual")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    extraction_warnings: Mapped[str] = mapped_column(Text, default="[]")  # 추출 당시 경고(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)

    items: Mapped[list[Item]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Item.line_no"
    )
    journal_entries: Mapped[list[JournalEntry]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="JournalEntry.line_no"
    )

    @property
    def extraction_warning_list(self) -> list[str]:
        return json.loads(self.extraction_warnings or "[]")

    def to_domain(self) -> DocumentData:
        return DocumentData(
            id=self.id,
            doc_type=DocType(self.doc_type),
            status=DocStatus(self.status),
            vendor_name=self.vendor_name,
            vendor_biz_no=self.vendor_biz_no,
            issue_date=self.issue_date,
            payment_method=PaymentMethod(self.payment_method) if self.payment_method else None,
            supply_amount=self.supply_amount,
            vat_amount=self.vat_amount,
            total_amount=self.total_amount,
            memo=self.memo,
            items=[i.to_domain() for i in self.items],
        )


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    spec: Mapped[str | None] = mapped_column(String(60))
    quantity: Mapped[float | None] = mapped_column(Float)
    unit_price: Mapped[int | None] = mapped_column(Integer)
    supply_amount: Mapped[int | None] = mapped_column(Integer)
    vat_amount: Mapped[int | None] = mapped_column(Integer)
    amount: Mapped[int | None] = mapped_column(Integer)
    account: Mapped[str | None] = mapped_column(String(40))

    document: Mapped[Document] = relationship(back_populates="items")

    def to_domain(self) -> LineItem:
        return LineItem(name=self.name, spec=self.spec, quantity=self.quantity, unit_price=self.unit_price,
                        supply_amount=self.supply_amount, vat_amount=self.vat_amount, amount=self.amount,
                        account=self.account)


class JournalEntry(Base):
    """분개 한 줄. 문서를 '확정'할 때 만들어지고, 확정 취소 시 지워진다."""
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    account: Mapped[str] = mapped_column(String(40))
    debit: Mapped[int] = mapped_column(Integer, default=0)
    credit: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(255), default="")

    document: Mapped[Document] = relationship(back_populates="journal_entries")

    def to_domain(self) -> JournalLine:
        return JournalLine(entry_date=self.entry_date, account=self.account, debit=self.debit,
                           credit=self.credit, description=self.description, document_id=self.document_id)

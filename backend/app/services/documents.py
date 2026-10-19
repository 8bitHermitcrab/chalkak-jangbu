"""문서 저장·수정·확정. 라우터는 HTTP만, 여기서 DB와 도메인 로직을 잇는다."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.domain import DocStatus, DocType, DocumentData, ExtractionResult
from app.models import Document, Item, JournalEntry
from app.schemas import DocumentOut, DocumentSummary, DocumentUpdate
from app.services.accounting import build_journal, validate


def save_image(upload_dir: Path, jpeg: bytes) -> str:
    sub = datetime.now().strftime("%Y%m")
    folder = upload_dir / sub
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.jpg"
    (folder / name).write_bytes(jpeg)
    return f"{sub}/{name}"


def _set_items(doc: Document, items) -> None:
    doc.items.clear()
    for n, i in enumerate(items, start=1):
        doc.items.append(Item(line_no=n, name=i.name, spec=i.spec, quantity=i.quantity, unit_price=i.unit_price,
                              supply_amount=i.supply_amount, vat_amount=i.vat_amount, amount=i.amount,
                              account=i.account))


def create_document(db: Session, image_path: str, filename: str | None, result: ExtractionResult) -> Document:
    doc = Document(
        doc_type=(result.doc_type or DocType.RECEIPT).value,
        status=DocStatus.PENDING.value,
        image_path=image_path,
        original_filename=filename,
        vendor_name=result.vendor_name,
        vendor_biz_no=result.vendor_biz_no,
        issue_date=result.issue_date,
        payment_method=result.payment_method.value if result.payment_method else None,
        supply_amount=result.supply_amount or 0,
        vat_amount=result.vat_amount or 0,
        total_amount=result.total_amount or 0,
        raw_text=result.raw_text,
        extractor=result.extractor,
        confidence=result.confidence,
        extraction_warnings=json.dumps(result.warnings, ensure_ascii=False),
    )
    _set_items(doc, result.items)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def update_document(db: Session, doc: Document, data: DocumentUpdate) -> Document:
    doc.doc_type = data.doc_type.value
    doc.vendor_name = (data.vendor_name or "").strip() or None
    doc.vendor_biz_no = (data.vendor_biz_no or "").strip() or None
    doc.issue_date = data.issue_date
    doc.payment_method = data.payment_method.value if data.payment_method else None
    doc.supply_amount, doc.vat_amount, doc.total_amount = data.supply_amount, data.vat_amount, data.total_amount
    doc.memo = data.memo
    _set_items(doc, data.items)
    if doc.status == DocStatus.CONFIRMED.value:
        # 확정된 문서를 고치면 분개도 새 내용으로 다시 만든다. 금액이 틀어졌으면 build_journal 이 막는다.
        _write_journal(doc, doc.to_domain())
    db.commit()
    db.refresh(doc)
    return doc


def _write_journal(doc: Document, data: DocumentData) -> None:
    lines = build_journal(data)
    doc.journal_entries.clear()
    for n, line in enumerate(lines, start=1):
        doc.journal_entries.append(JournalEntry(line_no=n, entry_date=line.entry_date, account=line.account,
                                                debit=line.debit, credit=line.credit,
                                                description=line.description))


def confirm_document(db: Session, doc: Document) -> Document:
    _write_journal(doc, doc.to_domain())
    doc.status = DocStatus.CONFIRMED.value
    doc.confirmed_at = datetime.now()
    db.commit()
    db.refresh(doc)
    return doc


def unconfirm_document(db: Session, doc: Document) -> Document:
    doc.journal_entries.clear()
    doc.status = DocStatus.PENDING.value
    doc.confirmed_at = None
    db.commit()
    db.refresh(doc)
    return doc


def image_url(doc: Document) -> str:
    return f"/api/documents/{doc.id}/image"


def to_out(doc: Document) -> DocumentOut:
    data = doc.to_domain()
    return DocumentOut(
        **data.model_dump(exclude={"id", "status"}),
        id=doc.id,
        status=DocStatus(doc.status),
        image_url=image_url(doc),
        original_filename=doc.original_filename,
        raw_text=doc.raw_text,
        extractor=doc.extractor,
        confidence=doc.confidence,
        extraction_notes=doc.extraction_warning_list,
        warnings=validate(data),
        journal=[j.to_domain() for j in doc.journal_entries],
        created_at=doc.created_at,
        confirmed_at=doc.confirmed_at,
    )


def to_summary(doc: Document) -> DocumentSummary:
    data = doc.to_domain()
    names = [i.name for i in data.items]
    return DocumentSummary(
        id=doc.id,
        doc_type=data.doc_type,
        status=data.status,
        vendor_name=data.vendor_name,
        issue_date=data.issue_date,
        payment_method=data.payment_method,
        total_amount=data.total_amount,
        item_summary=(names[0] + (f" 외 {len(names) - 1}건" if len(names) > 1 else "")) if names else "",
        confidence=doc.confidence,
        warning_count=len(validate(data)),
        image_url=image_url(doc),
        created_at=doc.created_at,
    )

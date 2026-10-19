from __future__ import annotations

from collections import defaultdict
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.database import get_db
from app.domain import DocStatus, JournalLine
from app.models import Document, JournalEntry
from app.schemas import GroupTotal, LedgerSummary, MetaOut
from app.services.accounting import item_supply
from app.services.classifier import EXPENSE_ACCOUNTS
from app.services.excel_export import build_workbook

router = APIRouter(prefix="/api", tags=["ledger"])


def _documents(db: Session, start: date | None, end: date | None, status: DocStatus | None) -> list[Document]:
    q = select(Document).options(selectinload(Document.items), selectinload(Document.journal_entries))
    if start:
        q = q.where(Document.issue_date >= start)
    if end:
        q = q.where(Document.issue_date <= end)
    if status:
        q = q.where(Document.status == status.value)
    return list(db.scalars(q).all())


@router.get("/meta", response_model=MetaOut)
def meta(settings: Settings = Depends(get_settings)):
    mode = settings.extractor
    if mode == "auto":
        mode = "claude" if settings.anthropic_api_key else "tesseract"
    return MetaOut(accounts=EXPENSE_ACCOUNTS, extractor=mode, own_business_name=settings.own_business_name)


@router.get("/vendors", response_model=list[str], summary="거래처 자동완성")
def vendors(db: Session = Depends(get_db)):
    rows = db.scalars(select(Document.vendor_name).where(Document.vendor_name.is_not(None)).distinct())
    return sorted(rows.all())


@router.get("/journal", response_model=list[JournalLine], summary="분개장")
def journal(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)):
    q = select(JournalEntry)
    if start:
        q = q.where(JournalEntry.entry_date >= start)
    if end:
        q = q.where(JournalEntry.entry_date <= end)
    q = q.order_by(JournalEntry.entry_date, JournalEntry.document_id, JournalEntry.line_no)
    return [e.to_domain() for e in db.scalars(q).all()]


def _group(rows: dict[str, list[int]]) -> list[GroupTotal]:
    return [GroupTotal(key=k, count=v[0], supply_amount=v[1], vat_amount=v[2], total_amount=v[3])
            for k, v in rows.items()]


@router.get("/summary", response_model=LedgerSummary, summary="월별·거래처별·계정별 집계 (확정분)")
def summary(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)):
    docs = _documents(db, start, end, None)
    confirmed = [d.to_domain() for d in docs if d.status == DocStatus.CONFIRMED.value]
    by_month: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    by_vendor: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    by_account: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for d in confirmed:
        for key, bucket in (((d.issue_date.strftime("%Y-%m") if d.issue_date else "날짜 없음"), by_month),
                            (d.vendor_name or "거래처 미상", by_vendor)):
            b = bucket[key]
            b[0] += 1
            b[1] += d.supply_amount
            b[2] += d.vat_amount
            b[3] += d.total_amount
        for i in d.items:
            b = by_account[i.account or "미분류"]
            s = item_supply(i, d.vat_amount > 0)
            b[0] += 1
            b[1] += s
            b[3] += s
    return LedgerSummary(
        pending_count=sum(d.status == DocStatus.PENDING.value for d in docs),
        confirmed_count=len(confirmed),
        total_amount=sum(d.total_amount for d in confirmed),
        by_month=sorted(_group(by_month), key=lambda g: g.key),
        by_vendor=sorted(_group(by_vendor), key=lambda g: -g.total_amount),
        by_account=sorted(_group(by_account), key=lambda g: -g.supply_amount),
    )


@router.get("/export/excel", summary="엑셀 다운로드")
def export_excel(
    start: date | None = None,
    end: date | None = None,
    include_pending: bool = Query(False, description="검토 전 문서도 포함"),
    db: Session = Depends(get_db),
):
    docs = _documents(db, start, end, None if include_pending else DocStatus.CONFIRMED)
    journal_lines = [e.to_domain() for d in docs for e in d.journal_entries]
    content = build_workbook([d.to_domain() for d in docs], journal_lines, (start, end))
    label = f"{start or '전체'}_{end or date.today()}"
    filename = quote(f"찰칵장부_{label}.xlsx")
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )

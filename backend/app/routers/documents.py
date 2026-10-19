from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.deps import get_extraction_service
from app.domain import DocStatus, DocType
from app.models import Document
from app.schemas import DocumentOut, DocumentSummary, DocumentUpdate, UploadFailure, UploadResponse
from app.services import documents as svc
from app.services.accounting import AccountingError
from app.services.extraction import ExtractionService
from app.services.extraction.image_utils import InvalidImageError, normalize_image

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _get(db: Session, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    return doc


@router.post("", response_model=UploadResponse, summary="사진 업로드 → 자동 인식")
def upload(
    files: list[UploadFile] = File(..., description="영수증·거래명세서 사진 (여러 장 가능)"),
    doc_type: DocType | None = Form(None, description="비워 두면 자동 판별"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    extraction: ExtractionService = Depends(get_extraction_service),
):
    """하루치 명세서를 한꺼번에 올려도 된다. 한 장이 실패해도 나머지는 저장된다."""
    created, failures = [], []
    limit = settings.max_upload_mb * 1024 * 1024
    for f in files:
        name = f.filename or "photo"
        data = f.file.read(limit + 1)
        if len(data) > limit:
            failures.append(UploadFailure(filename=name, error=f"{settings.max_upload_mb}MB를 넘는 파일입니다."))
            continue
        try:
            jpeg = normalize_image(data)
        except InvalidImageError as exc:
            failures.append(UploadFailure(filename=name, error=str(exc)))
            continue
        path = svc.save_image(settings.upload_dir, jpeg)
        result = extraction.run(jpeg, doc_type)
        created.append(svc.to_out(svc.create_document(db, path, name, result)))
    if not created and failures:
        raise HTTPException(400, failures[0].error)
    return UploadResponse(documents=created, failures=failures)


@router.get("", response_model=list[DocumentSummary], summary="문서 목록")
def list_documents(
    status: DocStatus | None = None,
    doc_type: DocType | None = None,
    vendor: str | None = Query(None, description="거래처명 일부"),
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
):
    q = select(Document)
    if status:
        q = q.where(Document.status == status.value)
    if doc_type:
        q = q.where(Document.doc_type == doc_type.value)
    if vendor:
        q = q.where(Document.vendor_name.contains(vendor))
    if start:
        q = q.where(Document.issue_date >= start)
    if end:
        q = q.where(Document.issue_date <= end)
    q = q.order_by(Document.issue_date.desc().nulls_first(), Document.id.desc())
    return [svc.to_summary(d) for d in db.scalars(q).all()]


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    return svc.to_out(_get(db, doc_id))


@router.get("/{doc_id}/image", response_class=FileResponse)
def get_image(doc_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    doc = _get(db, doc_id)
    path = (settings.upload_dir / doc.image_path).resolve()
    if not path.is_relative_to(settings.upload_dir.resolve()) or not path.exists():
        raise HTTPException(404, "사진 파일이 없습니다.")
    return FileResponse(path, media_type="image/jpeg")


@router.put("/{doc_id}", response_model=DocumentOut, summary="검토 후 수정")
def update_document(doc_id: int, data: DocumentUpdate, db: Session = Depends(get_db)):
    doc = _get(db, doc_id)
    try:
        return svc.to_out(svc.update_document(db, doc, data))
    except AccountingError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.post("/{doc_id}/confirm", response_model=DocumentOut, summary="확정 (분개 생성)")
def confirm(doc_id: int, db: Session = Depends(get_db)):
    doc = _get(db, doc_id)
    try:
        return svc.to_out(svc.confirm_document(db, doc))
    except AccountingError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.post("/{doc_id}/unconfirm", response_model=DocumentOut, summary="확정 취소 (분개 삭제)")
def unconfirm(doc_id: int, db: Session = Depends(get_db)):
    return svc.to_out(svc.unconfirm_document(db, _get(db, doc_id)))


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    doc = _get(db, doc_id)
    path = settings.upload_dir / doc.image_path
    db.delete(doc)
    db.commit()
    path.unlink(missing_ok=True)

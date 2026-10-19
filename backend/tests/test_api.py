"""API 흐름 테스트: 업로드 → 검토 수정 → 확정(분개) → 집계 → 엑셀.

추출기는 가짜로 바꿔 끼우므로 API 키나 Tesseract 없이 돈다.
실행: docker compose run --rm backend pytest
"""
import io
import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp()

from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from PIL import Image  # noqa: E402

from app.deps import get_extraction_service  # noqa: E402
from app.domain import DocType, ExtractionResult, LineItem, PaymentMethod  # noqa: E402
from app.main import app  # noqa: E402
from app.services.extraction import ExtractionService  # noqa: E402


class FakeExtractor:
    name = "fake"

    def extract(self, jpeg, doc_type_hint=None):
        return ExtractionResult(
            doc_type=DocType.STATEMENT, vendor_name="한돈유통", payment_method=PaymentMethod.CREDIT,
            supply_amount=260_000, vat_amount=0, total_amount=260_000, extractor="fake", confidence=0.9,
            items=[LineItem(name="삼겹살", quantity=10, unit_price=18_000, supply_amount=180_000),
                   LineItem(name="목살", quantity=5, unit_price=16_000, supply_amount=80_000)],
        )


app.dependency_overrides[get_extraction_service] = lambda: ExtractionService(FakeExtractor())


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (400, 600), "white").save(buf, format="JPEG")
    return buf.getvalue()


def test_full_flow():
    with TestClient(app) as client:
        res = client.post("/api/documents", files=[
            ("files", ("a.jpg", _jpeg(), "image/jpeg")),
            ("files", ("broken.jpg", b"not an image", "image/jpeg")),
        ])
        assert res.status_code == 200, res.text
        body = res.json()
        assert len(body["documents"]) == 1 and len(body["failures"]) == 1
        doc = body["documents"][0]
        assert doc["status"] == "pending"
        assert "거래일자가 비어 있습니다." in doc["warnings"]

        assert client.get(doc["image_url"]).status_code == 200

        # 사람이 사진을 보고 날짜를 채워 넣는다
        update = {k: doc[k] for k in ("doc_type", "vendor_name", "vendor_biz_no", "payment_method",
                                      "supply_amount", "vat_amount", "total_amount", "memo", "items")}
        update["issue_date"] = "2025-10-03"
        res = client.put(f"/api/documents/{doc['id']}", json=update)
        assert res.status_code == 200 and res.json()["warnings"] == []

        res = client.post(f"/api/documents/{doc['id']}/confirm")
        assert res.status_code == 200
        journal = res.json()["journal"]
        assert sum(l["debit"] for l in journal) == sum(l["credit"] for l in journal) == 260_000

        # 확정 후 금액을 틀리게 고치면 거부된다 (장부가 깨지지 않도록)
        bad = dict(update, total_amount=999)
        assert client.put(f"/api/documents/{doc['id']}", json=bad).status_code == 422

        summary = client.get("/api/summary").json()
        assert summary["confirmed_count"] == 1 and summary["total_amount"] == 260_000
        assert summary["by_vendor"][0]["key"] == "한돈유통"

        res = client.get("/api/export/excel")
        assert res.status_code == 200
        wb = load_workbook(io.BytesIO(res.content))
        assert wb["거래내역"]["D2"].value == "한돈유통"

        assert client.post(f"/api/documents/{doc['id']}/unconfirm").json()["journal"] == []
        assert client.delete(f"/api/documents/{doc['id']}").status_code == 204
        assert client.get(f"/api/documents/{doc['id']}").status_code == 404

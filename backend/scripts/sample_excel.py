"""예시 장부 엑셀 만들기 (DB·API 없이). 고깃집 한 달치 매입을 흉내 낸 데이터.

실행: python -m scripts.sample_excel 찰칵장부_예시.xlsx
"""
import sys
from datetime import date

from app.domain import DocStatus, DocType, DocumentData, LineItem, PaymentMethod
from app.services.accounting import build_journal
from app.services.classifier import classify_item
from app.services.excel_export import build_workbook


def make(doc_id, doc_type, vendor, day, payment, rows):
    items = [
        LineItem(name=name, quantity=q, unit_price=p, supply_amount=round(q * p), vat_amount=vat,
                 account=classify_item(name, doc_type)[0])
        for name, q, p, vat in rows
    ]
    supply = sum(i.supply_amount for i in items)
    vat = sum(i.vat_amount for i in items)
    return DocumentData(id=doc_id, doc_type=doc_type, status=DocStatus.CONFIRMED, vendor_name=vendor,
                        issue_date=day, payment_method=payment, supply_amount=supply, vat_amount=vat,
                        total_amount=supply + vat, items=items)


S, R = DocType.STATEMENT, DocType.RECEIPT
DOCS = [
    make(1, S, "한돈유통", date(2025, 10, 3), PaymentMethod.CREDIT,
         [("삼겹살", 10, 18000, 0), ("목살", 5, 16000, 0), ("쌈장", 2, 6500, 1300)]),
    make(2, S, "가락채소", date(2025, 10, 3), PaymentMethod.CREDIT,
         [("상추 4kg", 2, 12000, 0), ("깻잎", 3, 8000, 0), ("대파", 2, 5000, 0)]),
    make(3, S, "한빛주류", date(2025, 10, 4), PaymentMethod.TRANSFER,
         [("참이슬", 40, 1400, 5600), ("카스", 24, 1700, 4080)]),
    make(4, R, "다이소 망원점", date(2025, 10, 5), PaymentMethod.CARD,
         [("쿠킹호일", 2, 2727, 546), ("위생장갑", 1, 1818, 182)]),
    make(5, S, "참숯상회", date(2025, 10, 7), PaymentMethod.CASH, [("참숯 10kg", 3, 25000, 7500)]),
    make(6, S, "한돈유통", date(2025, 10, 10), PaymentMethod.CREDIT,
         [("항정살", 4, 32000, 0), ("갈매기살", 3, 28000, 0)]),
]

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "찰칵장부_예시.xlsx"
    journal = [line for d in DOCS for line in build_journal(d)]
    with open(out, "wb") as f:
        f.write(build_workbook(DOCS, journal, (date(2025, 10, 1), date(2025, 10, 31))))
    print(f"{out}: 문서 {len(DOCS)}건, 분개 {len(journal)}줄")

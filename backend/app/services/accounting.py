"""회계 처리: 금액 맞추기, 검증, 분개 생성.

매입 한 건은 이렇게 분개한다.

    (차) 원재료(식자재) 등 비용 계정   공급가액   ← 품목별 계정과목으로 나눠서
    (차) 부가세대급금                  세액
        (대) 현금 / 미지급금 / 보통예금 / 외상매입금   합계

외상으로 받은 식자재 거래명세서는 '외상매입금', 카드 결제는 '미지급금(카드)' 로 잡는다.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import date

from app.domain import DOC_TYPE_LABEL, DocType, DocumentData, JournalLine, LineItem, PaymentMethod
from app.services.classifier import ACCOUNT_DRINK, ACCOUNT_FOOD, default_account

ACCOUNT_VAT = "부가세대급금"
CREDIT_ACCOUNTS = {
    PaymentMethod.CASH: "현금",
    PaymentMethod.CARD: "미지급금(카드)",
    PaymentMethod.TRANSFER: "보통예금",
}
ACCOUNT_TRADE_PAYABLE = "외상매입금"   # 식자재 등 원재료를 외상으로 산 경우
ACCOUNT_OTHER_PAYABLE = "미지급금"     # 그 밖의 외상

# 품목 합계와 문서 공급가액이 이 정도까지 다르면 단수(원 단위 반올림) 차이로 보고 조용히 맞춘다.
ROUNDING_TOLERANCE = 10


class AccountingError(ValueError):
    """확정할 수 없는 상태(금액 불일치 등)."""


def reconcile_amounts(
    supply: int | None, vat: int | None, total: int | None
) -> tuple[int, int, int, list[str]]:
    """공급가액·세액·합계 중 비어 있는 값을 나머지로 채운다."""
    warnings: list[str] = []
    if total is not None and supply is not None and vat is None:
        vat = total - supply
    elif total is not None and vat is not None and supply is None:
        supply = total - vat
    elif supply is not None and vat is not None and total is None:
        total = supply + vat
    elif total is not None and supply is None and vat is None:
        supply, vat = total, 0
        warnings.append("부가세가 따로 표시되지 않아 합계 전체를 공급가액으로 잡았습니다. 과세 거래라면 세액을 입력해 주세요.")
    elif supply is not None and vat is None and total is None:
        vat, total = 0, supply
    supply, vat, total = supply or 0, vat or 0, total or 0
    if supply + vat != total:
        warnings.append(f"공급가액({supply:,}) + 세액({vat:,}) 이 합계({total:,}) 와 다릅니다.")
    return supply, vat, total, warnings


def item_supply(item: LineItem, doc_has_vat: bool) -> int:
    """품목의 공급가액. 비어 있으면 금액이나 수량×단가로 추정한다."""
    if item.supply_amount is not None:
        return item.supply_amount
    if item.amount is not None:
        if item.vat_amount is not None:
            return item.amount - item.vat_amount
        # 문서에 세액이 따로 있는데 품목엔 금액만 있으면 부가세 포함 금액으로 본다.
        return round(item.amount * 10 / 11) if doc_has_vat else item.amount
    if item.quantity is not None and item.unit_price is not None:
        return round(item.quantity * item.unit_price)
    return 0


def validate(doc: DocumentData) -> list[str]:
    """검토 화면에 띄울 경고 목록. 비어 있으면 바로 확정해도 된다."""
    warnings: list[str] = []
    if not doc.vendor_name:
        warnings.append("거래처명이 비어 있습니다.")
    if doc.issue_date is None:
        warnings.append("거래일자가 비어 있습니다.")
    if doc.total_amount <= 0:
        warnings.append("합계 금액이 0원입니다.")
    if doc.supply_amount + doc.vat_amount != doc.total_amount:
        warnings.append(
            f"공급가액({doc.supply_amount:,}) + 세액({doc.vat_amount:,}) ≠ 합계({doc.total_amount:,})"
        )
    if doc.items:
        items_sum = sum(item_supply(i, doc.vat_amount > 0) for i in doc.items)
        diff = doc.supply_amount - items_sum
        if abs(diff) > ROUNDING_TOLERANCE:
            warnings.append(
                f"품목 공급가액 합({items_sum:,})이 문서 공급가액({doc.supply_amount:,})과 {diff:+,}원 차이 납니다."
            )
        for idx, item in enumerate(doc.items, start=1):
            if item.quantity is not None and item.unit_price is not None and item.supply_amount is not None:
                expected = round(item.quantity * item.unit_price)
                if abs(expected - item.supply_amount) > ROUNDING_TOLERANCE:
                    warnings.append(
                        f"{idx}번 품목 '{item.name}': 수량×단가({expected:,})와 공급가액({item.supply_amount:,})이 다릅니다."
                    )
    return warnings


def credit_account(doc: DocumentData, debit_accounts: list[str]) -> str:
    method = doc.payment_method or (
        PaymentMethod.CREDIT if doc.doc_type == DocType.STATEMENT else PaymentMethod.CARD
    )
    if method in CREDIT_ACCOUNTS:
        return CREDIT_ACCOUNTS[method]
    is_raw_material = any(a in (ACCOUNT_FOOD, ACCOUNT_DRINK) for a in debit_accounts)
    return ACCOUNT_TRADE_PAYABLE if is_raw_material else ACCOUNT_OTHER_PAYABLE


def describe(doc: DocumentData) -> str:
    """적요: '한돈유통 거래명세서 - 삼겹살 외 3건'"""
    parts = [doc.vendor_name or "거래처 미상", DOC_TYPE_LABEL[doc.doc_type]]
    text = " ".join(parts)
    names = [i.name for i in doc.items if i.name]
    if names:
        text += f" - {names[0]}" + (f" 외 {len(names) - 1}건" if len(names) > 1 else "")
    return text


def build_journal(doc: DocumentData) -> list[JournalLine]:
    """확정할 문서 한 건의 분개를 만든다. 차변 합계 = 대변 합계가 보장된다."""
    if doc.total_amount <= 0:
        raise AccountingError("합계 금액이 0원이라 분개할 수 없습니다.")
    if doc.supply_amount + doc.vat_amount != doc.total_amount:
        raise AccountingError("공급가액 + 세액이 합계와 맞지 않아 분개할 수 없습니다. 금액을 먼저 고쳐 주세요.")

    entry_date = doc.issue_date or date.today()
    description = describe(doc)

    # 1) 품목을 계정과목별로 묶어 차변 금액을 만든다.
    by_account: OrderedDict[str, int] = OrderedDict()
    for item in doc.items:
        account = item.account or default_account(doc.doc_type)
        by_account[account] = by_account.get(account, 0) + item_supply(item, doc.vat_amount > 0)
    if not by_account or sum(by_account.values()) == 0:
        by_account = OrderedDict({default_account(doc.doc_type): doc.supply_amount})

    # 2) 품목 합과 문서 공급가액의 차이(반올림·할인 등)는 가장 큰 계정에 붙여 대차를 맞춘다.
    diff = doc.supply_amount - sum(by_account.values())
    if diff:
        largest = max(by_account, key=lambda a: by_account[a])
        by_account[largest] += diff

    lines = [
        JournalLine(entry_date=entry_date, account=a, debit=amt, description=description, document_id=doc.id)
        for a, amt in by_account.items()
        if amt != 0
    ]
    if doc.vat_amount:
        lines.append(JournalLine(entry_date=entry_date, account=ACCOUNT_VAT, debit=doc.vat_amount,
                                 description=description, document_id=doc.id))
    lines.append(JournalLine(entry_date=entry_date, account=credit_account(doc, list(by_account)),
                             credit=doc.total_amount, description=description, document_id=doc.id))

    debit_total = sum(l.debit for l in lines)
    credit_total = sum(l.credit for l in lines)
    if debit_total != credit_total:  # 위 로직상 일어나면 안 되지만, 장부가 틀어지는 것보다는 멈추는 게 낫다.
        raise AccountingError(f"대차 불일치: 차변 {debit_total:,} / 대변 {credit_total:,}")
    return lines

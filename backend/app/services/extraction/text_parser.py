"""OCR로 얻은 날것의 텍스트에서 영수증/거래명세서 항목을 규칙으로 뽑아낸다.

Claude 비전 모델을 쓸 수 없을 때(API 키가 없거나 호출 실패) 쓰는 대체 경로다.
완벽하지 않으므로 결과는 항상 '검토 필요' 상태로 저장되고, 사람이 화면에서 고친다.
"""
from __future__ import annotations

import re
from datetime import date

from app.domain import DocType, ExtractionResult, LineItem, PaymentMethod
from app.services.classifier import classify_item

_NUM = r"-?\d{1,3}(?:[,.]\d{3})+|-?\d+"
_DATE_RE = re.compile(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")
_SHORT_DATE_RE = re.compile(r"(?<!\d)(\d{2})[.\-/](\d{2})[.\-/](\d{2})(?!\d)")
_BIZ_RE = re.compile(r"(\d{3})\s*-\s*(\d{2})\s*-\s*(\d{5})")
_ITEM_RE = re.compile(
    rf"^(?P<name>[가-힣A-Za-z(][^\d]*?(?:\d+\s*(?:kg|g|개|팩|박스|병|ea|EA)\s*)?)\s+"
    rf"(?P<qty>\d+(?:\.\d+)?)\s+(?P<price>{_NUM})\s+(?P<amount>{_NUM})(?:\s+(?P<vat>{_NUM}))?\s*$"
)

_TOTAL_KEYS = ("받을금액", "결제금액", "합계금액", "총합계", "총금액", "총액", "합계", "청구금액", "판매금액")
_SUPPLY_KEYS = ("공급가액", "과세물품가액", "과세금액", "공급가")
_VAT_KEYS = ("부가세", "부가가치세", "세액")
_SKIP_ITEM_KEYS = _TOTAL_KEYS + _SUPPLY_KEYS + _VAT_KEYS + ("소계", "카드", "승인", "거스름", "받은금액", "면세")


def parse_int(text: str) -> int | None:
    cleaned = re.sub(r"[^\d\-]", "", text.replace("O", "0").replace("o", "0"))
    if not cleaned or cleaned == "-":
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _numbers(line: str) -> list[int]:
    return [n for n in (parse_int(m) for m in re.findall(_NUM, line)) if n is not None]


def _compact(line: str) -> str:
    return re.sub(r"\s+", "", line)


def _amount_after_key(lines: list[str], keys: tuple[str, ...]) -> int | None:
    """키워드가 있는 줄(없으면 바로 다음 줄)의 마지막 숫자. 아래쪽 값을 우선한다(최종 합계)."""
    found: int | None = None
    for i, line in enumerate(lines):
        compact = _compact(line)
        if any(k in compact for k in keys):
            after = line
            for k in keys:
                idx = compact.find(k)
                if idx >= 0:
                    # 키워드 뒤쪽 숫자만 본다 (키워드 앞 '2' 같은 번호 무시)
                    after = compact[idx + len(k):]
                    break
            nums = [n for n in _numbers(after) if abs(n) >= 10]
            # 값이 다음 줄에 있는 양식도 있다. 단, 다음 줄이 '삼겹살 10 18,000 ...' 같은
            # 품목 줄이면 지금 줄은 표 머리글이므로 건너뛴다.
            if not nums and i + 1 < len(lines) and not re.search(r"[가-힣A-Za-z]", lines[i + 1]):
                nums = [n for n in _numbers(lines[i + 1]) if abs(n) >= 10]
            if nums:
                found = nums[-1]
    return found


def _find_date(text: str) -> date | None:
    for m in _DATE_RE.finditer(text):
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
    for m in _SHORT_DATE_RE.finditer(text):
        try:
            return date(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
    return None


def _find_vendor(lines: list[str], own_biz_no: str | None) -> tuple[str | None, str | None]:
    """공급자(파는 쪽) 상호와 사업자번호를 찾는다.

    거래명세서에는 공급자와 공급받는자(우리 가게)가 같이 적혀 있어서,
    가게 자신의 사업자번호(OWN_BUSINESS_NO)는 후보에서 뺀다.
    """
    own = re.sub(r"\D", "", own_biz_no or "")
    biz_candidates: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        for m in _BIZ_RE.finditer(line):
            no = "-".join(m.groups())
            if own and no.replace("-", "") == own:
                continue
            biz_candidates.append((i, no))

    # '공급자' 라벨 근처의 번호를 우선한다.
    biz_no = None
    for i, line in enumerate(lines):
        if "공급자" in _compact(line) and "받는" not in _compact(line):
            near = [no for j, no in biz_candidates if i <= j <= i + 2]
            if near:
                biz_no = near[0]
                break
    if biz_no is None and biz_candidates:
        biz_no = biz_candidates[0][1]

    name = None
    for line in lines:
        m = re.search(r"(?:상\s*호|업체명|가맹점명?|거래처)\s*(?:\(.*?\))?\s*[:：]?\s*([^\s:：|][^|:：]{0,25})", line)
        if m:
            candidate = re.split(r"\s{2,}|대표|성명|사업자", m.group(1))[0].strip()
            if candidate and "받는" not in candidate:
                name = candidate
                break
    if name is None:
        for line in lines:
            stripped = line.strip()
            if (
                len(stripped) >= 2
                and re.search(r"[가-힣]", stripped)
                and not any(k in stripped for k in ("영수증", "거래명세", "명세표", "계산서"))
                and not _DATE_RE.search(stripped)
            ):
                name = stripped[:30]
                break
    return name, biz_no


def _find_payment(text: str, doc_type: DocType) -> PaymentMethod:
    compact = _compact(text)
    if any(k in compact for k in ("신용카드", "카드승인", "승인번호", "카드번호", "체크카드")):
        return PaymentMethod.CARD
    if any(k in compact for k in ("계좌이체", "무통장", "이체")):
        return PaymentMethod.TRANSFER
    if any(k in compact for k in ("현금영수증", "현금")):
        return PaymentMethod.CASH
    if any(k in compact for k in ("외상", "미수", "전잔액", "미결제")):
        return PaymentMethod.CREDIT
    return PaymentMethod.CREDIT if doc_type == DocType.STATEMENT else PaymentMethod.CARD


def _find_items(lines: list[str], doc_type: DocType) -> list[LineItem]:
    items: list[LineItem] = []
    for line in lines:
        compact = _compact(line)
        if any(k in compact for k in _SKIP_ITEM_KEYS):
            continue
        m = _ITEM_RE.match(line.strip())
        if not m:
            continue
        qty = float(m.group("qty"))
        price = parse_int(m.group("price"))
        amount = parse_int(m.group("amount"))
        vat = parse_int(m.group("vat")) if m.group("vat") else None
        if price is None or amount is None:
            continue
        # 수량×단가가 금액과 크게 다르면 품목 줄이 아니라고 본다 (전화번호, 날짜 등 오탐 방지)
        if price and abs(qty * price - amount) > max(10, amount * 0.02):
            continue
        name = m.group("name").strip(" .:-")
        items.append(
            LineItem(
                name=name,
                quantity=qty,
                unit_price=price,
                supply_amount=amount if vat is not None or doc_type == DocType.STATEMENT else None,
                vat_amount=vat,
                amount=amount + (vat or 0) if vat is not None else amount,
                account=classify_item(name, doc_type)[0],
            )
        )
    return items


def guess_doc_type(text: str) -> DocType:
    compact = _compact(text)
    if any(k in compact for k in ("거래명세", "명세표", "납품", "공급받는자")):
        return DocType.STATEMENT
    return DocType.RECEIPT


def parse_text(text: str, doc_type: DocType | None = None, own_biz_no: str | None = None) -> ExtractionResult:
    lines = [l for l in text.splitlines() if l.strip()]
    doc_type = doc_type or guess_doc_type(text)
    vendor, biz_no = _find_vendor(lines, own_biz_no)
    items = _find_items(lines, doc_type)

    total = _amount_after_key(lines, _TOTAL_KEYS)
    supply = _amount_after_key(lines, _SUPPLY_KEYS)
    vat = _amount_after_key(lines, _VAT_KEYS)
    if total is None and items:
        total = sum((i.amount or 0) for i in items)

    found = sum(x is not None for x in (vendor, biz_no, _find_date(text), total)) + (1 if items else 0)
    return ExtractionResult(
        doc_type=doc_type,
        vendor_name=vendor,
        vendor_biz_no=biz_no,
        issue_date=_find_date(text),
        payment_method=_find_payment(text, doc_type),
        supply_amount=supply,
        vat_amount=vat,
        total_amount=total,
        items=items,
        raw_text=text,
        extractor="rule",
        confidence=round(found / 5 * 0.7, 2),  # 규칙 기반은 아무리 잘 맞아도 0.7을 넘기지 않게 둔다
    )

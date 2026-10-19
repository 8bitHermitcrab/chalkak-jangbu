"""Claude 비전 모델로 영수증/거래명세서 사진을 바로 구조화된 데이터로 읽는다.

손글씨 거래명세서, 구겨진 영수증, 비스듬히 찍은 사진처럼 OCR+규칙으로는 잘 안 되는 경우를
처리하려고 쓰는 주 추출기다. 응답 형식을 툴 스키마로 강제해서 JSON 파싱 실패를 막는다.
"""
from __future__ import annotations

import base64
from datetime import date

from app.domain import DocType, ExtractionResult, LineItem, PaymentMethod
from app.services.classifier import EXPENSE_ACCOUNTS, normalize_account

TOOL_NAME = "record_document"

_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "품목명 그대로 (예: 한돈 삼겹살)"},
        "spec": {"type": ["string", "null"], "description": "규격/단위 (예: 1kg, 1box)"},
        "quantity": {"type": ["number", "null"]},
        "unit_price": {"type": ["integer", "null"], "description": "단가(원)"},
        "supply_amount": {"type": ["integer", "null"], "description": "공급가액(원). 표에 있을 때만"},
        "vat_amount": {"type": ["integer", "null"], "description": "세액(원). 표에 있을 때만"},
        "amount": {"type": ["integer", "null"], "description": "그 줄의 금액(원)"},
        "account": {"type": "string", "enum": EXPENSE_ACCOUNTS},
    },
    "required": ["name", "account"],
}

TOOL = {
    "name": TOOL_NAME,
    "description": "사진에서 읽은 영수증/거래명세서 내용을 기록한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "doc_type": {"type": "string", "enum": ["receipt", "statement"],
                         "description": "receipt=영수증, statement=거래명세서/명세표"},
            "vendor_name": {"type": ["string", "null"], "description": "공급자(판매자) 상호"},
            "vendor_biz_no": {"type": ["string", "null"], "description": "공급자 사업자등록번호 000-00-00000"},
            "issue_date": {"type": ["string", "null"], "description": "거래일자 YYYY-MM-DD"},
            "payment_method": {"type": ["string", "null"], "enum": ["cash", "card", "transfer", "credit", None]},
            "supply_amount": {"type": ["integer", "null"]},
            "vat_amount": {"type": ["integer", "null"]},
            "total_amount": {"type": ["integer", "null"], "description": "최종 합계(원)"},
            "items": {"type": "array", "items": _ITEM_SCHEMA},
            "raw_text": {"type": "string", "description": "사진에 보이는 글자를 줄 단위로 옮겨 적은 것"},
            "confidence": {"type": "number", "description": "0~1, 사진이 흐리거나 잘렸으면 낮게"},
            "notes": {"type": "array", "items": {"type": "string"},
                      "description": "사람이 꼭 확인해야 할 부분 (안 읽히는 글자, 계산 안 맞는 줄 등)"},
        },
        "required": ["doc_type", "items", "raw_text", "confidence"],
    },
}


def build_prompt(doc_type_hint: DocType | None, own_business_name: str | None, own_biz_no: str | None) -> str:
    lines = [
        "음식점(고깃집)에서 받은 영수증 또는 거래명세서 사진입니다. 장부 입력용으로 내용을 정확히 읽어 주세요.",
        "",
        "규칙:",
        "- 금액은 원 단위 정수로. 쉼표·'원' 은 빼고 숫자만.",
        "- 거래명세서에는 '공급자'와 '공급받는자'가 함께 있습니다. vendor_name/vendor_biz_no 는 반드시 '공급자'(물건을 판 쪽)입니다.",
        "- 손글씨나 흐린 숫자는 추측하지 말고, 수량×단가와 금액이 맞는지 확인한 뒤 맞지 않으면 notes 에 적으세요.",
        "- 사진에 없는 값은 null. 지어내지 마세요.",
        "- 날짜가 '25.10.03' 처럼 짧게 적혀 있으면 2025-10-03 처럼 바꿔 주세요.",
        "- 결제수단: 카드 승인 내역이 있으면 card, 현금영수증/현금이면 cash, 이체면 transfer, "
        "명세서에 결제 표시가 없으면(월말 정산 등) credit.",
        f"- 품목 account 는 다음 중 하나: {', '.join(EXPENSE_ACCOUNTS)}. "
        "고기·채소·양념·쌀은 원재료(식자재), 술·음료는 원재료(주류·음료), 숯·호일·물티슈·장갑은 소모품비.",
    ]
    if own_business_name or own_biz_no:
        lines.append(
            f"- 참고: 우리 가게(공급받는자)는 '{own_business_name or '-'}' / 사업자번호 '{own_biz_no or '-'}' 입니다. 이 정보는 공급자로 쓰지 마세요."
        )
    if doc_type_hint:
        lines.append(f"- 사용자가 선택한 문서 종류: {'거래명세서' if doc_type_hint == DocType.STATEMENT else '영수증'}")
    lines.append(f"\n{TOOL_NAME} 도구로 결과를 기록하세요.")
    return "\n".join(lines)


def _to_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def result_from_tool_input(data: dict, model: str, doc_type_hint: DocType | None) -> ExtractionResult:
    doc_type = DocType(data["doc_type"]) if data.get("doc_type") in ("receipt", "statement") else doc_type_hint
    if doc_type_hint:  # 사용자가 직접 고른 종류가 우선
        doc_type = doc_type_hint
    payment = data.get("payment_method")
    items = []
    for raw in data.get("items") or []:
        if not raw.get("name"):
            continue
        item = LineItem(**{k: raw.get(k) for k in LineItem.model_fields})
        item.account = normalize_account(raw.get("account"), item.name, doc_type)
        items.append(item)
    return ExtractionResult(
        doc_type=doc_type,
        vendor_name=data.get("vendor_name"),
        vendor_biz_no=data.get("vendor_biz_no"),
        issue_date=_to_date(data.get("issue_date")),
        payment_method=PaymentMethod(payment) if payment in PaymentMethod._value2member_map_ else None,
        supply_amount=data.get("supply_amount"),
        vat_amount=data.get("vat_amount"),
        total_amount=data.get("total_amount"),
        items=items,
        raw_text=data.get("raw_text") or "",
        extractor=f"claude:{model}",
        confidence=max(0.0, min(1.0, float(data.get("confidence") or 0))),
        warnings=[f"AI 확인 요청: {n}" for n in data.get("notes") or []],
    )


class ClaudeVisionExtractor:
    name = "claude"

    def __init__(self, api_key: str, model: str, own_business_name: str | None = None, own_biz_no: str | None = None):
        import anthropic  # 키가 있을 때만 필요하므로 지연 import

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.own_business_name = own_business_name
        self.own_biz_no = own_biz_no

    def extract(self, jpeg: bytes, doc_type_hint: DocType | None = None) -> ExtractionResult:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            tools=[TOOL],
            tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                 "data": base64.b64encode(jpeg).decode()}},
                    {"type": "text", "text": build_prompt(doc_type_hint, self.own_business_name, self.own_biz_no)},
                ],
            }],
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == TOOL_NAME:
                return result_from_tool_input(block.input, self.model, doc_type_hint)
        raise RuntimeError("AI 응답에 추출 결과가 없습니다.")

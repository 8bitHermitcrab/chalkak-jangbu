"""Claude 응답(툴 입력) → ExtractionResult 변환. 실제 API는 부르지 않는다."""
from datetime import date

from app.domain import DocType, PaymentMethod
from app.services.classifier import ACCOUNT_FOOD, ACCOUNT_SUPPLIES
from app.services.extraction.claude_vision import TOOL, build_prompt, result_from_tool_input


def test_maps_tool_input_and_fixes_bad_account():
    data = {
        "doc_type": "statement",
        "vendor_name": "한돈유통",
        "vendor_biz_no": "214-86-12345",
        "issue_date": "2025-10-03",
        "payment_method": "credit",
        "total_amount": 274300,
        "items": [
            {"name": "삼겹살", "quantity": 10, "unit_price": 18000, "amount": 180000, "account": "원재료(식자재)"},
            {"name": "참숯", "quantity": 1, "amount": 30000, "account": "식비"},  # 목록에 없는 계정
            {"name": "", "account": "기타비용"},  # 이름 없는 줄은 버린다
        ],
        "raw_text": "...",
        "confidence": 1.4,
        "notes": ["세 번째 줄 단가가 흐립니다"],
    }
    r = result_from_tool_input(data, "claude-test", None)
    assert r.doc_type == DocType.STATEMENT
    assert r.issue_date == date(2025, 10, 3)
    assert r.payment_method == PaymentMethod.CREDIT
    assert [i.account for i in r.items] == [ACCOUNT_FOOD, ACCOUNT_SUPPLIES]
    assert r.confidence == 1.0
    assert r.warnings == ["AI 확인 요청: 세 번째 줄 단가가 흐립니다"]
    assert r.extractor == "claude:claude-test"


def test_user_selected_type_wins_and_bad_values_ignored():
    r = result_from_tool_input(
        {"doc_type": "receipt", "issue_date": "10월 3일", "payment_method": "bitcoin", "items": [],
         "raw_text": "", "confidence": 0.3},
        "m", DocType.STATEMENT,
    )
    assert r.doc_type == DocType.STATEMENT
    assert r.issue_date is None and r.payment_method is None


def test_prompt_mentions_our_store_so_it_is_not_taken_as_vendor():
    prompt = build_prompt(DocType.STATEMENT, "고기굽는집", "110-22-33333")
    assert "고기굽는집" in prompt and "공급자" in prompt
    assert TOOL["input_schema"]["properties"]["items"]["items"]["properties"]["account"]["enum"]

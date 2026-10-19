"""품목명 → 계정과목 분류.

고깃집 같은 소규모 음식점에서 실제로 자주 나오는 품목을 기준으로 만든 키워드 규칙이다.
AI 추출기가 계정과목을 제안하더라도 허용 목록 밖이면 이 규칙으로 다시 분류한다.
"""
from __future__ import annotations

from app.domain import DocType

# 이 서비스가 쓰는 계정과목. 프론트엔드 드롭다운도 이 목록을 그대로 받아 간다.
ACCOUNT_FOOD = "원재료(식자재)"
ACCOUNT_DRINK = "원재료(주류·음료)"
ACCOUNT_SUPPLIES = "소모품비"
ACCOUNT_UTILITIES = "수도광열비"
ACCOUNT_WELFARE = "복리후생비"
ACCOUNT_FEES = "지급수수료"
ACCOUNT_REPAIR = "수선비"
ACCOUNT_OTHER = "기타비용"

EXPENSE_ACCOUNTS = [
    ACCOUNT_FOOD,
    ACCOUNT_DRINK,
    ACCOUNT_SUPPLIES,
    ACCOUNT_UTILITIES,
    ACCOUNT_WELFARE,
    ACCOUNT_FEES,
    ACCOUNT_REPAIR,
    ACCOUNT_OTHER,
]

# 순서가 중요하다: 앞쪽 규칙이 먼저 맞으면 그 계정으로 확정된다.
# (예: "숯불양념" 은 식자재여야 하므로 식자재 규칙을 소모품 '숯' 보다 먼저 검사)
_RULES: list[tuple[str, tuple[str, ...]]] = [
    (ACCOUNT_DRINK, (
        "소주", "맥주", "막걸리", "청하", "와인", "하이볼", "사케", "콜라", "사이다",
        "음료", "생수", "탄산", "주스", "참이슬", "처음처럼", "카스", "테라", "켈리", "진로",
    )),
    (ACCOUNT_FOOD, (
        # 육류
        "삼겹", "목살", "항정", "가브리", "갈매기", "껍데기", "갈비", "등심", "안심", "채끝",
        "차돌", "우삼겹", "한우", "한돈", "돼지", "돈육", "소고기", "우육", "양념육", "막창",
        "곱창", "대창", "오리", "닭", "육우", "수입육", "냉동육", "생고기",
        # 채소·쌈
        "상추", "깻잎", "쌈", "파채", "대파", "쪽파", "양파", "마늘", "고추", "버섯", "배추",
        "무우", "애호박", "호박", "감자", "고구마", "콩나물", "숙주", "부추", "미나리", "당근",
        "오이", "양배추", "깍두기", "김치", "채소", "야채",
        # 양념·식재료
        "쌈장", "된장", "고추장", "간장", "식초", "설탕", "소금", "참기름", "들기름",
        "식용유", "올리브유", "고춧가루", "양념", "소스", "육수", "다시다", "후추", "참깨", "통깨",
        "쌀", "공기밥", "냉면", "국수", "라면", "두부", "계란", "달걀", "치즈", "떡",
        "밀가루", "전분", "어묵", "젓갈", "명이", "장아찌",
    )),
    (ACCOUNT_UTILITIES, ("lpg", "도시가스", "가스요금", "가스대", "전기요금", "전기료", "수도요금", "수도료")),
    (ACCOUNT_SUPPLIES, (
        "숯", "번개탄", "착화", "호일", "쿠킹", "집게", "가위", "물티슈", "냅킨", "휴지",
        "일회용", "위생장갑", "고무장갑", "장갑", "랩", "봉투", "비닐", "세제", "락스",
        "수세미", "앞치마", "행주", "이쑤시개", "종이컵", "포장용기", "용기", "석쇠", "불판",
        "가스", "부탄",
    )),
    (ACCOUNT_FEES, ("수수료", "배달대행", "배민", "요기요", "쿠팡이츠", "광고", "카드단말")),
    (ACCOUNT_REPAIR, ("수리", "수선", "a/s", "as비", "교체비", "설치비")),
    (ACCOUNT_WELFARE, ("직원식", "직원 식대", "식대", "간식", "회식", "음료 간식")),
]


def classify_item(name: str | None, doc_type: DocType | None = None) -> tuple[str, bool]:
    """품목명을 계정과목으로 분류한다.

    반환값: (계정과목, 키워드로 판단했는지 여부)
    키워드가 하나도 맞지 않으면 문서 종류에 따라 기본 계정을 돌려준다.
    거래명세서는 대부분 식자재 납품이므로 식자재, 영수증은 소모품비가 기본값이다.
    """
    text = (name or "").lower().replace(" ", "")
    for account, keywords in _RULES:
        if any(k.replace(" ", "") in text for k in keywords):
            return account, True
    return default_account(doc_type), False


def default_account(doc_type: DocType | None) -> str:
    return ACCOUNT_FOOD if doc_type == DocType.STATEMENT else ACCOUNT_SUPPLIES


def normalize_account(account: str | None, name: str | None, doc_type: DocType | None) -> str:
    """AI가 제안한 계정과목이 허용 목록에 있으면 쓰고, 아니면 규칙으로 분류한다."""
    if account in EXPENSE_ACCOUNTS:
        return account  # type: ignore[return-value]
    return classify_item(name, doc_type)[0]

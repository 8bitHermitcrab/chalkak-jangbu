"""휴대폰으로 찍은 사진을 OCR/AI가 읽기 좋은 형태로 맞춘다."""
from __future__ import annotations

import io

from PIL import Image, ImageOps

try:  # 아이폰 기본 촬영 포맷(HEIC) 지원. 설치돼 있지 않아도 나머지 포맷은 동작한다.
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

MAX_SIDE = 2000  # 너무 큰 사진은 줄인다. 영수증 글자를 읽기엔 이 정도면 충분하다.


class InvalidImageError(ValueError):
    pass


def normalize_image(data: bytes) -> bytes:
    """회전 정보(EXIF) 반영, 크기 축소, JPEG 변환."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
    except Exception as exc:  # noqa: BLE001 - Pillow는 포맷마다 다른 예외를 던진다
        raise InvalidImageError("이미지 파일을 읽을 수 없습니다. JPG, PNG, HEIC 사진을 올려 주세요.") from exc
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90)
    return out.getvalue()


def prepare_for_ocr(jpeg: bytes) -> Image.Image:
    """Tesseract용 전처리: 흑백 + 대비 보정 + 작은 사진 확대."""
    img = Image.open(io.BytesIO(jpeg)).convert("L")
    if max(img.size) < 1500:
        scale = 1500 / max(img.size)
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    return ImageOps.autocontrast(img)

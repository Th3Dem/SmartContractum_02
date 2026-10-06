"""Validation of submitted publications and questions, including cover images."""
import base64
import image_decoder
import os
import re
import time
from typing import Any, Dict, Optional, Tuple

import image_decoder

from backend import config
from backend.config import LEGACY_MATERIAL_TYPES, VALID_COMPLEXITIES, VALID_MATERIAL_TYPES
from backend.content import has_valid_article_text, is_valid_id, sanitize_article_html
from backend.storage import save_media_file


class CoverValidationResult(tuple):
    """
    Validation result that unpacks as (is_valid, error_msg) for full backward compatibility,
    while also exposing .is_valid, .error_msg, .saved_url, .meta, .image_bytes.
    """
    def __new__(cls, is_valid: bool, error_msg: Optional[str] = None, saved_url: Optional[str] = None, meta: Optional[dict] = None, image_bytes: Optional[bytes] = None):
        return super().__new__(cls, (is_valid, error_msg))

    def __init__(self, is_valid: bool, error_msg: Optional[str] = None, saved_url: Optional[str] = None, meta: Optional[dict] = None, image_bytes: Optional[bytes] = None):
        self.is_valid = is_valid
        self.error_msg = error_msg
        self.saved_url = saved_url
        self.meta = meta or {}
        self.image_bytes = image_bytes


MAX_COVER_DECODED_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_COVER_BASE64_CHARS = 14 * 1024 * 1024 + 1024  # ~14 MB

COVER_DATA_URI_PATTERN = re.compile(
    r"^data:image/(jpeg|jpg|png|webp|gif|svg\+xml);base64,(.+)$",
    re.IGNORECASE | re.DOTALL
)


def validate_cover_image(cover_image: Any, target_media_dir: Optional[str] = None, require_exists: bool = False) -> CoverValidationResult:
    """
    Validates publication cover image:
    - Field is optional (None, empty string or whitespace-only is valid).
    - If provided: must be string.
    - Size: maximum 10 MB decoded data (~14 MB base64).
    - Schemes supported:
        * Relative path: /media/...
        * Data URI: data:image/(jpeg|jpg|png|webp|gif|svg+xml);base64,...
    - Deep validation via image_decoder.decode_and_validate_image:
        * PNG: signature, IHDR, IDAT, IEND, zlib decompression.
        * JPEG: SOI, SOF, APP1 EXIF orientation, EOI end marker.
        * GIF: GIF87a/GIF89a, screen descriptor, static first frame check, trailer.
        * WebP: RIFF, WEBP, VP8/VP8L/VP8X, static frame check.
        * SVG: <svg tag and viewBox.
        * Pixel bomb protection: rejects images exceeding 25 million pixels.
    - Storage:
        * Decoded binary image is automatically stored to data/media/<sha256>.<ext>.
        * Returns CoverValidationResult (unpacks as (is_valid, error_msg)).
    """
    if cover_image is None or cover_image == "":
        return CoverValidationResult(True, None, saved_url=None)

    if not isinstance(cover_image, str):
        return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")

    stripped = cover_image.strip()
    if not stripped:
        return CoverValidationResult(True, None, saved_url=None)

    if stripped.startswith("/media/"):
        if ".." in stripped or len(stripped) > 500:
            return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")
        if not re.match(r"^/media/[a-zA-Z0-9_\-\./]+$", stripped):
            return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")

        media_root = target_media_dir or config.MEDIA_DIR
        rel_path = stripped[len("/media/"):].lstrip("/")
        full_path = os.path.abspath(os.path.join(media_root, rel_path))
        if not full_path.startswith(os.path.abspath(media_root)):
            return CoverValidationResult(False, "Недопустимый путь к медиафайлу.")

        if os.path.isfile(full_path):
            try:
                with open(full_path, "rb") as f:
                    file_bytes = f.read()
                ok, err, meta = image_decoder.decode_and_validate_image(file_bytes)
                if not ok:
                    return CoverValidationResult(False, err or "Обложка повреждена или не может быть декодирована.")
                return CoverValidationResult(True, None, saved_url=stripped, meta=meta, image_bytes=file_bytes)
            except Exception as e:
                return CoverValidationResult(False, f"Ошибка чтения медиафайла: {str(e)}")
        else:
            if require_exists:
                return CoverValidationResult(False, "Файл изображения не найден на сервере.")
            else:
                return CoverValidationResult(True, None, saved_url=stripped)

    if stripped.startswith("data:image/"):
        if len(stripped) > MAX_COVER_BASE64_CHARS:
            return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")

        match = COVER_DATA_URI_PATTERN.match(stripped)
        if not match:
            return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")

        mime_sub = match.group(1).lower()
        b64_str = match.group(2).strip()

        try:
            decoded = base64.b64decode(b64_str, validate=True)
        except Exception:
            return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")

        if len(decoded) == 0 or len(decoded) > MAX_COVER_DECODED_BYTES:
            return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")

        # Deep decoding and verification via image_decoder
        ok, err, meta = image_decoder.decode_and_validate_image(decoded)
        if not ok:
            return CoverValidationResult(False, err or "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")

        ext = meta.get("format", "jpg")
        media_root = target_media_dir or config.MEDIA_DIR
        saved_url = save_media_file(decoded, ext, media_dir=media_root)

        return CoverValidationResult(True, None, saved_url=saved_url, meta=meta, image_bytes=decoded)

    return CoverValidationResult(False, "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ.")


def resolve_cover_position(settings: Any) -> Optional[str]:
    """
    Extracts or computes CSS object-position for article/card cover image.
    Supports coverPosition, objectPosition, or focalPoint (dict or string).
    """
    if not isinstance(settings, dict):
        return None
    cov_pos = settings.get("coverPosition") or settings.get("objectPosition")
    if cov_pos and isinstance(cov_pos, str) and cov_pos.strip():
        return cov_pos.strip()
    focal = settings.get("focalPoint")
    if isinstance(focal, str) and focal.strip():
        return focal.strip()
    if isinstance(focal, dict):
        x = focal.get("x")
        y = focal.get("y")
        if x is not None and y is not None:
            try:
                xf = float(x)
                yf = float(y)
                if 0 <= xf <= 1 and 0 <= yf <= 1 and (xf < 1 or yf < 1):
                    return f"{round(xf * 100, 2)}% {round(yf * 100, 2)}%"
                return f"{round(xf, 2)}% {round(yf, 2)}%"
            except (ValueError, TypeError):
                pass
    return None


def validate_submission_payload(payload: Any) -> Tuple[bool, Optional[str], Dict[str, str]]:
    """
    Validates submission payload according to product requirements:
    - title: non-empty trimmed string (min 1 char)
    - html: contains text characters [a-zA-Zа-яА-Я0-9] (no empty tags, &nbsp;, dividers, images only)
    - publicationSettings:
        - targetAudience: non-empty string, valid ID
        - topics: array of 1 to 5 non-empty string IDs
        - keywords: array of 1 to 10 strings, each 1..60 chars, no case-insensitive duplicates
        - description: string 50..500 chars
        - format: valid format ID or null/empty
        - complexity: valid complexity ID or null/empty
        - coverImage: optional valid image up to 10 MB (data URI / relative /media/ path)
    """
    field_errors: Dict[str, str] = {}

    if not isinstance(payload, dict):
        return False, "Тело запроса должно быть JSON-объектом", {"payload": "Invalid JSON object"}

    pub_settings = payload.get("publicationSettings") or payload.get("publication_settings")
    if pub_settings is None and (payload.get("materialType") == "question" or payload.get("type") == "question"):
        pub_settings = {}
        payload["publicationSettings"] = pub_settings

    # Resolve materialType early to apply material-specific rules (e.g. questions)
    raw_mat = None
    if isinstance(pub_settings, dict):
        raw_mat = pub_settings.get("materialType") or pub_settings.get("type")
    if not raw_mat:
        raw_mat = payload.get("materialType") or payload.get("type")

    is_question = False
    if raw_mat is not None and isinstance(raw_mat, str):
        norm_mat = raw_mat.strip().lower()
        if norm_mat in LEGACY_MATERIAL_TYPES:
            norm_mat = LEGACY_MATERIAL_TYPES[norm_mat]
        if norm_mat in VALID_MATERIAL_TYPES:
            raw_mat = norm_mat
            is_question = (norm_mat == "question")
            if isinstance(pub_settings, dict):
                pub_settings["materialType"] = norm_mat
                pub_settings["type"] = norm_mat
            payload["materialType"] = norm_mat

    # 1. draftId
    draft_id = payload.get("draftId") or payload.get("draft_id")
    if not draft_id or not isinstance(draft_id, str) or not draft_id.strip():
        if is_question:
            draft_id = f"draft_q_{int(time.time()*1000)}"
            payload["draftId"] = draft_id
        else:
            field_errors["draftId"] = "Идентификатор черновика (draftId) обязателен."

    # 2. title
    title = payload.get("title")
    if title is None or not isinstance(title, str) or not title.strip():
        field_errors["title"] = "Заголовок статьи не может быть пустым."

    # 3. html
    article_html = payload.get("html") or payload.get("article_html") or payload.get("content")
    if article_html is None or not isinstance(article_html, str):
        field_errors["html"] = "Тело статьи должно содержать текст (буквы или цифры). Пустые блоки, пробелы и только изображения недопустимы."
    else:
        sanitized_html = sanitize_article_html(article_html)
        if not has_valid_article_text(sanitized_html):
            field_errors["html"] = "Тело статьи должно содержать текст (буквы или цифры). Пустые блоки, пробелы и только изображения недопустимы."
        else:
            if "html" in payload and isinstance(payload["html"], str):
                payload["html"] = sanitized_html
            elif "article_html" in payload and isinstance(payload["article_html"], str):
                payload["article_html"] = sanitized_html
            elif "content" in payload and isinstance(payload["content"], str):
                payload["content"] = sanitized_html

    # 4. publicationSettings
    if pub_settings is None or not isinstance(pub_settings, dict):
        field_errors["publicationSettings"] = "Настройки публикации обязательны и должны быть объектом."
    else:
        # 4a. targetAudience
        target_audience = pub_settings.get("targetAudience") or pub_settings.get("target_audience")
        if not target_audience or not isinstance(target_audience, str) or not target_audience.strip():
            if is_question:
                target_audience = "developers"
                pub_settings["targetAudience"] = "developers"
            else:
                field_errors["targetAudience"] = "Целевая аудитория обязательна и должна быть выбрана."
        elif not is_valid_id(target_audience):
            field_errors["targetAudience"] = "Указан недопустимый идентификатор целевой аудитории."

        # 4b. topics
        topics = pub_settings.get("topics")
        if topics is None or not isinstance(topics, list) or len(topics) == 0:
            if is_question:
                pub_settings["topics"] = ["smart-contracts-development"]
                topics = pub_settings["topics"]
            else:
                field_errors["topics"] = "Темы публикации должны быть массивом идентификаторов."
        elif len(topics) < 1 or len(topics) > 5:
            field_errors["topics"] = "Необходимо выбрать от 1 до 5 тем публикации."
        elif not all(isinstance(t, str) and is_valid_id(t) for t in topics):
            field_errors["topics"] = "Темы публикации содержат невалидные идентификаторы."
        elif len(set(topics)) != len(topics):
            field_errors["topics"] = "Темы публикации не должны дублироваться."

        # 4c. keywords
        keywords = pub_settings.get("keywords")
        if keywords is None or not isinstance(keywords, list):
            if is_question:
                pub_settings["keywords"] = []
                keywords = []
            else:
                field_errors["keywords"] = "Ключевые слова должны быть массивом строк."
        elif len(keywords) < 1:
            if not is_question:
                field_errors["keywords"] = "Необходимо указать хотя бы одно ключевое слово."
        elif len(keywords) > 10:
            field_errors["keywords"] = "Нельзя указать более 10 ключевых слов."
        else:
            seen_kw = set()
            invalid_kw_len = False
            has_dup = False
            for kw in keywords:
                if not isinstance(kw, str):
                    invalid_kw_len = True
                    break
                stripped = kw.strip()
                if len(stripped) < 1 or len(stripped) > 60:
                    invalid_kw_len = True
                    break
                norm = re.sub(r'\s+', ' ', stripped).lower()
                if norm in seen_kw:
                    has_dup = True
                    break
                seen_kw.add(norm)

            if invalid_kw_len:
                field_errors["keywords"] = "Каждое ключевое слово должно содержать от 1 до 60 символов."
            elif has_dup:
                field_errors["keywords"] = "Ключевые слова не должны дублироваться без учета регистра."

        # 4d. description
        desc = pub_settings.get("description")
        if is_question:
            if not desc or not isinstance(desc, str) or not desc.strip():
                clean_title = (title or "Вопрос сообществу").strip()
                pub_settings["description"] = clean_title[:500]
            elif len(desc.strip()) > 500:
                field_errors["description"] = "Краткое описание должно содержать от 50 до 500 символов."
        else:
            if desc is None or not isinstance(desc, str):
                field_errors["description"] = "Краткое описание обязательно."
            elif len(desc.strip()) < 50 or len(desc.strip()) > 500:
                field_errors["description"] = "Краткое описание должно содержать от 50 до 500 символов."

        # 4e. format
        fmt = pub_settings.get("format")
        if fmt is not None and fmt != "":
            if not isinstance(fmt, str) or not is_valid_id(fmt):
                field_errors["format"] = "Недопустимый формат публикации."

        # 4f. complexity (deprecated per Issue #61: optional, not enforced)
        compl = pub_settings.get("complexity")
        if compl is not None and compl != "":
            if not isinstance(compl, str) or compl not in VALID_COMPLEXITIES:
                pass

        # 4g. materialType / type (Issue #61: publication or question)
        mat_check = pub_settings.get("materialType") or pub_settings.get("type") or payload.get("materialType")
        if mat_check is not None and mat_check != "":
            if not isinstance(mat_check, str):
                field_errors["materialType"] = f"Недопустимый тип материала публикации. Допустимые типы: {', '.join(VALID_MATERIAL_TYPES)}"
            else:
                norm_mat = mat_check.strip().lower()
                if norm_mat in LEGACY_MATERIAL_TYPES:
                    norm_mat = LEGACY_MATERIAL_TYPES[norm_mat]
                if norm_mat not in VALID_MATERIAL_TYPES:
                    field_errors["materialType"] = f"Недопустимый тип материала публикации. Допустимые типы: {', '.join(VALID_MATERIAL_TYPES)}"
                else:
                    pub_settings["materialType"] = norm_mat
                    pub_settings["type"] = norm_mat
                    payload["materialType"] = norm_mat

        # 4h. coverImage
        cover_image = pub_settings.get("coverImage")
        if cover_image is not None and cover_image != "":
            cov_res = validate_cover_image(cover_image)
            is_cov_valid, cov_err = cov_res[0], cov_res[1]
            if not is_cov_valid:
                field_errors["coverImage"] = cov_err or "Обложка должна быть валидным изображением JPG, PNG, WebP или GIF до 10 МБ."
            elif cov_res.saved_url and cov_res.saved_url.startswith("/media/"):
                pub_settings["coverImage"] = cov_res.saved_url

        # 4i. companyId (optional)
        comp_id = pub_settings.get("companyId") or pub_settings.get("company_id")
        if comp_id is not None and comp_id != "":
            if not isinstance(comp_id, str) or not is_valid_id(comp_id):
                field_errors["companyId"] = "Недопустимый идентификатор компании."

        # 4j. clubId (optional)
        club_id = pub_settings.get("clubId") or pub_settings.get("club_id")
        if club_id is not None and club_id != "":
            if not isinstance(club_id, str) or not is_valid_id(club_id):
                field_errors["clubId"] = "Недопустимый идентификатор клуба."

    if field_errors:
        order = [
            "title", "html", "targetAudience", "topics", "keywords", "description",
            "format", "complexity", "materialType", "coverImage", "companyId", "clubId",
            "draftId", "publicationSettings"
        ]
        first_key = next((k for k in order if k in field_errors), next(iter(field_errors.keys())))
        error_msg = field_errors[first_key]
        return False, error_msg, field_errors

    return True, None, {}

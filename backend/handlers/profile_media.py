"""Avatar and cover of a person; logo and cover of a company. Only the owner's own uploads can be assigned."""
import datetime
import os
import re

from backend import config
from backend.config import MAX_JSON_BODY_BYTES
from backend.companies import is_company_owner
from backend.identity import sync_comment_snapshots
from backend.media_library import (
    COMPANY_MEDIA_KINDS,
    PROFILE_MEDIA_KINDS,
    focal_dict,
    is_upload_owned_by,
    parse_focal,
)

ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
MEDIA_URL = re.compile(r"^/media/[A-Za-z0-9._-]+$")
# Smallest accepted pixel size per kind; the client crops to larger sizes
MIN_SIZE = {"avatar": (64, 64), "logo": (64, 64), "cover": (600, 150)}


class ProfileMediaHandlers:
    def _check_media_url(self, conn, url, user_id, kind, current):
        """Returns (http_status, message) when url may not be assigned by this user, or None."""
        if url == current:
            return None
        if not isinstance(url, str) or not MEDIA_URL.match(url) or ".." in url:
            return 400, "Изображение должно быть загружено через сайт"
        if not url.lower().endswith(ALLOWED_EXTENSIONS):
            return 400, "Поддерживаются изображения JPEG, PNG и WebP"
        media_root = getattr(self.server, "media_dir", config.MEDIA_DIR)
        if not os.path.isfile(os.path.join(media_root, url[len("/media/"):])):
            return 400, "Файл изображения не найден"
        if not is_upload_owned_by(conn, url, user_id):
            return 403, "Можно использовать только изображения, загруженные вами"
        row = conn.execute("SELECT width, height FROM media_uploads WHERE url = ? OR url = ?",
                           (url, f"{url}#{user_id}")).fetchone()
        min_w, min_h = MIN_SIZE[kind]
        if row and row["width"] and row["height"] and (row["width"] < min_w or row["height"] < min_h):
            return 400, f"Изображение слишком маленькое: нужно не меньше {min_w}x{min_h} пикселей"
        return None

    def _read_media_payload(self, kinds):
        data = self.read_json_body(MAX_JSON_BODY_BYTES)
        if data is None:
            return None
        kind = data.get("kind")
        if kind not in kinds:
            self.send_json_response(400, {"success": False, "error": "Неизвестный тип изображения"})
            return None
        focal, error = parse_focal(data.get("focal"))
        if error:
            self.send_json_response(400, {"success": False, "error": error})
            return None
        return kind, data.get("url"), bool(data.get("remove")), focal

    def handle_update_profile_media(self):
        """POST /api/user/profile-media {kind: avatar|cover, url, focal?, remove?}"""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация", "requireAuth": True})
            return
        parsed = self._read_media_payload(PROFILE_MEDIA_KINDS)
        if parsed is None:
            return
        kind, url, remove, focal = parsed
        conn = self.get_db()
        try:
            row = conn.execute("SELECT avatar, cover, cover_focal FROM user_profiles WHERE user_id = ?", (user["id"],)).fetchone()
            if not row:
                self.send_json_response(404, {"success": False, "error": "Профиль не найден"})
                return
            if not remove:
                error = self._check_media_url(conn, url, user["id"], kind, row[kind])
                if error:
                    self.send_json_response(error[0], {"success": False, "error": error[1]})
                    return
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            # One statement: a failure leaves the previous image in place. Old files are never deleted here.
            with conn:
                if kind == "avatar":
                    conn.execute("UPDATE user_profiles SET avatar = ?, updated_at = ? WHERE user_id = ?",
                                 (None if remove else url, now, user["id"]))
                    sync_comment_snapshots(conn, user["id"])
                else:
                    conn.execute("UPDATE user_profiles SET cover = ?, cover_focal = ?, updated_at = ? WHERE user_id = ?",
                                 (None if remove else url, None if remove else focal, now, user["id"]))
            row = conn.execute("SELECT avatar, cover, cover_focal FROM user_profiles WHERE user_id = ?", (user["id"],)).fetchone()
        finally:
            conn.close()
        self.send_json_response(200, {"success": True, "avatar": row["avatar"], "cover": row["cover"],
                                      "coverFocal": focal_dict(row["cover_focal"])})

    def handle_update_company_media(self, company_id):
        """POST /api/companies/<id>/media {kind: logo|cover, url, focal?, remove?} (owner only)"""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация", "requireAuth": True})
            return
        parsed = self._read_media_payload(COMPANY_MEDIA_KINDS)
        if parsed is None:
            return
        kind, url, remove, focal = parsed
        conn = self.get_db()
        try:
            row = conn.execute("SELECT logo, cover, cover_focal FROM companies WHERE id = ?", (company_id,)).fetchone()
            if not row:
                self.send_json_response(404, {"success": False, "error": "Компания не найдена"})
                return
            if not is_company_owner(conn, company_id, user):
                self.send_json_response(403, {"success": False, "error": "Изображения компании меняет только владелец"})
                return
            if not remove:
                error = self._check_media_url(conn, url, user["id"], kind, row[kind])
                if error:
                    self.send_json_response(error[0], {"success": False, "error": error[1]})
                    return
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            with conn:
                if kind == "logo":
                    conn.execute("UPDATE companies SET logo = ?, updated_at = ? WHERE id = ?",
                                 (None if remove else url, now, company_id))
                else:
                    conn.execute("UPDATE companies SET cover = ?, cover_focal = ?, updated_at = ? WHERE id = ?",
                                 (None if remove else url, None if remove else focal, now, company_id))
            row = conn.execute("SELECT logo, cover, cover_focal FROM companies WHERE id = ?", (company_id,)).fetchone()
        finally:
            conn.close()
        self.send_json_response(200, {"success": True, "logo": row["logo"], "cover": row["cover"],
                                      "coverFocal": focal_dict(row["cover_focal"])})

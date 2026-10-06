"""Media upload and serving."""
import image_decoder
import json
import os
import re

import image_decoder

from backend import config
from backend.config import MAX_MEDIA_BODY_BYTES
from backend.storage import save_media_file
from backend.submissions import validate_cover_image


class MediaHandlers:
    def handle_serve_media(self, parsed_url):
        """
        GET /media/<filename>
        Serves stored media files with strict path-traversal prevention,
        proper Content-Type header, and long-term caching headers.
        """
        media_root = getattr(self.server, "media_dir", config.MEDIA_DIR)
        rel_path = parsed_url.path[len("/media/"):].lstrip("/")
        if not rel_path or ".." in rel_path:
            self.send_json_response(400, {"success": False, "error": "Invalid media path"})
            return

        full_path = os.path.abspath(os.path.join(media_root, rel_path))
        if not full_path.startswith(os.path.abspath(media_root)):
            self.send_json_response(403, {"success": False, "error": "Access denied"})
            return

        if not os.path.isfile(full_path):
            self.send_json_response(404, {"success": False, "error": "Media not found"})
            return

        ext = os.path.splitext(full_path)[1].lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".svg": "image/svg+xml"
        }
        content_type = mime_types.get(ext, "application/octet-stream")

        try:
            with open(full_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Disposition", "inline")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_json_response(500, {"success": False, "error": f"Failed to read media: {str(e)}"})

    def handle_media_upload(self):
        """
        POST /api/media/upload
        Accepts:
          - JSON: { "image": "data:image/..." } or { "coverImage": "..." }
          - Raw binary image bytes
        Validates via image_decoder and saves to data/media/<hash>.<ext>.
        Returns { success: True, url: "/media/...", meta: { ... } }
        """
        raw_body = self.read_request_body(MAX_MEDIA_BODY_BYTES)
        if raw_body is None:
            return

        if len(raw_body) == 0:
            self.send_json_response(400, {"success": False, "error": "Пустое тело запроса"})
            return

        content_type = self.headers.get("Content-Type", "")
        media_root = getattr(self.server, "media_dir", config.MEDIA_DIR)

        if "application/json" in content_type:
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                self.send_json_response(400, {"success": False, "error": f"Невалидный JSON: {str(e)}"})
                return
            except Exception as e:
                self.send_json_response(400, {"success": False, "error": f"Ошибка обработки JSON: {str(e)}"})
                return

            if not isinstance(payload, dict):
                self.send_json_response(400, {"success": False, "error": "Тело запроса должно быть JSON-объектом."})
                return

            image_val = payload.get("image") or payload.get("coverImage") or payload.get("file")
            if not image_val or not isinstance(image_val, str):
                self.send_json_response(400, {"success": False, "error": "Поле image должно содержать Data URI или base64"})
                return
            res = validate_cover_image(image_val, target_media_dir=media_root)
            if not res.is_valid:
                self.send_json_response(400, {"success": False, "error": res.error_msg})
                return
            self.send_json_response(200, {
                "success": True,
                "url": res.saved_url,
                "meta": res.meta
            })
            return

        if "multipart/form-data" in content_type:
            boundary_match = re.search(r'boundary=([^\s;]+)', content_type)
            if boundary_match:
                boundary = boundary_match.group(1).strip('"\'').encode('ascii')
                parts = raw_body.split(b'--' + boundary)
                file_bytes = None
                for part in parts:
                    if b'filename=' in part:
                        header_end = part.find(b'\r\n\r\n')
                        if header_end != -1:
                            file_bytes = part[header_end + 4:].rstrip(b'\r\n-')
                            break
                        header_end = part.find(b'\n\n')
                        if header_end != -1:
                            file_bytes = part[header_end + 2:].rstrip(b'\r\n-')
                            break
                if file_bytes:
                    raw_body = file_bytes

        # Direct binary image upload
        ok, err, meta = image_decoder.decode_and_validate_image(raw_body)
        if not ok:
            self.send_json_response(400, {"success": False, "error": err or "Невалидный формат изображения"})
            return

        ext = meta.get("format", "jpg")
        saved_url = save_media_file(raw_body, ext, media_dir=media_root)
        self.send_json_response(200, {
            "success": True,
            "url": saved_url,
            "meta": meta
        })

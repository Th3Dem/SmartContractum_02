"""Personal server drafts with revision checks."""
import datetime
import json
import sqlite3
import urllib.parse
import uuid

from backend.config import MAX_JSON_BODY_BYTES


SETTINGS_ERROR = "publicationSettings должен быть объектом или null"
DELTA_ERROR = "delta должен быть объектом Quill или null"
HTML_ERROR = "html должен быть строкой или null"


def _json_object_input(value, error):
    """Object (or a JSON string of an object) -> JSON text for SQLite; None stays None.

    Raises ValueError(error) for any other type, so the handler answers 400
    instead of letting sqlite3 fail on a dict (Issue #252)."""
    if value is None:
        return None
    if isinstance(value, str):
        if not value.strip():
            return None
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            raise ValueError(error)
    if not isinstance(value, dict):
        raise ValueError(error)
    return json.dumps(value, ensure_ascii=False)


def _json_object_output(raw):
    """Stored JSON text -> object for the client; empty or unreadable values -> None."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, (dict, list)):
        return raw if isinstance(raw, dict) else None
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _html_input(value):
    if value is None or isinstance(value, str):
        return value
    raise ValueError(HTML_ERROR)


def _text_input(value, field):
    if value is None or isinstance(value, str):
        return value
    raise ValueError(f"{field} должен быть строкой или null")


def _draft_fields(data, current=None):
    """Validated column values from a request body. Missing keys keep the current
    row values (PUT); ValueError carries a message for a 400 response."""
    def pick(key, column):
        if key in data:
            return data.get(key), True
        return (current[column] if current is not None else None), False

    title, _ = pick("title", "title")
    content, _ = pick("content", "content")
    company_id, _ = pick("companyId", "company_id")
    settings, settings_new = pick("publicationSettings", "publication_settings")
    delta, delta_new = pick("delta", "content_delta")
    html, _ = pick("html", "content_html")
    return {
        "title": _text_input(title, "title"),
        "content": _text_input(content, "content"),
        "company_id": _text_input(company_id, "companyId"),
        "publication_settings": _json_object_input(settings, SETTINGS_ERROR) if settings_new else settings,
        "content_delta": _json_object_input(delta, DELTA_ERROR) if delta_new else delta,
        "content_html": _html_input(html),
    }


def _revision_input(value):
    if value is None or (isinstance(value, int) and not isinstance(value, bool)):
        return value
    raise ValueError("revision должен быть целым числом")


def _draft_json(row):
    """One response shape for every drafts endpoint: settings and delta are objects."""
    keys = row.keys()
    return {
        "id": row["id"],
        "materialType": row["material_type"],
        "title": row["title"],
        "content": row["content"],
        "delta": _json_object_output(row["content_delta"]) if "content_delta" in keys else None,
        "html": row["content_html"] if "content_html" in keys else None,
        "publicationSettings": _json_object_output(row["publication_settings"]),
        "companyId": row["company_id"],
        "revision": row["revision"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"]
    }


class DraftsHandlers:
    def handle_get_drafts(self, parsed):
        """GET /api/drafts?type=...&limit=20&offset=0"""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация"})
            return

        query = urllib.parse.parse_qs(parsed.query)
        material_type = query.get("material_type", query.get("type", [None]))[0]
        try:
            limit = int(query.get("limit", ["20"])[0])
        except ValueError:
            limit = 20
        limit = max(1, min(limit, 100))
        try:
            offset = int(query.get("offset", ["0"])[0])
        except ValueError:
            offset = 0

        where_clauses = ["user_id = ?"]
        params = [user["id"]]

        if material_type:
            where_clauses.append("material_type = ?")
            params.append(material_type)

        where_sql = " AND ".join(where_clauses)

        conn = self.get_db()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) as count FROM user_drafts WHERE {where_sql}", params)
            total = cur.fetchone()["count"]

            cur.execute(f"""
                SELECT * FROM user_drafts
                WHERE {where_sql}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """, params + [limit, offset])
            rows = cur.fetchall()

            drafts = [_draft_json(r) for r in rows]
            
            self.send_json_response(200, {
                "success": True,
                "drafts": drafts,
                "total": total
            })
        finally:
            conn.close()

    def handle_get_draft(self, path):
        """GET /api/drafts/<id>"""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация"})
            return

        draft_id = path.split("/")[-1]
        
        conn = self.get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM user_drafts WHERE id = ?", (draft_id,))
            row = cur.fetchone()

            if not row:
                self.send_json_response(404, {"success": False, "error": "Черновик не найден"})
                return
            
            if row["user_id"] != user["id"]:
                self.send_json_response(403, {"success": False, "error": "Нет доступа к черновику"})
                return

            self.send_json_response(200, {"success": True, "draft": _draft_json(row)})
        finally:
            conn.close()

    def handle_post_drafts(self):
        """POST /api/drafts"""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация"})
            return

        raw_body = self.read_request_body(MAX_JSON_BODY_BYTES)
        if not raw_body:
            return
        
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            self.send_json_response(400, {"success": False, "error": "Invalid JSON"})
            return

        draft_id = data.get("id") or str(uuid.uuid4())
        material_type = data.get("materialType")
        
        if material_type not in ("publication", "question"):
            self.send_json_response(400, {"success": False, "error": "Недопустимый тип материала"})
            return

        try:
            fields = _draft_fields(data)
            client_revision = _revision_input(data.get("revision"))
        except ValueError as e:
            self.send_json_response(400, {"success": False, "error": str(e)})
            return
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM user_drafts WHERE id = ?", (draft_id,))
                row = cur.fetchone()

                if row:
                    if row["user_id"] != user["id"]:
                        self.send_json_response(403, {"success": False, "error": "Нет доступа к черновику"})
                        return

                    # Issue #256: POST to an existing draft is an update and obeys the same
                    # revision check as PUT; without a revision freshness cannot be proven.
                    if client_revision is None or client_revision < row["revision"]:
                        self.send_json_response(409, {"success": False, "error": "CONFLICT", "serverDraft": _draft_json(row)})
                        return

                    # Compare-and-swap on the revision read above: a concurrent save in between wins, this one conflicts
                    cur.execute("""
                        UPDATE user_drafts
                        SET material_type = ?, title = ?, content = ?, publication_settings = ?, company_id = ?,
                            content_delta = ?, content_html = ?, revision = revision + 1, updated_at = ?
                        WHERE id = ? AND revision = ?
                    """, (material_type, fields["title"], fields["content"], fields["publication_settings"],
                          fields["company_id"], fields["content_delta"], fields["content_html"],
                          now_iso, draft_id, row["revision"]))
                    if cur.rowcount == 0:
                        cur.execute("SELECT * FROM user_drafts WHERE id = ?", (draft_id,))
                        self.send_json_response(409, {"success": False, "error": "CONFLICT", "serverDraft": _draft_json(cur.fetchone())})
                        return
                else:
                    try:
                        cur.execute("""
                            INSERT INTO user_drafts (id, user_id, material_type, title, content, publication_settings, company_id,
                                                     content_delta, content_html, revision, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                        """, (draft_id, user["id"], material_type, fields["title"], fields["content"],
                              fields["publication_settings"], fields["company_id"], fields["content_delta"],
                              fields["content_html"], now_iso, now_iso))
                    except sqlite3.IntegrityError:
                        # Created by a concurrent request after the SELECT above
                        self.send_json_response(409, {"success": False, "error": "CONFLICT"})
                        return

                cur.execute("SELECT * FROM user_drafts WHERE id = ?", (draft_id,))
                draft_row = cur.fetchone()

            status_code = 200 if row else 201
            self.send_json_response(status_code, {"success": True, "draft": _draft_json(draft_row)})
        finally:
            conn.close()

    def handle_put_draft(self, path):
        """PUT /api/drafts/<id>"""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация"})
            return

        draft_id = path.split("/")[-1]

        raw_body = self.read_request_body(MAX_JSON_BODY_BYTES)
        if not raw_body:
            return
        
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            self.send_json_response(400, {"success": False, "error": "Invalid JSON"})
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM user_drafts WHERE id = ?", (draft_id,))
                row = cur.fetchone()

                if not row:
                    self.send_json_response(404, {"success": False, "error": "Черновик не найден"})
                    return

                if row["user_id"] != user["id"]:
                    self.send_json_response(403, {"success": False, "error": "Нет доступа к черновику"})
                    return

                client_revision = data.get("revision")
                if client_revision is not None and (isinstance(client_revision, bool) or not isinstance(client_revision, int)):
                    self.send_json_response(400, {"success": False, "error": "revision должен быть целым числом"})
                    return
                server_revision = row["revision"]
                if client_revision is not None and client_revision < server_revision:
                    self.send_json_response(409, {"success": False, "error": "CONFLICT", "serverDraft": _draft_json(row)})
                    return

                new_revision = server_revision + 1
                now_iso = datetime.datetime.utcnow().isoformat() + "Z"
                
                material_type = data.get("materialType", row["material_type"])
                if material_type not in ("publication", "question"):
                    self.send_json_response(400, {"success": False, "error": "Недопустимый тип материала"})
                    return
                try:
                    fields = _draft_fields(data, current=row)
                except ValueError as e:
                    self.send_json_response(400, {"success": False, "error": str(e)})
                    return

                cur.execute("""
                    UPDATE user_drafts
                    SET material_type = ?, title = ?, content = ?, publication_settings = ?, company_id = ?,
                        content_delta = ?, content_html = ?, revision = ?, updated_at = ?
                    WHERE id = ? AND revision = ?
                """, (material_type, fields["title"], fields["content"], fields["publication_settings"],
                      fields["company_id"], fields["content_delta"], fields["content_html"],
                      new_revision, now_iso, draft_id, server_revision))
                if cur.rowcount == 0:
                    cur.execute("SELECT * FROM user_drafts WHERE id = ?", (draft_id,))
                    self.send_json_response(409, {"success": False, "error": "CONFLICT", "serverDraft": _draft_json(cur.fetchone())})
                    return

                cur.execute("SELECT * FROM user_drafts WHERE id = ?", (draft_id,))
                updated_row = cur.fetchone()

            self.send_json_response(200, {"success": True, "draft": _draft_json(updated_row)})
        finally:
            conn.close()

    def handle_delete_draft(self, path):
        """DELETE /api/drafts/<id>"""
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация"})
            return

        draft_id = path.split("/")[-1]

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT user_id FROM user_drafts WHERE id = ?", (draft_id,))
                row = cur.fetchone()

                if not row:
                    self.send_json_response(404, {"success": False, "error": "Черновик не найден"})
                    return

                if row["user_id"] != user["id"]:
                    self.send_json_response(403, {"success": False, "error": "Нет доступа к черновику"})
                    return

                cur.execute("DELETE FROM user_drafts WHERE id = ?", (draft_id,))

            self.send_json_response(200, {"success": True, "message": "Черновик удален"})
        finally:
            conn.close()

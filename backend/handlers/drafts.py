"""Personal server drafts with revision checks."""
import datetime
import json
import urllib.parse
import uuid

from backend.config import MAX_JSON_BODY_BYTES


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

            drafts = []
            for r in rows:
                drafts.append({
                    "id": r["id"],
                    "materialType": r["material_type"],
                    "title": r["title"],
                    "content": r["content"],
                    "publicationSettings": r["publication_settings"],
                    "companyId": r["company_id"],
                    "revision": r["revision"],
                    "createdAt": r["created_at"],
                    "updatedAt": r["updated_at"]
                })
            
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

            draft = {
                "id": row["id"],
                "materialType": row["material_type"],
                "title": row["title"],
                "content": row["content"],
                "publicationSettings": row["publication_settings"],
                "companyId": row["company_id"],
                "revision": row["revision"],
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"]
            }
            self.send_json_response(200, {"success": True, "draft": draft})
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

        title = data.get("title")
        content = data.get("content")
        pub_settings = data.get("publicationSettings")
        company_id = data.get("companyId")
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT user_id, revision FROM user_drafts WHERE id = ?", (draft_id,))
                row = cur.fetchone()

                if row:
                    if row["user_id"] != user["id"]:
                        self.send_json_response(403, {"success": False, "error": "Нет доступа к черновику"})
                        return
                    
                    new_revision = row["revision"] + 1
                    cur.execute("""
                        UPDATE user_drafts
                        SET material_type = ?, title = ?, content = ?, publication_settings = ?, company_id = ?, revision = ?, updated_at = ?
                        WHERE id = ?
                    """, (material_type, title, content, pub_settings, company_id, new_revision, now_iso, draft_id))
                    revision = new_revision
                else:
                    cur.execute("""
                        INSERT INTO user_drafts (id, user_id, material_type, title, content, publication_settings, company_id, revision, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """, (draft_id, user["id"], material_type, title, content, pub_settings, company_id, now_iso, now_iso))
                    revision = 1

                cur.execute("SELECT * FROM user_drafts WHERE id = ?", (draft_id,))
                draft_row = cur.fetchone()

            draft = {
                "id": draft_row["id"],
                "materialType": draft_row["material_type"],
                "title": draft_row["title"],
                "content": draft_row["content"],
                "publicationSettings": draft_row["publication_settings"],
                "companyId": draft_row["company_id"],
                "revision": draft_row["revision"],
                "createdAt": draft_row["created_at"],
                "updatedAt": draft_row["updated_at"]
            }
            status_code = 200 if row else 201
            self.send_json_response(status_code, {"success": True, "draft": draft})
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
                server_revision = row["revision"]
                if client_revision is not None and client_revision < server_revision:
                    draft_state = {
                        "id": row["id"],
                        "materialType": row["material_type"],
                        "title": row["title"],
                        "content": row["content"],
                        "publicationSettings": row["publication_settings"],
                        "companyId": row["company_id"],
                        "revision": row["revision"],
                        "createdAt": row["created_at"],
                        "updatedAt": row["updated_at"]
                    }
                    self.send_json_response(409, {"success": False, "error": "CONFLICT", "serverDraft": draft_state})
                    return

                new_revision = server_revision + 1
                now_iso = datetime.datetime.utcnow().isoformat() + "Z"
                
                material_type = data.get("materialType", row["material_type"])
                title = data.get("title", row["title"])
                content = data.get("content", row["content"])
                pub_settings = data.get("publicationSettings", row["publication_settings"])
                company_id = data.get("companyId", row["company_id"])

                cur.execute("""
                    UPDATE user_drafts
                    SET material_type = ?, title = ?, content = ?, publication_settings = ?, company_id = ?, revision = ?, updated_at = ?
                    WHERE id = ?
                """, (material_type, title, content, pub_settings, company_id, new_revision, now_iso, draft_id))

                cur.execute("SELECT * FROM user_drafts WHERE id = ?", (draft_id,))
                updated_row = cur.fetchone()

            draft_state = {
                "id": updated_row["id"],
                "materialType": updated_row["material_type"],
                "title": updated_row["title"],
                "content": updated_row["content"],
                "publicationSettings": updated_row["publication_settings"],
                "companyId": updated_row["company_id"],
                "revision": updated_row["revision"],
                "createdAt": updated_row["created_at"],
                "updatedAt": updated_row["updated_at"]
            }
            self.send_json_response(200, {"success": True, "draft": draft_state})
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

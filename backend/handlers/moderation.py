"""Submission of publications and questions to moderation and their status."""
import datetime
import json
import sqlite3
import time
import urllib.parse
import uuid

from backend.config import MAX_JSON_BODY_BYTES
from backend.content import compute_snapshot_hash, sanitize_article_html
from backend.db import can_user_publish_for_company
from backend.moderation import REJECT_REASONS, STATUS_LABELS, material_type_of
from backend.submissions import validate_submission_payload


class ModerationHandlers:
    def handle_moderation_submit(self):
        """
        POST /api/moderation/submit
        Receives { draftId, title, html, delta, publicationSettings, idempotencyKey }.
        Validates payload, enforces idempotency, checks status transition,
        calculates SHA-256 snapshot hash, and stores immutable snapshot in SQLite.
        Requires authenticated user. author_id is strictly bound to curr_user.
        """
        raw_body = self.read_request_body(MAX_JSON_BODY_BYTES)
        if raw_body is None:
            return

        curr_user = self.get_current_user()
        if not curr_user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация для отправки материалов",
                "requireAuth": True
            })
            return

        if not raw_body:
            self.send_json_response(400, {
                "success": False,
                "error": "Пустое тело запроса (Content-Length must be > 0)",
                "fieldErrors": {}
            })
            return

        try:
            body = raw_body.decode("utf-8")
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.send_json_response(400, {
                "success": False,
                "error": f"Невалидный JSON: {str(e)}",
                "fieldErrors": {}
            })
            return
        except Exception as e:
            self.send_json_response(400, {
                "success": False,
                "error": f"Ошибка декодирования запроса: {str(e)}",
                "fieldErrors": {}
            })
            return

        if not isinstance(payload, dict):
            self.send_json_response(400, {
                "success": False,
                "error": "Тело запроса должно быть JSON-объектом.",
                "fieldErrors": {}
            })
            return

        idempotency_key = payload.get("idempotencyKey") or payload.get("idempotency_key")
        if isinstance(idempotency_key, str):
            idempotency_key = idempotency_key.strip() or None
        else:
            idempotency_key = None

        conn = self.get_db()
        try:
            # Idempotency check: if already processed, return existing submission immediately
            if idempotency_key:
                with conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT * FROM moderation_submissions WHERE idempotency_key = ? LIMIT 1",
                        (idempotency_key,)
                    )
                    existing = cur.fetchone()
                    if existing:
                        self.send_json_response(200, {
                            "success": True,
                            "status": existing["status"],
                            "submissionId": existing["id"],
                            "snapshotHash": existing["snapshot_hash"],
                            "createdAt": existing["created_at"],
                            "isDuplicate": True
                        })
                        return

            # Validation check
            is_valid, err_msg, field_errors = validate_submission_payload(payload)
            if not is_valid:
                self.send_json_response(400, {
                    "success": False,
                    "error": err_msg,
                    "fieldErrors": field_errors
                })
                return

            draft_id = payload.get("draftId") or payload.get("draft_id")
            title = payload.get("title").strip()
            raw_html = payload.get("html") or payload.get("article_html") or payload.get("content") or ""
            article_html = sanitize_article_html(raw_html)
            delta = payload.get("delta") or payload.get("article_delta")
            pub_settings = payload.get("publicationSettings") or payload.get("publication_settings")
            author_id = curr_user["id"]

            # Company publication authorization check
            comp_id = pub_settings.get("companyId") or pub_settings.get("company_id")
            if comp_id:
                with conn:
                    cur = conn.cursor()
                    cur.execute("SELECT id FROM companies WHERE id = ?", (comp_id,))
                    comp_row = cur.fetchone()
                if not comp_row:
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Указанная компания не найдена.",
                        "fieldErrors": {
                            "companyId": "Указанная компания не существует."
                        }
                    })
                    return

                user_role = curr_user.get("role", "user")
                if not can_user_publish_for_company(conn, author_id, comp_id, user_role=user_role):
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Отказано в доступе: у вас нет прав на публикацию от имени выбранной компании.",
                        "fieldErrors": {
                            "companyId": "Вы не являетесь владельцем или участником этой компании."
                        }
                    })
                    return
                pub_settings["companyId"] = comp_id

            # Status transition check: cannot transition if already approved or in terminal invalid state
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, status FROM moderation_submissions WHERE draft_id = ? ORDER BY created_at DESC LIMIT 1",
                    (draft_id,)
                )
                last_sub = cur.fetchone()
                if last_sub and last_sub["status"] == "approved":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Черновик уже одобрен модератором и не может быть отправлен повторно.",
                        "fieldErrors": {
                            "status": "Статья уже имеет статус 'approved'."
                        }
                    })
                    return
                if last_sub and last_sub["status"] == "rejected":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Материал отклонен модератором и не может быть отправлен повторно.",
                        "fieldErrors": {
                            "status": "Материал отклонен модератором."
                        }
                    })
                    return

            # Compute deterministic SHA-256 snapshot hash
            snapshot_hash = compute_snapshot_hash(title, article_html, pub_settings)

            submission_id = f"sub_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            pub_settings_json = json.dumps(pub_settings, ensure_ascii=False)
            article_delta_json = json.dumps(delta, ensure_ascii=False) if delta is not None else None

            # Insert immutable snapshot row
            try:
                with conn:
                    conn.execute("""
                        INSERT INTO moderation_submissions (
                            id, draft_id, title, author_id, status, publication_settings,
                            article_html, article_delta, idempotency_key, snapshot_hash,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'pending_moderation', ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        submission_id, draft_id, title, author_id, pub_settings_json,
                        article_html, article_delta_json, idempotency_key, snapshot_hash,
                        now_iso, now_iso
                    ))
                    # A newer version replaces earlier unreviewed versions of the same material in the queue
                    conn.execute("""
                        UPDATE moderation_submissions
                        SET status = 'draft', claimed_by = NULL, claimed_at = NULL, updated_at = ?
                        WHERE draft_id = ? AND author_id = ? AND status = 'pending_moderation' AND id != ?
                    """, (now_iso, draft_id, author_id, submission_id))
            except sqlite3.IntegrityError:
                # Race condition with identical idempotency_key
                if idempotency_key:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT * FROM moderation_submissions WHERE idempotency_key = ? LIMIT 1",
                        (idempotency_key,)
                    )
                    dup_row = cur.fetchone()
                    if dup_row:
                        self.send_json_response(200, {
                            "success": True,
                            "status": dup_row["status"],
                            "submissionId": dup_row["id"],
                            "id": dup_row["id"],
                            "url": f"/article.html?id={dup_row['id']}",
                            "snapshotHash": dup_row["snapshot_hash"],
                            "createdAt": dup_row["created_at"],
                            "isDuplicate": True
                        })
                        return

                self.send_json_response(500, {
                    "success": False,
                    "error": "Ошибка сохранения заявки в базу данных (Integrity Error)",
                    "fieldErrors": {}
                })
                return

            self.send_json_response(200, {
                "success": True,
                "status": "pending_moderation",
                "submissionId": submission_id,
                "id": submission_id,
                "url": f"/article.html?id={submission_id}",
                "snapshotHash": snapshot_hash,
                "createdAt": now_iso
            })
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def handle_moderation_status(self, parsed_url):
        """
        GET /api/moderation/status?draftId=...
        Returns status of the latest submission for the draft.
        Requires authentication. Allowed only for the submission author or moderator/admin.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация для проверки статуса модерации",
                "requireAuth": True
            })
            return

        query = urllib.parse.parse_qs(parsed_url.query)
        draft_id = query.get("draftId", [None])[0] or query.get("draft_id", [None])[0]

        if not draft_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Параметр draftId обязателен",
                "fieldErrors": {"draftId": "Параметр draftId обязателен"}
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT * FROM moderation_submissions WHERE draft_id = ? ORDER BY created_at DESC LIMIT 1",
                    (draft_id,)
                )
                row = cur.fetchone()

            if not row:
                self.send_json_response(404, {
                    "success": False,
                    "status": "draft",
                    "submissionId": None,
                    "error": "Заявка на модерацию для данного черновика не найдена"
                })
                return

            if not self.is_moderator_or_admin(user) and row["author_id"] != user["id"]:
                self.send_json_response(403, {
                    "success": False,
                    "error": "Доступ запрещен: вы можете просматривать статус только своих заявок"
                })
                return

            self.send_json_response(200, {
                "success": True,
                "status": row["status"],
                "submissionId": row["id"],
                "snapshotHash": row["snapshot_hash"],
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"]
            })
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def handle_moderation_list(self):
        """
        GET /api/moderation/list
        Returns array of submissions in queue (for moderator or admin access only).
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация для доступа к очереди модерации",
                "requireAuth": True
            })
            return

        if not self.is_moderator_or_admin(user):
            self.send_json_response(403, {
                "success": False,
                "error": "Доступ запрещен: требуется роль модератора или администратора"
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM moderation_submissions ORDER BY created_at DESC")
                rows = cur.fetchall()

            submissions = []
            for row in rows:
                try:
                    settings = json.loads(row["publication_settings"]) if row["publication_settings"] else {}
                except Exception:
                    settings = {}

                try:
                    delta = json.loads(row["article_delta"]) if row["article_delta"] else None
                except Exception:
                    delta = None

                submissions.append({
                    "id": row["id"],
                    "draftId": row["draft_id"],
                    "title": row["title"],
                    "authorId": row["author_id"],
                    "status": row["status"],
                    "publicationSettings": settings,
                    "articleHtml": row["article_html"],
                    "articleDelta": delta,
                    "idempotencyKey": row["idempotency_key"],
                    "snapshotHash": row["snapshot_hash"],
                    "createdAt": row["created_at"],
                    "updatedAt": row["updated_at"]
                })

            self.send_json_response(200, {
                "success": True,
                "submissions": submissions,
                "count": len(submissions)
            })
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def handle_my_submissions(self, parsed_url):
        """
        GET /api/moderation/my?status=
        The latest version of each material the current user sent to moderation, with the decision.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация", "requireAuth": True})
            return
        query = urllib.parse.parse_qs(parsed_url.query)
        status_filter = query.get("status", [""])[0]
        conn = self.get_db()
        try:
            rows = conn.execute("""
                SELECT ms.* FROM moderation_submissions ms
                WHERE ms.author_id = ? AND ms.status != 'draft'
                  AND ms.created_at = (
                      SELECT MAX(x.created_at) FROM moderation_submissions x
                      WHERE x.draft_id = ms.draft_id AND x.author_id = ms.author_id AND x.status != 'draft'
                  )
                ORDER BY COALESCE(ms.reviewed_at, ms.created_at) DESC
                LIMIT 200
            """, (user["id"],)).fetchall()
        finally:
            conn.close()
        items = []
        counts = {"pending_moderation": 0, "needs_revision": 0, "approved": 0, "rejected": 0}
        for r in rows:
            if r["status"] in counts:
                counts[r["status"]] += 1
            if status_filter and r["status"] != status_filter:
                continue
            items.append({
                "id": r["id"],
                "draftId": r["draft_id"],
                "title": r["title"],
                "materialType": material_type_of(r["publication_settings"]),
                "status": r["status"],
                "statusLabel": STATUS_LABELS.get(r["status"], r["status"]),
                "reviewComment": r["review_comment"],
                "reviewReasonLabel": REJECT_REASONS.get(r["review_reason_code"] or "", None),
                "reviewedAt": r["reviewed_at"],
                "createdAt": r["created_at"],
                "url": f"/article.html?id={urllib.parse.quote(r['id'])}" if r["status"] == "approved" else None,
            })
        self.send_json_response(200, {"success": True, "items": items, "counts": counts})

    def handle_my_submission(self, submission_id):
        """
        GET /api/moderation/my/<id>
        Full snapshot of the current user's own material returned for revision, to reopen it in the editor.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {"success": False, "error": "Необходима авторизация", "requireAuth": True})
            return
        conn = self.get_db()
        try:
            row = conn.execute("SELECT * FROM moderation_submissions WHERE id = ?", (submission_id,)).fetchone()
        finally:
            conn.close()
        if not row or row["author_id"] != user["id"]:
            self.send_json_response(404, {"success": False, "error": "Материал не найден"})
            return
        try:
            settings = json.loads(row["publication_settings"] or "{}")
        except ValueError:
            settings = {}
        try:
            delta = json.loads(row["article_delta"]) if row["article_delta"] else None
        except ValueError:
            delta = None
        self.send_json_response(200, {"success": True, "submission": {
            "id": row["id"],
            "draftId": row["draft_id"],
            "title": row["title"],
            "materialType": material_type_of(row["publication_settings"]),
            "status": row["status"],
            "statusLabel": STATUS_LABELS.get(row["status"], row["status"]),
            "reviewComment": row["review_comment"],
            "reviewReasonLabel": REJECT_REASONS.get(row["review_reason_code"] or "", None),
            "html": row["article_html"],
            "delta": delta,
            "publicationSettings": settings,
            "canRevise": row["status"] == "needs_revision",
        }})

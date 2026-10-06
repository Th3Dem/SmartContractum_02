"""Comments and answers: listing, posting, editing, deleting, subscriptions, solutions."""
import datetime
import json
import sqlite3
import time
import uuid

from backend.config import MAX_JSON_BODY_BYTES


class CommentsHandlers:
    def handle_comment_subscribe_toggle(self, comment_id: str):
        """
        POST /api/comments/<id>/subscribe
        Toggles subscription to replies on a comment or answer.
        Requires authentication (returns 401 if unauthorized).
        Toggles subscription: if exists, delete and return {"success": true, "subscribed": false};
        if not exists, insert and return {"success": true, "subscribed": true}.
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация",
                "code": "AUTH_REQUIRED",
                "requireAuth": True
            })
            return

        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        if not comment_id and isinstance(payload, dict):
            comment_id = str(payload.get("commentId") or payload.get("comment_id") or "").strip()

        if not comment_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Идентификатор комментария обязателен",
                "code": "INVALID_COMMENT_ID"
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM article_comments WHERE id = ?", (comment_id,))
                comment = cur.fetchone()
                if not comment:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Комментарий не найден",
                        "code": "NOT_FOUND"
                    })
                    return

                cur.execute(
                    "SELECT id FROM comment_subscriptions WHERE comment_id = ? AND user_id = ?",
                    (comment_id, user["id"])
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute("DELETE FROM comment_subscriptions WHERE id = ?", (existing["id"],))
                    subscribed = False
                else:
                    sub_id = f"csub_{uuid.uuid4().hex[:12]}"
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur.execute("""
                        INSERT INTO comment_subscriptions (id, comment_id, user_id, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (sub_id, comment_id, user["id"], now_iso))
                    subscribed = True
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "subscribed": subscribed
        })

    def handle_get_comment_subscriptions(self):
        """
        GET /api/comments/subscriptions
        Returns list of comment IDs the current user is subscribed to:
        {"success": true, "subscriptions": [...]}
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Требуется авторизация",
                "code": "AUTH_REQUIRED",
                "requireAuth": True
            })
            return

        conn = self.get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT comment_id FROM comment_subscriptions WHERE user_id = ? ORDER BY created_at ASC",
                (user["id"],)
            )
            rows = cur.fetchall()
            sub_ids = [r["comment_id"] for r in rows]
        finally:
            conn.close()

        self.send_json_response(200, {
            "success": True,
            "subscriptions": sub_ids
        })

    def handle_get_article_comments(self, article_id: str):
        """
        GET /api/articles/<id>/comments
        Returns structured comments and discussions for the article/question. Accessible to guests.
        Includes answers with nested comments, questionComments, myAnswerId, counters, and flat comments array.
        Enforces:
        - parentCommentId included in DTO
        - Accurate counters: answersCount, questionCommentsCount, commentsCount, discussionCount
        - Deletion placeholders for deleted nodes with active published descendants
        - Strict isolation: orphaned child comments excluded from questionComments
        """
        if not article_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор статьи"
            })
            return

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id, draft_id, status FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (article_id, article_id))
            art_row = cur.fetchone()
            real_id = art_row["id"] if art_row else article_id
            draft_id = art_row["draft_id"] if art_row else None
            parent_is_approved = bool(art_row and art_row["status"] == "approved")

            target_article_ids = [real_id]
            if draft_id and draft_id != real_id:
                target_article_ids.append(draft_id)
            placeholders = ",".join("?" for _ in target_article_ids)

            cur.execute(f"""
                SELECT ac.id, ac.article_id, ac.user_id, 
                       COALESCE(up.name, u.name, ac.author_name) AS author_name, 
                       COALESCE(up.avatar, u.avatar, ac.author_avatar) AS author_avatar, 
                       ac.content, ac.status, ac.comment_type, ac.is_solution, 
                       ac.parent_answer_id, ac.parent_comment_id,
                       ac.client_operation_id, ac.updated_at, ac.revision, ac.created_at
                FROM article_comments ac
                LEFT JOIN users u ON ac.user_id = u.id
                LEFT JOIN user_profiles up ON ac.user_id = up.user_id
                WHERE ac.article_id IN ({placeholders}) AND ac.status IN ('published', 'deleted')
                ORDER BY ac.is_solution DESC, ac.created_at ASC
            """, tuple(target_article_ids))
            rows = cur.fetchall()

            cur.execute(f"SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id IN ({placeholders}) AND status = 'published' AND comment_type = 'comment'", tuple(target_article_ids))
            cur.execute(f"SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id IN ({placeholders}) AND status = 'published' AND comment_type = 'answer'", tuple(target_article_ids))

            curr_user = self.get_current_user()
            curr_user_id = curr_user["id"] if curr_user else None

            all_comm_ids = [r["id"] for r in rows]
            comment_scores = {}
            user_comment_votes = {}
            user_comment_reports = set()
            user_comment_saves = set()
            comment_save_counts = {}
            if all_comm_ids:
                for i in range(0, len(all_comm_ids), 500):
                    chunk = all_comm_ids[i:i+500]
                    placeholders = ",".join("?" for _ in chunk)
                    cur.execute(
                        f"SELECT comment_id, COALESCE(SUM(value), 0) AS score FROM comment_votes WHERE comment_id IN ({placeholders}) GROUP BY comment_id",
                        tuple(chunk)
                    )
                    for cr in cur.fetchall():
                        comment_scores[cr["comment_id"]] = cr["score"]

                    cur.execute(
                        f"SELECT comment_id, COUNT(*) AS cnt FROM comment_saves WHERE comment_id IN ({placeholders}) GROUP BY comment_id",
                        tuple(chunk)
                    )
                    for cr in cur.fetchall():
                        comment_save_counts[cr["comment_id"]] = cr["cnt"]

                    if curr_user_id:
                        cur.execute(
                            f"SELECT comment_id, value FROM comment_votes WHERE user_id = ? AND comment_id IN ({placeholders})",
                            (curr_user_id, *chunk)
                        )
                        for cr in cur.fetchall():
                            user_comment_votes[cr["comment_id"]] = cr["value"]

                        cur.execute(
                            f"SELECT comment_id FROM comment_reports WHERE user_id = ? AND comment_id IN ({placeholders})",
                            (curr_user_id, *chunk)
                        )
                        for cr in cur.fetchall():
                            user_comment_reports.add(cr["comment_id"])

                        cur.execute(
                            f"SELECT comment_id FROM comment_saves WHERE user_id = ? AND comment_id IN ({placeholders})",
                            (curr_user_id, *chunk)
                        )
                        for cr in cur.fetchall():
                            user_comment_saves.add(cr["comment_id"])

        row_map = {r["id"]: r for r in rows}
        published_rows = [r for r in rows if r["status"] == "published"]

        # Track ancestor IDs that are required to display published descendants
        needed_ancestors = set()
        for r in published_rows:
            curr_pid = r["parent_comment_id"] if "parent_comment_id" in r.keys() else None
            visited = set()
            while curr_pid and curr_pid in row_map and curr_pid not in visited:
                visited.add(curr_pid)
                needed_ancestors.add(curr_pid)
                p_row = row_map[curr_pid]
                curr_pid = p_row["parent_comment_id"] if "parent_comment_id" in p_row.keys() else None

            p_ans = r["parent_answer_id"] if "parent_answer_id" in r.keys() else None
            if p_ans and p_ans in row_map:
                needed_ancestors.add(p_ans)

        comments = []
        answers_map = {}
        child_comments = []
        question_comments = []
        my_answer_id = None
        has_solution = False
        solution_comment_id = None

        for r in rows:
            is_del = (r["status"] == "deleted")
            # If deleted and not an ancestor of any published descendant, omit completely
            if is_del and r["id"] not in needed_ancestors:
                continue

            ctype = (r["comment_type"] if "comment_type" in r.keys() else None) or "comment"
            is_sol = bool(r["is_solution"]) if "is_solution" in r.keys() and r["is_solution"] is not None else False
            rev = r["revision"] if "revision" in r.keys() and r["revision"] is not None else 1
            upd_at = r["updated_at"] if "updated_at" in r.keys() else None
            p_ans_id = r["parent_answer_id"] if "parent_answer_id" in r.keys() else None
            p_comm_id = r["parent_comment_id"] if "parent_comment_id" in r.keys() else None
            client_op_id = r["client_operation_id"] if "client_operation_id" in r.keys() else None
            comm_score = comment_scores.get(r["id"], 0)
            comm_my_vote = user_comment_votes.get(r["id"], 0)
            comm_is_author = bool(curr_user and r["user_id"] == curr_user_id)
            comm_can_vote = bool(curr_user and parent_is_approved and not is_del and r["status"] == "published" and not comm_is_author)

            if not is_del and is_sol and ctype == "answer":
                has_solution = True
                solution_comment_id = r["id"]

            if is_del:
                dto = {
                    "id": r["id"],
                    "articleId": r["article_id"],
                    "userId": r["user_id"],
                    "authorName": "Удаленный комментарий",
                    "authorAvatar": None,
                    "content": "Комментарий удален",
                    "commentType": ctype,
                    "isSolution": False,
                    "parentAnswerId": p_ans_id,
                    "parentCommentId": p_comm_id,
                    "clientOperationId": client_op_id,
                    "isDeleted": True,
                    "updatedAt": upd_at,
                    "revision": rev,
                    "createdAt": r["created_at"],
                    "score": comm_score,
                    "myVote": comm_my_vote,
                    "canVote": False,
                    "isAuthor": False,
                    "hasReported": (r["id"] in user_comment_reports),
                    "isReported": (r["id"] in user_comment_reports),
                    "isSaved": (r["id"] in user_comment_saves),
                    "hasSaved": (r["id"] in user_comment_saves),
                    "savesCount": comment_save_counts.get(r["id"], 0)
                }
            else:
                dto = {
                    "id": r["id"],
                    "articleId": r["article_id"],
                    "userId": r["user_id"],
                    "authorName": r["author_name"],
                    "authorAvatar": r["author_avatar"] or None,
                    "content": r["content"],
                    "commentType": ctype,
                    "isSolution": is_sol,
                    "parentAnswerId": p_ans_id,
                    "parentCommentId": p_comm_id,
                    "clientOperationId": client_op_id,
                    "isDeleted": False,
                    "updatedAt": upd_at,
                    "revision": rev,
                    "createdAt": r["created_at"],
                    "score": comm_score,
                    "myVote": comm_my_vote,
                    "canVote": comm_can_vote,
                    "isAuthor": comm_is_author,
                    "hasReported": (r["id"] in user_comment_reports),
                    "isReported": (r["id"] in user_comment_reports),
                    "isSaved": (r["id"] in user_comment_saves),
                    "hasSaved": (r["id"] in user_comment_saves),
                    "savesCount": comment_save_counts.get(r["id"], 0)
                }

            if ctype == "answer":
                ans_obj = dict(dto)
                ans_obj["comments"] = []
                ans_obj["commentsCount"] = 0
                answers_map[r["id"]] = ans_obj
                if not is_del and curr_user_id and r["user_id"] == curr_user_id and my_answer_id is None:
                    my_answer_id = r["id"]
                comments.append(dto)
            else:
                if p_ans_id:
                    child_comments.append(dto)
                else:
                    if p_comm_id is not None and p_comm_id not in row_map:
                        # Orphaned comment without valid parent comment
                        continue
                    question_comments.append(dto)
                    comments.append(dto)

        for child in child_comments:
            pid = child["parentAnswerId"]
            if pid in answers_map:
                answers_map[pid]["comments"].append(child)
                if not child.get("isDeleted"):
                    answers_map[pid]["commentsCount"] += 1
                comments.append(child)
            else:
                # Invariant: do NOT dump orphaned child comments into questionComments
                pass

        answers_list = list(answers_map.values())
        answers_count = sum(1 for a in answers_list if not a.get("isDeleted"))
        question_comments_count = sum(1 for q in question_comments if not q.get("isDeleted") and q.get("parentAnswerId") is None)
        comments_count = sum(1 for c in comments if c.get("commentType") == "comment" and not c.get("isDeleted"))
        discussion_count = answers_count + comments_count

        self.send_json_response(200, {
            "success": True,
            "comments": comments,
            "answers": answers_list,
            "questionComments": question_comments,
            "myAnswerId": my_answer_id,
            "answersCount": answers_count,
            "questionCommentsCount": question_comments_count,
            "commentsCount": comments_count,
            "discussionCount": discussion_count,
            "total": len(comments),
            "hasSolution": has_solution,
            "solutionCommentId": solution_comment_id
        })

    def handle_post_article_comment(self, article_id: str):
        """
        POST /api/articles/<id>/comments or POST /api/comments
        Adds an answer or comment to the specified article/question.
        Requires authentication (401 requireAuth).
        Validates content: non-empty, stripped, max 5000 chars. Stores plain-text.
        Strictly validates commentType: must be 'comment' or 'answer' (400).
        Supports parentCommentId and clientOperationId.
        Enforces invariants:
          - Only questions can receive answers (400).
          - Single active published answer per user per question (409 ANSWER_ALREADY_EXISTS).
          - Validates parentCommentId (must be published comment on same publication, comment_type == 'comment').
          - Automatically derives parentAnswerId from parent comment. Reject contradictory parentAnswerId (400).
          - Cycle detection and depth check (depth limit 20 levels; 21st rejected with 400).
          - Idempotency with clientOperationId: replay with same payload returns 200/201 without duplicate,
            replay with conflicting payload returns 409 OPERATION_ID_CONFLICT.
          - Atomic notifications in the same transaction (targeted to immediate parent author, no self-notifications).
        """
        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if payload is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для отправки комментария необходимо войти",
                "requireAuth": True
            })
            return

        if not article_id:
            article_id = payload.get("articleId") or payload.get("article_id") or ""

        if not article_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор статьи"
            })
            return

        raw_comment_type = payload.get("commentType") if "commentType" in payload else payload.get("comment_type")
        if not isinstance(raw_comment_type, str) or raw_comment_type.strip().lower() not in ("comment", "answer"):
            self.send_json_response(400, {
                "success": False,
                "error": "Некорректный или отсутствующий commentType. Допустимые значения: 'comment', 'answer'."
            })
            return
        comment_type = raw_comment_type.strip().lower()

        content = payload.get("content")
        if content is None or not isinstance(content, str) or not content.strip():
            self.send_json_response(400, {
                "success": False,
                "error": "Комментарий не может быть пустым"
            })
            return

        stripped_content = content.strip()
        if len(stripped_content) > 5000:
            self.send_json_response(400, {
                "success": False,
                "error": "Комментарий не должен превышать 5000 символов"
            })
            return

        raw_parent_comm = payload.get("parentCommentId") if "parentCommentId" in payload else payload.get("parent_comment_id")
        raw_parent_ans = payload.get("parentAnswerId") if "parentAnswerId" in payload else payload.get("parent_answer_id")
        raw_client_op = payload.get("clientOperationId") if "clientOperationId" in payload else payload.get("client_operation_id")

        target_parent_comm_id = raw_parent_comm.strip() if isinstance(raw_parent_comm, str) and raw_parent_comm.strip() else None
        target_parent_ans_id = raw_parent_ans.strip() if isinstance(raw_parent_ans, str) and raw_parent_ans.strip() else None
        client_op_id = raw_client_op.strip() if isinstance(raw_client_op, str) and raw_client_op.strip() else None

        conn = self.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT id, title, author_id, publication_settings FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (article_id, article_id))
            art_row = cur.fetchone()
            if not art_row:
                self.send_json_response(404, {
                    "success": False,
                    "error": "Статья не найдена"
                })
                return

            real_id = art_row["id"]
            user_id = user["id"]
            author_name = user.get("name") or (f"Пользователь #{user_id[:6]}" if user_id else "Читатель")
            author_avatar = user.get("avatar") or None

            material_type = "article"
            art_settings = {}
            try:
                art_settings = json.loads(art_row["publication_settings"]) if art_row["publication_settings"] else {}
                material_type = (art_settings.get("materialType") or art_settings.get("type") or "article").strip().lower()
            except Exception:
                pass

            art_title = art_row["title"] or "Публикация"
            art_author_id = art_row["author_id"]

            if comment_type == "answer":
                if material_type != "question":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Ответ (answer) возможен только для публикаций с типом 'Вопрос' (materialType = 'question')."
                    })
                    return

                if target_parent_comm_id is not None or target_parent_ans_id is not None:
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Ответ не может иметь родительский комментарий или ответ."
                    })
                    return

                recipients_set = {art_author_id}
                notification_type = "new_answer"
                notification_title = "Новый ответ на ваш вопрос"
                notification_message = f"Пользователь {author_name} ответил на ваш вопрос «{art_title[:60]}»"
            else:
                # comment_type == 'comment'
                if target_parent_comm_id is not None:
                    cur.execute("""
                        SELECT id, user_id, article_id, comment_type, status, parent_answer_id, parent_comment_id
                        FROM article_comments
                        WHERE id = ? LIMIT 1
                    """, (target_parent_comm_id,))
                    p_comm_row = cur.fetchone()
                    if not p_comm_row or p_comm_row["status"] != "published":
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Указанный родительский комментарий не найден или не опубликован."
                        })
                        return

                    if p_comm_row["article_id"] != real_id:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Родительский комментарий принадлежит другой публикации."
                        })
                        return

                    if p_comm_row["comment_type"] != "comment":
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Родительский комментарий не может быть ответом. Для ответа на ответ используйте parentAnswerId."
                        })
                        return

                    # Automatically derive parent_answer_id from parent comment
                    derived_ans_id = p_comm_row["parent_answer_id"]
                    if target_parent_ans_id is not None and target_parent_ans_id != derived_ans_id:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Указанный parentAnswerId противоречит родительскому комментарию."
                        })
                        return
                    target_parent_ans_id = derived_ans_id

                    # Cycle detection and depth check: walk up parent_comment_id chain
                    depth = 1
                    curr_anc_id = p_comm_row["parent_comment_id"]
                    visited_anc = {target_parent_comm_id}
                    while curr_anc_id is not None:
                        depth += 1
                        if curr_anc_id in visited_anc:
                            self.send_json_response(400, {
                                "success": False,
                                "error": "Обнаружен цикл в иерархии комментариев."
                            })
                            return
                        visited_anc.add(curr_anc_id)
                        if depth >= 20:
                            self.send_json_response(400, {
                                "success": False,
                                "error": "Превышена максимальная глубина вложенности комментариев (максимум 20 уровней)."
                            })
                            return
                        cur.execute("SELECT parent_comment_id FROM article_comments WHERE id = ? LIMIT 1", (curr_anc_id,))
                        anc_r = cur.fetchone()
                        if not anc_r:
                            break
                        curr_anc_id = anc_r["parent_comment_id"]

                    recipients_set = {p_comm_row["user_id"]}
                    notification_type = "new_reply"
                    notification_title = "Новый ответ в обсуждении"
                    notification_message = f"Пользователь {author_name} ответил на ваш комментарий к «{art_title[:60]}»"
                elif target_parent_ans_id is not None:
                    # Direct comment on answer
                    cur.execute("""
                        SELECT id, user_id, article_id, comment_type, status
                        FROM article_comments
                        WHERE id = ? LIMIT 1
                    """, (target_parent_ans_id,))
                    p_ans_row = cur.fetchone()
                    if not p_ans_row or p_ans_row["comment_type"] != "answer" or p_ans_row["status"] != "published" or p_ans_row["article_id"] != real_id:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Указанный ответ не найден или не принадлежит данному вопросу."
                        })
                        return

                    recipients_set = {p_ans_row["user_id"]}
                    notification_type = "new_reply"
                    notification_title = "Новый ответ в обсуждении"
                    notification_message = f"Пользователь {author_name} ответил на ваш ответ к «{art_title[:60]}»"
                else:
                    # Root comment on article or question
                    recipients_set = {art_author_id}
                    company_id = art_settings.get("companyId") or art_settings.get("company_id")
                    if company_id:
                        cur.execute("SELECT owner_id FROM companies WHERE id = ?", (company_id,))
                        comp_row = cur.fetchone()
                        if comp_row and comp_row["owner_id"]:
                            recipients_set.add(comp_row["owner_id"])

                    notification_type = "new_reply"
                    notification_title = "Новый комментарий"
                    notification_message = f"Пользователь {author_name} оставил комментарий к «{art_title[:60]}»"

            # Idempotency check with clientOperationId
            if client_op_id:
                cur.execute("""
                    SELECT * FROM article_comments
                    WHERE user_id = ? AND client_operation_id = ?
                    LIMIT 1
                """, (user_id, client_op_id))
                existing_op = cur.fetchone()
                if existing_op:
                    same_art = (existing_op["article_id"] == real_id)
                    same_content = (existing_op["content"] == stripped_content)
                    same_type = (existing_op["comment_type"] == comment_type)
                    same_p_comm = ((existing_op["parent_comment_id"] or None) == target_parent_comm_id)
                    same_p_ans = ((existing_op["parent_answer_id"] or None) == target_parent_ans_id)

                    if same_art and same_content and same_type and same_p_comm and same_p_ans:
                        cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = ? AND status = 'published' AND comment_type = 'comment'", (real_id,))
                        comments_count = cur.fetchone()["cnt"]
                        cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = ? AND status = 'published' AND comment_type = 'answer'", (real_id,))
                        answers_count = cur.fetchone()["cnt"]
                        discussion_count = comments_count + answers_count
                        self.send_json_response(200, {
                            "success": True,
                            "comment": {
                                "id": existing_op["id"],
                                "articleId": existing_op["article_id"],
                                "userId": existing_op["user_id"],
                                "authorName": existing_op["author_name"],
                                "authorAvatar": existing_op["author_avatar"] or None,
                                "content": existing_op["content"],
                                "commentType": existing_op["comment_type"],
                                "isSolution": bool(existing_op["is_solution"]),
                                "parentAnswerId": existing_op["parent_answer_id"],
                                "parentCommentId": existing_op["parent_comment_id"],
                                "clientOperationId": existing_op["client_operation_id"],
                                "updatedAt": existing_op["updated_at"],
                                "revision": existing_op["revision"] if "revision" in existing_op.keys() and existing_op["revision"] is not None else 1,
                                "createdAt": existing_op["created_at"]
                            },
                            "commentsCount": comments_count,
                            "answersCount": answers_count,
                            "discussionCount": discussion_count,
                            "isDuplicate": True
                        })
                        return
                    else:
                        self.send_json_response(409, {
                            "success": False,
                            "error": "Запрос с данным clientOperationId уже обработан с другими параметрами.",
                            "code": "OPERATION_ID_CONFLICT"
                        })
                        return

            if comment_type == "answer":
                cur.execute("""
                    SELECT id FROM article_comments
                    WHERE article_id = ? AND user_id = ? AND comment_type = 'answer' AND status = 'published'
                    LIMIT 1
                """, (real_id, user_id))
                existing_answer = cur.fetchone()
                if existing_answer:
                    self.send_json_response(409, {
                        "success": False,
                        "error": "Вы уже опубликовали ответ на этот вопрос",
                        "code": "ANSWER_ALREADY_EXISTS",
                        "myAnswerId": existing_answer["id"]
                    })
                    return

            comment_id = f"comm_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

            try:
                cur.execute("""
                    INSERT INTO article_comments (
                        id, article_id, user_id, author_name, author_avatar, content, status,
                        comment_type, is_solution, parent_answer_id, parent_comment_id, client_operation_id,
                        updated_at, revision, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'published', ?, 0, ?, ?, ?, NULL, 1, ?)
                """, (
                    comment_id, real_id, user_id, author_name, author_avatar,
                    stripped_content, comment_type, target_parent_ans_id,
                    target_parent_comm_id, client_op_id, now_iso
                ))
            except sqlite3.IntegrityError:
                if client_op_id:
                    cur.execute("""
                        SELECT * FROM article_comments
                        WHERE user_id = ? AND client_operation_id = ?
                        LIMIT 1
                    """, (user_id, client_op_id))
                    race_row = cur.fetchone()
                    if race_row:
                        same_art = (race_row["article_id"] == real_id)
                        same_content = (race_row["content"] == stripped_content)
                        same_type = (race_row["comment_type"] == comment_type)
                        same_p_comm = ((race_row["parent_comment_id"] or None) == target_parent_comm_id)
                        same_p_ans = ((race_row["parent_answer_id"] or None) == target_parent_ans_id)
                        if same_art and same_content and same_type and same_p_comm and same_p_ans:
                            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = ? AND status = 'published' AND comment_type = 'comment'", (real_id,))
                            comments_count = cur.fetchone()["cnt"]
                            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = ? AND status = 'published' AND comment_type = 'answer'", (real_id,))
                            answers_count = cur.fetchone()["cnt"]
                            discussion_count = comments_count + answers_count
                            self.send_json_response(200, {
                                "success": True,
                                "comment": {
                                    "id": race_row["id"],
                                    "articleId": race_row["article_id"],
                                    "userId": race_row["user_id"],
                                    "authorName": race_row["author_name"],
                                    "authorAvatar": race_row["author_avatar"] or None,
                                    "content": race_row["content"],
                                    "commentType": race_row["comment_type"],
                                    "isSolution": bool(race_row["is_solution"]),
                                    "parentAnswerId": race_row["parent_answer_id"],
                                    "parentCommentId": race_row["parent_comment_id"],
                                    "clientOperationId": race_row["client_operation_id"],
                                    "updatedAt": race_row["updated_at"],
                                    "revision": race_row["revision"] if "revision" in race_row.keys() and race_row["revision"] is not None else 1,
                                    "createdAt": race_row["created_at"]
                                },
                                "commentsCount": comments_count,
                                "answersCount": answers_count,
                                "discussionCount": discussion_count,
                                "isDuplicate": True
                            })
                            return
                        else:
                            self.send_json_response(409, {
                                "success": False,
                                "error": "Запрос с данным clientOperationId уже обработан с другими параметрами.",
                                "code": "OPERATION_ID_CONFLICT"
                            })
                            return
                if comment_type == "answer":
                    cur.execute("""
                        SELECT id FROM article_comments
                        WHERE article_id = ? AND user_id = ? AND comment_type = 'answer' AND status = 'published'
                        LIMIT 1
                    """, (real_id, user_id))
                    existing_ans = cur.fetchone()
                    my_id = existing_ans["id"] if existing_ans else ""
                    self.send_json_response(409, {
                        "success": False,
                        "error": "Вы уже опубликовали ответ на этот вопрос",
                        "code": "ANSWER_ALREADY_EXISTS",
                        "myAnswerId": my_id
                    })
                    return
                raise

            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = ? AND status = 'published' AND comment_type = 'comment'", (real_id,))
            comments_count = cur.fetchone()["cnt"]
            cur.execute("SELECT COUNT(*) AS cnt FROM article_comments WHERE article_id = ? AND status = 'published' AND comment_type = 'answer'", (real_id,))
            answers_count = cur.fetchone()["cnt"]
            discussion_count = comments_count + answers_count

            # Notification is sent only if recipient exists and is not the actor
            for recipient_id in recipients_set:
                if recipient_id and recipient_id != user_id:
                    notif_id = f"notif_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
                    cur.execute("""
                        INSERT INTO user_notifications (
                            id, user_id, actor_id, actor_name, article_id, comment_id, type, title, message, is_read, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                    """, (
                        notif_id, recipient_id, user_id, author_name, real_id, comment_id,
                        notification_type, notification_title, notification_message, now_iso
                    ))

        comment_data = {
            "id": comment_id,
            "articleId": real_id,
            "userId": user_id,
            "authorName": author_name,
            "authorAvatar": author_avatar,
            "content": stripped_content,
            "commentType": comment_type,
            "isSolution": False,
            "parentAnswerId": target_parent_ans_id,
            "parentCommentId": target_parent_comm_id,
            "clientOperationId": client_op_id,
            "updatedAt": None,
            "revision": 1,
            "createdAt": now_iso
        }

        self.send_json_response(201, {
            "success": True,
            "comment": comment_data,
            "commentsCount": comments_count,
            "answersCount": answers_count,
            "discussionCount": discussion_count
        })

    def handle_update_article_comment(self, art_id: str, comm_id: str):
        """
        PUT /api/articles/<art_id>/comments/<comm_id> or PUT /api/comments/<comm_id>
        Allows the author of an answer or comment to edit its content.
        Enforces authentication (401), content validation (1..5000 chars),
        published status check, author ownership (403), URL article matching (400),
        immutability of relational bindings (400),
        and optimistic concurrency locking via revision (409 CONCURRENCY_CONFLICT).
        """
        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=False)
        if payload is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для редактирования необходимо войти",
                "requireAuth": True
            })
            return

        if not comm_id:
            comm_id = payload.get("commentId") or payload.get("comment_id") or ""
        if not comm_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор комментария"
            })
            return

        content = payload.get("content")
        if content is None or not isinstance(content, str) or not content.strip():
            self.send_json_response(400, {
                "success": False,
                "error": "Комментарий не может быть пустым"
            })
            return

        stripped_content = content.strip()
        if len(stripped_content) > 5000:
            self.send_json_response(400, {
                "success": False,
                "error": "Комментарий не должен превышать 5000 символов"
            })
            return

        revision_param = payload.get("revision")

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM article_comments WHERE id = ?", (comm_id,))
                comment = cur.fetchone()
                if not comment:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Комментарий не найден"
                    })
                    return

                comm_type = (comment["comment_type"] if "comment_type" in comment.keys() else "").strip().lower()
                comm_status = (comment["status"] if "status" in comment.keys() else "").strip().lower()
                if comm_type not in ("answer", "comment") or comm_status != "published":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Редактирование доступно только для опубликованных комментариев и ответов"
                    })
                    return

                if art_id:
                    cur.execute("SELECT id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (art_id, art_id))
                    art_row = cur.fetchone()
                    canonical_art_id = art_row["id"] if art_row else art_id
                    if canonical_art_id != comment["article_id"]:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Идентификатор публикации не совпадает с комментарием"
                        })
                        return

                if user["id"] != comment["user_id"]:
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Вы можете редактировать только свой комментарий или ответ"
                    })
                    return

                # Enforce 48-hour editing window (Issue #73)
                created_at_raw = comment["created_at"] if "created_at" in comment.keys() else None
                if created_at_raw:
                    try:
                        created_dt = datetime.datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
                        if created_dt.tzinfo is None:
                            created_dt = created_dt.replace(tzinfo=datetime.timezone.utc)
                        now_utc = datetime.datetime.now(datetime.timezone.utc)
                        diff_seconds = (now_utc - created_dt).total_seconds()
                        if diff_seconds >= 48 * 3600:
                            self.send_json_response(403, {
                                "success": False,
                                "error": "Срок редактирования комментария истек (максимум 48 часов с момента публикации)",
                                "code": "EDIT_WINDOW_EXPIRED"
                            })
                            return
                    except Exception:
                        pass

                # Invariant: reject attempts to modify immutable bindings
                if "articleId" in payload or "article_id" in payload:
                    p_art = payload.get("articleId") or payload.get("article_id")
                    cur.execute("SELECT id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (p_art, p_art))
                    p_art_row = cur.fetchone()
                    p_art_canonical = p_art_row["id"] if p_art_row else p_art
                    if p_art_canonical != comment["article_id"]:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Запрещено изменять публикацию комментария"
                        })
                        return

                if "commentType" in payload or "comment_type" in payload:
                    p_ctype = payload.get("commentType") or payload.get("comment_type")
                    if p_ctype != comment["comment_type"]:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Запрещено изменять тип комментария"
                        })
                        return

                if "parentAnswerId" in payload or "parent_answer_id" in payload:
                    p_ans = payload.get("parentAnswerId") if "parentAnswerId" in payload else payload.get("parent_answer_id")
                    if isinstance(p_ans, str) and not p_ans.strip():
                        p_ans = None
                    c_ans = comment["parent_answer_id"] if "parent_answer_id" in comment.keys() else None
                    if p_ans != c_ans:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Запрещено изменять родительский ответ комментария"
                        })
                        return

                if "parentCommentId" in payload or "parent_comment_id" in payload:
                    p_comm = payload.get("parentCommentId") if "parentCommentId" in payload else payload.get("parent_comment_id")
                    if isinstance(p_comm, str) and not p_comm.strip():
                        p_comm = None
                    c_comm = comment["parent_comment_id"] if "parent_comment_id" in comment.keys() else None
                    if p_comm != c_comm:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Запрещено изменять родительский комментарий"
                        })
                        return

                if "isSolution" in payload or "is_solution" in payload:
                    p_sol = payload.get("isSolution") if "isSolution" in payload else payload.get("is_solution")
                    if p_sol is not None:
                        c_sol = bool(comment["is_solution"]) if "is_solution" in comment.keys() and comment["is_solution"] is not None else False
                        if bool(p_sol) != c_sol:
                            self.send_json_response(400, {
                                "success": False,
                                "error": "Запрещено изменять статус решения через редактирование комментария"
                            })
                            return

                current_revision = comment["revision"] if "revision" in comment.keys() and comment["revision"] is not None else 1

                if comm_type == "comment":
                    if revision_param is None:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Поле revision обязательно для редактирования комментария",
                            "code": "REVISION_REQUIRED"
                        })
                        return
                    if not isinstance(revision_param, int) or isinstance(revision_param, bool):
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Поле revision должно быть целым числом",
                            "code": "INVALID_REVISION"
                        })
                        return
                    if revision_param != current_revision:
                        self.send_json_response(409, {
                            "success": False,
                            "error": "Комментарий был изменен в другой сессии",
                            "code": "CONCURRENCY_CONFLICT",
                            "currentRevision": current_revision,
                            "currentContent": comment["content"]
                        })
                        return
                    expected_rev = revision_param
                elif comm_type == "answer":
                    if revision_param is not None:
                        if not isinstance(revision_param, int) or isinstance(revision_param, bool):
                            self.send_json_response(400, {
                                "success": False,
                                "error": "Поле revision должно быть целым числом",
                                "code": "INVALID_REVISION"
                            })
                            return
                        if revision_param != current_revision:
                            self.send_json_response(409, {
                                "success": False,
                                "error": "Комментарий был изменен в другой сессии",
                                "code": "CONCURRENCY_CONFLICT",
                                "currentRevision": current_revision,
                                "currentContent": comment["content"]
                            })
                            return
                        expected_rev = revision_param
                    else:
                        expected_rev = current_revision
                else:
                    expected_rev = current_revision

                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cur.execute("""
                    UPDATE article_comments
                    SET content = ?, updated_at = ?, revision = revision + 1
                    WHERE id = ? AND revision = ?
                """, (stripped_content, now_iso, comm_id, expected_rev))

                if cur.rowcount == 0:
                    cur.execute("SELECT * FROM article_comments WHERE id = ?", (comm_id,))
                    latest = cur.fetchone()
                    latest_rev = latest["revision"] if latest and "revision" in latest.keys() else current_revision
                    latest_cnt = latest["content"] if latest else comment["content"]
                    self.send_json_response(409, {
                        "success": False,
                        "error": "Комментарий был изменен в другой сессии",
                        "code": "CONCURRENCY_CONFLICT",
                        "currentRevision": latest_rev,
                        "currentContent": latest_cnt
                    })
                    return

            new_revision = expected_rev + 1
            self.send_json_response(200, {
                "success": True,
                "comment": {
                    "id": comment["id"],
                    "articleId": comment["article_id"],
                    "userId": comment["user_id"],
                    "authorName": comment["author_name"],
                    "authorAvatar": comment["author_avatar"] or None,
                    "content": stripped_content,
                    "commentType": comment["comment_type"],
                    "isSolution": bool(comment["is_solution"]),
                    "parentAnswerId": comment["parent_answer_id"] if "parent_answer_id" in comment.keys() else None,
                    "parentCommentId": comment["parent_comment_id"] if "parent_comment_id" in comment.keys() else None,
                    "clientOperationId": comment["client_operation_id"] if "client_operation_id" in comment.keys() else None,
                    "revision": new_revision,
                    "updatedAt": now_iso,
                    "createdAt": comment["created_at"]
                }
            })
        finally:
            conn.close()

    def handle_delete_article_comment(self, art_id: str, comm_id: str):
        """
        DELETE /api/articles/<art_id>/comments/<comm_id> or DELETE /api/comments/<comm_id>
        Soft-deletes a comment or answer by setting status = 'deleted'.
        Requires authentication and ownership (or admin role).
        """
        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для удаления необходимо войти",
                "requireAuth": True
            })
            return

        if not comm_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор комментария"
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM article_comments WHERE id = ?", (comm_id,))
                comment = cur.fetchone()
                if not comment:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Комментарий не найден"
                    })
                    return

                if art_id:
                    cur.execute("SELECT id, draft_id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (art_id, art_id))
                    art_row = cur.fetchone()
                    canonical_art_id = art_row["id"] if art_row else art_id
                    draft_art_id = art_row["draft_id"] if art_row else None
                    valid_art_ids = {canonical_art_id}
                    if draft_art_id:
                        valid_art_ids.add(draft_art_id)
                    if comment["article_id"] not in valid_art_ids:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Идентификатор публикации не совпадает с комментарием"
                        })
                        return

                user_id = user["id"]
                user_role = user.get("role", "user")
                if user_id != comment["user_id"] and user_role != "admin":
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Вы можете удалять только свои комментарии"
                    })
                    return

                comm_type = (comment["comment_type"] if "comment_type" in comment.keys() else None) or "comment"
                if comm_type != "comment" and user_role != "admin":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Удаление доступно только для обычных комментариев"
                    })
                    return

                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cur.execute("UPDATE article_comments SET status = 'deleted', is_solution = 0, updated_at = ? WHERE id = ?", (now_iso, comm_id))

            self.send_json_response(200, {
                "success": True,
                "commentId": comm_id
            })
        finally:
            conn.close()

    def handle_comment_solution_toggle(self, art_id: str, comm_id: str):
        """
        POST /api/articles/<art_id>/comments/<comm_id>/solution or POST /api/comments/<comm_id>/solution
        Allows the question author to mark or unmark an answer as the accepted solution.
        Requires authentication. Enforces 403 if user is not author of the question (admin bypass removed).
        """
        payload = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
        if payload is None:
            return

        user = self.get_current_user()
        if not user:
            self.send_json_response(401, {
                "success": False,
                "error": "Для отметки решения необходимо авторизоваться",
                "requireAuth": True
            })
            return

        if not comm_id:
            comm_id = payload.get("commentId") or payload.get("comment_id") or ""

        if not comm_id:
            self.send_json_response(400, {
                "success": False,
                "error": "Не указан идентификатор комментария"
            })
            return

        conn = self.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM article_comments WHERE id = ?", (comm_id,))
                comment = cur.fetchone()
                if not comment:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Ответ не найден"
                    })
                    return

                actual_art_id = comment["article_id"]
                cur.execute("SELECT * FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (actual_art_id, actual_art_id))
                art_row = cur.fetchone()
                if not art_row:
                    self.send_json_response(404, {
                        "success": False,
                        "error": "Вопрос не найден"
                    })
                    return

                if art_id:
                    cur.execute("SELECT id FROM moderation_submissions WHERE id = ? OR draft_id = ? LIMIT 1", (art_id, art_id))
                    url_art_row = cur.fetchone()
                    canonical_url_id = url_art_row["id"] if url_art_row else art_id
                    if canonical_url_id != actual_art_id:
                        self.send_json_response(400, {
                            "success": False,
                            "error": "Идентификатор публикации не совпадает с ответом"
                        })
                        return

                material_type = "article"
                try:
                    art_settings = json.loads(art_row["publication_settings"]) if art_row["publication_settings"] else {}
                    material_type = (art_settings.get("materialType") or art_settings.get("type") or "article").strip().lower()
                except Exception:
                    pass

                if material_type != "question":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Статус решения может быть установлен только для вопросов (materialType = 'question')."
                    })
                    return

                is_author = (user.get("id") == art_row["author_id"])
                if not is_author:
                    self.send_json_response(403, {
                        "success": False,
                        "error": "Только автор вопроса может отмечать решение"
                    })
                    return

                comm_type = (comment["comment_type"] if "comment_type" in comment.keys() else "").strip().lower()
                comm_status = (comment["status"] if "status" in comment.keys() else "").strip().lower()
                if comm_type != "answer" or comm_status != "published":
                    self.send_json_response(400, {
                        "success": False,
                        "error": "Статус решения может быть установлен только ответу (comment_type = 'answer')."
                    })
                    return

                is_sol_val = payload.get("isSolution") if "isSolution" in payload else payload.get("is_solution")
                current_is_sol = int(comment["is_solution"] or 0)
                if is_sol_val is not None:
                    target_is_sol = bool(is_sol_val)
                else:
                    target_is_sol = (current_is_sol == 0)

                if target_is_sol:
                    if current_is_sol != 1:
                        cur.execute("UPDATE article_comments SET is_solution = 0 WHERE article_id = ? AND is_solution = 1", (actual_art_id,))
                        cur.execute("UPDATE article_comments SET is_solution = 1 WHERE id = ?", (comm_id,))

                        ans_author_id = comment["user_id"]
                        if ans_author_id and ans_author_id != user.get("id"):
                            notif_id = f"notif_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
                            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            art_title = art_row["title"] or "Вопрос"
                            cur.execute("""
                                INSERT INTO user_notifications (
                                    id, user_id, actor_id, actor_name, article_id, comment_id, type, title, message, is_read, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, 'solution_accepted', ?, ?, 0, ?)
                            """, (
                                notif_id,
                                ans_author_id,
                                user.get("id"),
                                user.get("name") or "Автор вопроса",
                                actual_art_id,
                                comm_id,
                                "Ваш ответ отмечен как решение",
                                f"Автор вопроса «{art_title[:60]}» отметил ваш ответ как решение",
                                now_iso
                            ))
                else:
                    if current_is_sol == 1:
                        cur.execute("UPDATE article_comments SET is_solution = 0 WHERE id = ?", (comm_id,))

            self.send_json_response(200, {
                "success": True,
                "isSolution": target_is_sol,
                "is_solution": target_is_sol,
                "commentId": comm_id,
                "articleId": actual_art_id
            })
        finally:
            conn.close()

"""HTTP method dispatch: maps request paths to the handler methods of each area."""
import urllib.parse

from backend.config import MAX_JSON_BODY_BYTES


class RoutingHandlers:
    def do_GET(self):
        """Handle GET requests for static files and REST API."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            self.send_json_response(200, {
                "status": "ok",
                "server": "Antigravity Moderation Server"
            })
        elif path == "/api/auth/status":
            user = self.get_current_user()
            if user:
                self.send_json_response(200, {"success": True, "authenticated": True, "user": user})
            else:
                self.send_json_response(200, {"success": True, "authenticated": False, "user": None})
        elif path == "/api/user/feed-settings":
            self.handle_get_feed_settings()
        elif path == "/api/user/settings":
            self.handle_get_user_settings()
        elif path == "/api/exceptions":
            self.handle_get_exceptions()
        elif path == "/api/subscriptions":
            self.handle_get_subscriptions()
        elif path == "/api/subscriptions/entities":
            self.handle_get_subscription_entities(parsed)
        elif path == "/api/moderation/status":
            self.handle_moderation_status(parsed)
        elif path == "/api/moderation/list":
            self.handle_moderation_list()
        elif path == "/api/moderation/my":
            self.handle_my_submissions(parsed)
        elif path.startswith("/api/moderation/my/"):
            self.handle_my_submission(path[len("/api/moderation/my/"):].strip("/"))
        elif path == "/api/admin/moderation/queue":
            self.handle_admin_queue(parsed)
        elif path == "/api/admin/moderation/log":
            self.handle_admin_log(parsed)
        elif path.startswith("/api/admin/moderation/submissions/"):
            self.handle_admin_submission(path[len("/api/admin/moderation/submissions/"):].strip("/"))
        elif path == "/api/admin/users":
            self.handle_admin_users(parsed)
        elif (path.startswith("/api/articles/") or path.startswith("/api/questions/")) and path.endswith("/comments"):
            prefix = "/api/articles/" if path.startswith("/api/articles/") else "/api/questions/"
            art_id = path[len(prefix): -len("/comments")].strip("/")
            self.handle_get_article_comments(art_id)
        elif path.rstrip("/") == "/api/comments/subscriptions":
            self.handle_get_comment_subscriptions()
        elif path.rstrip("/") == "/api/comments/saved":
            self.handle_get_saved_comments()
        elif path.rstrip("/") in ("/api/saved/counts", "/api/user/saved-stats"):
            self.handle_get_saved_counts()
        elif path.rstrip("/") == "/api/saved":
            self.handle_get_saved(parsed)
        elif path == "/api/comments":
            query = urllib.parse.parse_qs(parsed.query)
            art_id = (query.get("articleId", [""])[0] or query.get("article_id", [""])[0] or query.get("id", [""])[0]).strip()
            self.handle_get_article_comments(art_id)
        elif path == "/api/questions/unanswered":
            self.handle_get_unanswered_questions()
        elif path in ("/api/articles", "/api/questions") or path.startswith("/api/articles/") or path.startswith("/api/questions/"):
            self.handle_articles_api(parsed)
        elif path.startswith("/media/"):
            self.handle_serve_media(parsed)
        elif path == "/api/clubs" or path.startswith("/api/clubs/"):
            if path == "/api/clubs":
                self.handle_get_clubs(parsed)
            else:
                club_id = path[len("/api/clubs/"):].strip("/")
                self.handle_get_club_detail(club_id)
        elif path == "/api/companies" or path.startswith("/api/companies/"):
            if path == "/api/companies":
                self.handle_get_companies(parsed)
            else:
                company_id = path[len("/api/companies/"):].strip("/")
                self.handle_get_company_detail(company_id)
        elif path == "/api/directions":
            self.handle_get_directions(parsed)
        elif path == "/api/notifications":
            self.handle_get_notifications()
        elif path.startswith("/api/users/"):
            rest = path[len("/api/users/"):].strip("/")
            if rest.endswith("/activity"):
                user_id = rest[:-len("/activity")].strip("/")
                self.handle_get_user_activity(user_id, parsed)
            elif rest.endswith("/publications"):
                user_id = rest[:-len("/publications")].strip("/")
                self.handle_get_user_publications(user_id, parsed)
            elif rest.endswith("/questions"):
                user_id = rest[:-len("/questions")].strip("/")
                self.handle_get_user_questions(user_id, parsed)
            elif rest.endswith("/answers"):
                user_id = rest[:-len("/answers")].strip("/")
                self.handle_get_user_answers(user_id, parsed)
            elif rest.endswith("/comments"):
                user_id = rest[:-len("/comments")].strip("/")
                self.handle_get_user_comments(user_id, parsed)
            elif rest.endswith("/subscribers"):
                user_id = rest[:-len("/subscribers")].strip("/")
                self.handle_get_user_subscribers(user_id, parsed)
            elif rest.endswith("/subscriptions"):
                user_id = rest[:-len("/subscriptions")].strip("/")
                self.handle_get_user_profile_subscriptions(user_id, parsed)
            else:
                user_id = rest
                if user_id.endswith("/profile"):
                    user_id = user_id[:-len("/profile")].strip("/")
                self.handle_get_user_profile(user_id)
        elif path == "/api/user/profile":
            self.handle_get_current_user_profile(parsed)
        elif path == "/api/user/pinned":
            self.handle_get_user_pinned()
        elif path == "/api/drafts":
            self.handle_get_drafts(parsed)
        elif path.startswith("/api/drafts/"):
            self.handle_get_draft(path)
        elif path.startswith("/user/"):
            uid = path[len("/user/"):].strip("/")
            if uid:
                self.send_response(302)
                self.send_header("Location", f"/profile.html?id={urllib.parse.quote(uid)}")
                self.end_headers()
                return
        elif path in ("/mobile", "/emulator", "/mobile/", "/emulator/"):
            self.send_response(302)
            self.send_header("Location", "/mobile.html")
            self.end_headers()
            return
        elif path.startswith("/api/"):
            self.send_json_response(404, {
                "success": False,
                "error": f"API endpoint not found: {path}"
            })
        else:
            # Delegate to SimpleHTTPRequestHandler for static files
            super().do_GET()

    def do_HEAD(self):
        """Handle HEAD requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/user/"):
            uid = path[len("/user/"):].strip("/")
            if uid:
                self.send_response(302)
                self.send_header("Location", f"/profile.html?id={urllib.parse.quote(uid)}")
                self.end_headers()
                return
        if path in ("/mobile", "/emulator", "/mobile/", "/emulator/"):
            self.send_response(302)
            self.send_header("Location", "/mobile.html")
            self.end_headers()
            return
        super().do_HEAD()

    def do_POST(self):
        """Handle POST requests for REST API."""
        if not self.verify_csrf_token():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/auth/login":
            self.handle_auth_login()
        elif path == "/api/auth/logout":
            self.handle_auth_logout()
        elif path == "/api/auth/register":
            self.handle_auth_register()
        elif path == "/api/auth/verify-email":
            self.handle_auth_verify_email()
        elif path == "/api/auth/resend-code":
            self.handle_auth_resend_code()
        elif path == "/api/auth/change-password":
            self.handle_auth_change_password()
        elif path == "/api/auth/change-email":
            self.handle_auth_change_email()
        elif path == "/api/auth/verify-change-email":
            self.handle_auth_verify_change_email()
        elif path == "/api/auth/forgot-password":
            self.handle_auth_forgot_password()
        elif path == "/api/auth/reset-password":
            self.handle_auth_reset_password()
        elif path == "/api/auth/logout-all":
            self.handle_auth_logout_all()
        elif path == "/api/user/feed-settings":
            self.handle_post_feed_settings()
        elif path == "/api/clubs":
            self.handle_post_club()
        elif path == "/api/companies":
            self.handle_post_company()
        elif path == "/api/likes/toggle":
            p = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
            if p is None:
                return
            art_id = p.get("articleId") or p.get("article_id") or ""
            self.handle_article_like_toggle(art_id, _body_already_read=True)
        elif path.startswith("/api/articles/") and path.endswith("/like"):
            art_id = path[len("/api/articles/"): -len("/like")].strip("/")
            self.handle_article_like_toggle(art_id, _body_already_read=False)
        elif path in ("/api/saves/toggle", "/api/bookmarks/toggle"):
            p = self.read_json_body(MAX_JSON_BODY_BYTES, allow_empty=True, default_empty={})
            if p is None:
                return
            art_id = p.get("articleId") or p.get("article_id") or ""
            self.handle_article_save_toggle(art_id, action="toggle", _body_already_read=True)
        elif (path.startswith("/api/articles/") or path.startswith("/api/questions/")) and path.endswith("/save"):
            prefix = "/api/articles/" if path.startswith("/api/articles/") else "/api/questions/"
            art_id = path[len(prefix): -len("/save")].strip("/")
            self.handle_article_save_toggle(art_id, action="save", _body_already_read=False)
        elif (path.startswith("/api/articles/") or path.startswith("/api/questions/")) and path.endswith("/unsave"):
            prefix = "/api/articles/" if path.startswith("/api/articles/") else "/api/questions/"
            art_id = path[len(prefix): -len("/unsave")].strip("/")
            self.handle_article_save_toggle(art_id, action="unsave", _body_already_read=False)
        elif (path.startswith("/api/articles/") or path.startswith("/api/questions/")) and path.endswith("/bookmark"):
            prefix = "/api/articles/" if path.startswith("/api/articles/") else "/api/questions/"
            art_id = path[len(prefix): -len("/bookmark")].strip("/")
            self.handle_article_save_toggle(art_id, action="toggle", _body_already_read=False)
        elif path in ("/api/articles/sync-saves", "/api/saves/sync"):
            self.handle_sync_saves()
        elif path.startswith("/api/articles/") and "/comments/" in path and path.endswith("/solution"):
            parts = path.strip("/").split("/")
            art_id = parts[2] if len(parts) >= 6 else ""
            comm_id = parts[4] if len(parts) >= 6 else ""
            self.handle_comment_solution_toggle(art_id, comm_id)
        elif path.startswith("/api/articles/") and path.endswith("/solution"):
            art_id = path[len("/api/articles/"): -len("/solution")].strip("/")
            self.handle_comment_solution_toggle(art_id, "")
        elif path.startswith("/api/comments/") and path.endswith("/solution"):
            parts = path.strip("/").split("/")
            comm_id = parts[2] if len(parts) >= 4 else ""
            self.handle_comment_solution_toggle("", comm_id)
        elif path.startswith("/api/articles/") and "/comments/" in path and path.endswith("/vote"):
            parts = path.strip("/").split("/")
            comm_id = parts[4] if len(parts) >= 6 else ""
            self.handle_comment_vote(comm_id)
        elif path.startswith("/api/comments/") and path.endswith("/vote"):
            comm_id = path[len("/api/comments/"): -len("/vote")].strip("/")
            self.handle_comment_vote(comm_id)
        elif path.startswith("/api/articles/") and "/comments/" in path and path.rstrip("/").endswith("/report"):
            parts = path.strip("/").split("/")
            comm_id = parts[4] if len(parts) >= 6 else ""
            self.handle_comment_report(comm_id)
        elif path.rstrip("/").startswith("/api/comments/") and path.rstrip("/").endswith("/report"):
            comm_id = path.rstrip("/")[len("/api/comments/"): -len("/report")].strip("/")
            self.handle_comment_report(comm_id)
        elif path.startswith("/api/articles/") and "/comments/" in path and path.rstrip("/").endswith("/subscribe"):
            parts = path.strip("/").split("/")
            comm_id = parts[4] if len(parts) >= 6 else ""
            self.handle_comment_subscribe_toggle(comm_id)
        elif path.rstrip("/").startswith("/api/comments/") and path.rstrip("/").endswith("/subscribe"):
            comm_id = path.rstrip("/")[len("/api/comments/"): -len("/subscribe")].strip("/")
            self.handle_comment_subscribe_toggle(comm_id)
        elif path.rstrip("/").startswith("/api/comments/") and (path.rstrip("/").endswith("/save") or path.rstrip("/").endswith("/bookmark") or path.rstrip("/").endswith("/unsave")):
            action = "unsave" if path.rstrip("/").endswith("/unsave") else "toggle"
            suffix = "/unsave" if action == "unsave" else ("/bookmark" if path.rstrip("/").endswith("/bookmark") else "/save")
            comm_id = path.rstrip("/")[len("/api/comments/"): -len(suffix)].strip("/")
            self.handle_comment_save_toggle(comm_id, action=action)
        elif path.startswith("/api/articles/") and "/comments/" in path and (path.rstrip("/").endswith("/save") or path.rstrip("/").endswith("/bookmark") or path.rstrip("/").endswith("/unsave")):
            parts = path.strip("/").split("/")
            comm_id = parts[4] if len(parts) >= 6 else ""
            action = "unsave" if path.rstrip("/").endswith("/unsave") else "toggle"
            self.handle_comment_save_toggle(comm_id, action=action)
        elif path.rstrip("/") in ("/api/comments/save", "/api/comments/toggle-save"):
            self.handle_comment_save_toggle("", action="toggle")
        elif path.rstrip("/") in ("/api/comments/sync-saves", "/api/comments/sync"):
            self.handle_comment_saves_sync()
        elif (path.startswith("/api/articles/") or path.startswith("/api/questions/")) and not "/comments/" in path and path.rstrip("/").endswith("/report"):
            prefix = "/api/articles/" if path.startswith("/api/articles/") else "/api/questions/"
            art_id = path.rstrip("/")[len(prefix): -len("/report")].strip("/")
            self.handle_article_report(art_id)
        elif (path.startswith("/api/articles/") or path.startswith("/api/questions/")) and path.endswith("/vote"):
            prefix = "/api/articles/" if path.startswith("/api/articles/") else "/api/questions/"
            art_id = path[len(prefix): -len("/vote")].strip("/")
            self.handle_article_vote(art_id)
        elif (path.startswith("/api/articles/") or path.startswith("/api/questions/")) and path.endswith("/comments"):
            prefix = "/api/articles/" if path.startswith("/api/articles/") else "/api/questions/"
            art_id = path[len(prefix): -len("/comments")].strip("/")
            self.handle_post_article_comment(art_id)
        elif path == "/api/comments":
            self.handle_post_article_comment("")
        elif path == "/api/notifications/read":
            self.handle_post_notifications_read()
        elif path == "/api/user/profile":
            self.handle_post_user_profile()
        elif path == "/api/user/pinned":
            self.handle_post_user_pinned()
        elif path == "/api/exceptions/toggle":
            self.handle_exceptions_toggle()
        elif path == "/api/subscriptions/toggle":
            self.handle_subscriptions_toggle()
        elif path == "/api/moderation/submit":
            self.handle_moderation_submit()
        elif path.startswith("/api/admin/moderation/submissions/") and path.count("/") == 6:
            # /api/admin/moderation/submissions/<id>/<action>
            submission_id, action = path[len("/api/admin/moderation/submissions/"):].split("/", 1)
            if action == "decision":
                self.handle_admin_decision(submission_id)
            elif action in ("claim", "release"):
                self.handle_admin_claim(submission_id, take=(action == "claim"))
            else:
                self.send_json_response(404, {"success": False, "error": f"API endpoint not found: {path}"})
        elif path.startswith("/api/admin/users/") and path.count("/") == 5:
            # /api/admin/users/<id>/<role|status>
            target_id, field = path[len("/api/admin/users/"):].split("/", 1)
            if field in ("role", "status"):
                self.handle_admin_user_update(target_id, field)
            else:
                self.send_json_response(404, {"success": False, "error": f"API endpoint not found: {path}"})
        elif path == "/api/media/upload" or path == "/api/upload/image":
            self.handle_media_upload()
        elif path == "/api/drafts":
            self.handle_post_drafts()
        elif path.startswith("/api/"):
            raw_body = self.read_request_body(MAX_JSON_BODY_BYTES)
            if raw_body is None:
                return
            self.send_json_response(404, {
                "success": False,
                "error": f"API endpoint not found: {path}"
            })
        else:
            raw_body = self.read_request_body(MAX_JSON_BODY_BYTES)
            if raw_body is None:
                return
            self.send_json_response(405, {
                "success": False,
                "error": "Method Not Allowed"
            })

    def do_PUT(self):
        """Handle PUT requests for comments update and API fallback."""
        if not self.verify_csrf_token():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/articles/") and "/comments/" in path:
            parts = path.strip("/").split("/")
            if len(parts) >= 5:
                art_id = parts[2]
                comm_id = parts[4]
                self.handle_update_article_comment(art_id, comm_id)
                return
        elif path.startswith("/api/comments/"):
            parts = path.strip("/").split("/")
            if len(parts) >= 3:
                comm_id = parts[2]
                self.handle_update_article_comment("", comm_id)
                return
        elif path.startswith("/api/drafts/"):
            self.handle_put_draft(path)
            return

        raw_body = self.read_request_body(MAX_JSON_BODY_BYTES)
        if raw_body is None:
            return
        if path.startswith("/api/"):
            self.send_json_response(405, {
                "success": False,
                "error": f"Method Not Allowed: PUT {path}"
            })
        else:
            self.send_json_response(405, {
                "success": False,
                "error": "Method Not Allowed"
            })

    def do_DELETE(self):
        """Handle DELETE requests for comments and API fallback."""
        if not self.verify_csrf_token():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/articles/") and "/comments/" in path:
            parts = path.strip("/").split("/")
            if len(parts) >= 5:
                art_id = parts[2]
                comm_id = parts[4]
                self.handle_delete_article_comment(art_id, comm_id)
                return
        elif path.startswith("/api/comments/"):
            parts = path.strip("/").split("/")
            if len(parts) >= 3:
                comm_id = parts[2]
                self.handle_delete_article_comment("", comm_id)
                return
        elif path == "/api/user/pinned":
            self.handle_delete_user_pinned()
            return
        elif path.startswith("/api/drafts/"):
            self.handle_delete_draft(path)
            return

        if path.startswith("/api/"):
            self.send_json_response(405, {
                "success": False,
                "error": f"Method Not Allowed: DELETE {path}"
            })
        else:
            self.send_json_response(405, {
                "success": False,
                "error": "Method Not Allowed"
            })

    def do_PATCH(self):
        """Handle PATCH requests for REST API."""
        if not self.verify_csrf_token():
            return
        self.send_json_response(405, {
            "success": False,
            "error": "Method Not Allowed"
        })

"""
SMTP delivery of account emails against a minimal local SMTP server.

Checks the real smtplib path: sender header, multipart text and HTML bodies,
the code reaching the recipient, and the code being masked in the outbox table.
"""
import email
import email.policy
import os
import socketserver
import sqlite3
import tempfile
import threading
import unittest
from unittest import mock

import server
from server import EmailService, init_db


class _SMTPHandler(socketserver.StreamRequestHandler):
    def reply(self, line):
        self.wfile.write((line + "\r\n").encode("ascii"))

    def handle(self):
        self.reply("220 test SMTP ready")
        while True:
            line = self.rfile.readline().decode("utf-8", "replace").strip()
            if not line:
                return
            verb = line.split(" ", 1)[0].upper()
            if verb in ("EHLO", "HELO"):
                self.reply("250 test")
            elif verb in ("MAIL", "RCPT", "RSET", "NOOP"):
                if verb == "RCPT":
                    self.server.recipients.append(line.split(":", 1)[1].strip(" <>"))
                self.reply("250 OK")
            elif verb == "DATA":
                self.reply("354 End data with <CR><LF>.<CR><LF>")
                chunks = []
                while True:
                    data_line = self.rfile.readline()
                    if data_line in (b".\r\n", b".\n", b""):
                        break
                    chunks.append(data_line[1:] if data_line.startswith(b"..") else data_line)
                self.server.messages.append(b"".join(chunks))
                self.reply("250 Queued")
            elif verb == "QUIT":
                self.reply("221 Bye")
                return
            else:
                self.reply("502 Not implemented")


class _SMTPServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _SMTPHandler)
        self.messages = []
        self.recipients = []


class TestMailDelivery(unittest.TestCase):
    def setUp(self):
        self.smtp = _SMTPServer()
        threading.Thread(target=self.smtp.serve_forever, daemon=True).start()
        self.env = mock.patch.dict(os.environ, {
            "SMTP_HOST": "127.0.0.1",
            "SMTP_PORT": str(self.smtp.server_address[1]),
            "SMTP_USE_SSL": "0",
            "SMTP_USE_TLS": "0",
            "SMTP_USER": "",
            "SMTP_PASSWORD": "",
            "SMTP_FROM_EMAIL": "noreply@example.com",
            "SMTP_FROM_NAME": "SmartContractum",
        })
        self.env.start()
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "mail.db")
        init_db(self.db_path, seed=False).close()
        self.conn = sqlite3.connect(self.db_path)
        self.service = EmailService()

    def tearDown(self):
        self.conn.close()
        self.env.stop()
        self.smtp.shutdown()
        self.smtp.server_close()

    def test_verification_email_is_delivered_over_smtp(self):
        self.assertTrue(self.service.is_configured())
        ok, err = self.service.send_verification_email(self.conn, "user@example.com", "482913", "alice")
        self.assertTrue(ok, err)
        self.assertEqual(self.smtp.recipients, ["user@example.com"])

        msg = email.message_from_bytes(self.smtp.messages[0], policy=email.policy.default)
        self.assertEqual(msg["From"], "SmartContractum <noreply@example.com>")
        self.assertIn("SmartContractum", msg["Subject"])
        self.assertTrue(msg["Message-ID"])
        self.assertIn("482913", msg.get_body(preferencelist=("plain",)).get_content())
        self.assertIn("482913", msg.get_body(preferencelist=("html",)).get_content())

        stored = self.conn.execute("SELECT body_text, status FROM email_outbox").fetchone()
        self.assertEqual(stored[1], "sent")
        self.assertNotIn("482913", stored[0], "delivered codes are not kept in clear text")

    def test_unreachable_smtp_reports_failure(self):
        self.smtp.shutdown()
        self.smtp.server_close()
        ok, err = self.service.send_email(self.conn, "user@example.com", "Subject", "Body")
        self.assertFalse(ok)
        self.assertTrue(err)
        status = self.conn.execute("SELECT status FROM email_outbox").fetchone()[0]
        self.assertEqual(status, "failed")
        # Restart a server so tearDown can stop it cleanly
        self.smtp = _SMTPServer()
        threading.Thread(target=self.smtp.serve_forever, daemon=True).start()

    def test_without_sender_the_development_outbox_is_used(self):
        with mock.patch.dict(os.environ, {"SMTP_FROM_EMAIL": "", "SMTP_USER": ""}):
            self.assertFalse(self.service.is_configured())


if __name__ == "__main__":
    unittest.main()

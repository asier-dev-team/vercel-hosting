#!/usr/bin/env python3
import json
import os
import re
import sys
from email.utils import formatdate
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, request


ROOT = Path(__file__).resolve().parent
INDEX_FILE = ROOT / "first_iteration_site" / "index.html"


def read_api_key():
    env_key = os.environ.get("RESEND_API_KEY", "").strip()
    if env_key:
        return env_key

    config_path = ROOT / "config.yaml"
    if not config_path.exists():
        return ""

    config_text = config_path.read_text(encoding="utf-8")
    resend_key_match = re.search(r"^\s*resend_key:\s*[\"']?([^\"'\n]+)[\"']?\s*$", config_text, re.MULTILINE)
    if resend_key_match:
        return resend_key_match.group(1).strip()

    legacy_match = re.search(r"^\s*api_key:\s*[\"']?([^\"'\n]+)[\"']?\s*$", config_text, re.MULTILINE)
    return legacy_match.group(1).strip() if legacy_match else ""


def get_error_message(payload, fallback):
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        error_value = payload.get("error")
        if isinstance(error_value, str) and error_value.strip():
            return error_value.strip()
        if isinstance(error_value, dict):
            nested_message = error_value.get("message")
            if isinstance(nested_message, str) and nested_message.strip():
                return nested_message.strip()
    return fallback


class LocalHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        if self.path != "/api/send-consult":
            self.send_json(404, {"error": "Not found."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0

        try:
            payload = json.loads(self.rfile.read(content_length) or b"{}")
        except json.JSONDecodeError:
            self.send_json(400, {"error": "Invalid JSON body."})
            return

        name = str(payload.get("name", "")).strip()
        email = str(payload.get("email", "")).strip()
        project = str(payload.get("project", "")).strip()
        details = str(payload.get("details", "")).strip()

        if not name or not email or not details:
            self.send_json(400, {"error": "Name, email, and project details are required."})
            return

        api_key = read_api_key()
        if not api_key:
            self.send_json(500, {"error": "Missing RESEND_API_KEY or config.yaml resend_key."})
            return

        resend_payload = {
            "from": "Website Builder Service <onboarding@resend.dev>",
            "to": ["asierdevteam@gmail.com"],
            "reply_to": email,
            "subject": f"New website consult request from {name}",
            "text": "\n".join(
                [
                    f"Name: {name}",
                    f"Email: {email}",
                    f"Project: {project or 'Not provided'}",
                    "",
                    "Project details:",
                    details,
                ]
            ),
            "html": f"""
              <div style="font-family: Arial, sans-serif; background:#f4f8fb; padding:24px;">
                <div style="max-width:640px; margin:0 auto; background:white; border-radius:16px; padding:24px; border:1px solid #dbe7f0;">
                  <h1 style="margin:0 0 16px; color:#12324a;">New Website Consult Request</h1>
                  <p style="margin:0 0 12px; color:#4b6980;">A new lead came in from your website.</p>
                  <p><strong>Name:</strong> {self.escape_html(name)}</p>
                  <p><strong>Email:</strong> {self.escape_html(email)}</p>
                  <p><strong>Project:</strong> {self.escape_html(project or 'Not provided')}</p>
                  <p><strong>Details:</strong><br>{self.escape_html(details).replace(chr(10), '<br>')}</p>
                </div>
              </div>
            """,
        }

        req = request.Request(
            "https://api.resend.com/emails",
            data=json.dumps(resend_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "vercel-hosting-consult-form/1.0",
            },
            method="POST",
        )

        try:
            with request.urlopen(req) as response:
                body = json.loads(response.read().decode("utf-8") or "{}")
                self.send_json(200, {"success": True, "id": body.get("id")})
        except error.HTTPError as exc:
            try:
                raw_body = exc.read().decode("utf-8")
                body = json.loads(raw_body or "{}")
            except json.JSONDecodeError:
                body = {}
                raw_body = raw_body if "raw_body" in locals() else ""
            print(f"Resend error {exc.code}: {raw_body or body}", file=sys.stderr)
            self.send_json(exc.code, {"error": get_error_message(body, "Failed to send consult request.")})
        except Exception:
            self.send_json(500, {"error": "Unexpected error while sending email."})

    def do_GET(self):
        if self.path in ("/", ""):
            self.path = "/first_iteration_site/index.html"
        elif self.path.startswith("/api/"):
            self.send_json(404, {"error": "Not found."})
            return
        elif not (ROOT / self.path.lstrip("/")).exists():
            self.path = "/first_iteration_site/index.html"

        return super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Date", formatdate(usegmt=True))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def escape_html(value):
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )


def main():
    port = int(os.environ.get("PORT", "8000"))
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    server = ThreadingHTTPServer(("127.0.0.1", port), LocalHandler)
    print(f"Local server running at http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

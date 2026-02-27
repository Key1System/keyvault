from http.server import BaseHTTPRequestHandler
import json
import os
import random
import string
import urllib.request
import urllib.error
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "admin123")

def supabase_request(method, table, filters=None, data=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if filters:
        url += "?" + "&".join(filters)

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            return result, None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return [], f"HTTP {e.code}: {error_body}"
    except Exception as e:
        return [], str(e)

def generate_key():
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=16))

def json_response(handler, status, data):
    body = json.dumps(data).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)

def read_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    return json.loads(handler.rfile.read(length))

def check_auth(handler):
    return handler.headers.get("x-dashboard-password", "") == DASHBOARD_PASSWORD

class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/api/keys":
            if not check_auth(self):
                return json_response(self, 401, {"detail": "Unauthorized"})
            rows, err = supabase_request("GET", "keys", filters=["order=created_at.desc"])
            if err:
                return json_response(self, 500, {"detail": "DB error", "error": err})
            return json_response(self, 200, rows)

        # DEBUG - visit this in browser to diagnose
        if path == "/api/debug":
            rows, err = supabase_request("GET", "keys", filters=["order=created_at.desc"])
            return json_response(self, 200, {
                "supabase_url": SUPABASE_URL,
                "key_prefix": SUPABASE_KEY[:25] + "..." if SUPABASE_KEY else "MISSING",
                "rows_found": len(rows),
                "error": err,
                "rows": rows
            })

        return json_response(self, 404, {"detail": "Not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        body = read_body(self)

        if path == "/api/keys":
            if not check_auth(self):
                return json_response(self, 401, {"detail": "Unauthorized"})
            data = {
                "key": generate_key(),
                "label": body.get("label", ""),
                "enabled": True,
                "hwid": None,
                "expires_at": body.get("expires_at") or None,
                "last_seen": None,
                "active_hwid": None,
            }
            rows, err = supabase_request("POST", "keys", data=data)
            if err:
                return json_response(self, 500, {"detail": "DB error", "error": err})
            return json_response(self, 200, rows[0] if rows else {})

        if path == "/api/verify":
            key_value = body.get("key", "")
            hwid = body.get("hwid")

            rows, err = supabase_request("GET", "keys", filters=[f"key=eq.{key_value}"])

            if err:
                return json_response(self, 200, {
                    "valid": False,
                    "reason": "Database error",
                    "debug_error": err,
                    "debug_url": SUPABASE_URL,
                    "debug_key_prefix": SUPABASE_KEY[:20] + "..." if SUPABASE_KEY else "MISSING"
                })

            if not rows:
                return json_response(self, 200, {
                    "valid": False,
                    "reason": "Key not found",
                    "debug_key_searched": key_value
                })

            k = rows[0]

            if not k["enabled"]:
                return json_response(self, 200, {"valid": False, "reason": "Key is disabled"})

            if k["expires_at"]:
                expires = datetime.fromisoformat(k["expires_at"].replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > expires:
                    return json_response(self, 200, {"valid": False, "reason": "Key has expired"})

            if hwid:
                if k["hwid"] and k["hwid"] != hwid:
                    return json_response(self, 200, {"valid": False, "reason": "HWID mismatch"})
                if not k["hwid"]:
                    supabase_request("PATCH", "keys", filters=[f"id=eq.{k['id']}"], data={"hwid": hwid})

            supabase_request("PATCH", "keys", filters=[f"id=eq.{k['id']}"], data={
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "active_hwid": hwid or k["hwid"]
            })

            return json_response(self, 200, {
                "valid": True,
                "label": k["label"],
                "expires_at": k["expires_at"],
                "hwid": k["hwid"] or hwid
            })

        return json_response(self, 404, {"detail": "Not found"})

    def do_PATCH(self):
        path = self.path.split("?")[0]
        body = read_body(self)

        if path.startswith("/api/keys/"):
            if not check_auth(self):
                return json_response(self, 401, {"detail": "Unauthorized"})
            key_id = path.replace("/api/keys/", "")
            update_data = {}
            if "enabled" in body:
                update_data["enabled"] = body["enabled"]
            if "expires_at" in body:
                update_data["expires_at"] = body["expires_at"] if body["expires_at"] else None
            if "label" in body:
                update_data["label"] = body["label"]
            if "hwid" in body:
                update_data["hwid"] = body["hwid"] if body["hwid"] else None

            rows, err = supabase_request("PATCH", "keys", filters=[f"id=eq.{key_id}"], data=update_data)
            return json_response(self, 200, rows[0] if rows else {})

        return json_response(self, 404, {"detail": "Not found"})

    def do_DELETE(self):
        path = self.path.split("?")[0]

        if path.startswith("/api/keys/"):
            if not check_auth(self):
                return json_response(self, 401, {"detail": "Unauthorized"})
            key_id = path.replace("/api/keys/", "")
            supabase_request("DELETE", "keys", filters=[f"id=eq.{key_id}"])
            return json_response(self, 200, {"success": True})

        return json_response(self, 404, {"detail": "Not found"})

from http.server import BaseHTTPRequestHandler
import json
import os
import random
import string
from datetime import datetime, timezone
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "admin123")

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

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
    pwd = handler.headers.get("x-dashboard-password", "")
    return pwd == DASHBOARD_PASSWORD

class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # suppress default logging

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        # GET /api/keys
        if path == "/api/keys":
            if not check_auth(self):
                return json_response(self, 401, {"detail": "Unauthorized"})
            db = get_supabase()
            res = db.table("keys").select("*").order("created_at", desc=True).execute()
            return json_response(self, 200, res.data)

        return json_response(self, 404, {"detail": "Not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        body = read_body(self)

        # POST /api/keys — create key
        if path == "/api/keys":
            if not check_auth(self):
                return json_response(self, 401, {"detail": "Unauthorized"})
            db = get_supabase()
            data = {
                "key": generate_key(),
                "label": body.get("label", ""),
                "enabled": True,
                "hwid": None,
                "expires_at": body.get("expires_at") or None,
                "last_seen": None,
                "active_hwid": None,
            }
            res = db.table("keys").insert(data).execute()
            return json_response(self, 200, res.data[0])

        # POST /api/verify — verify key (public)
        if path == "/api/verify":
            key_value = body.get("key", "")
            hwid = body.get("hwid")
            db = get_supabase()
            res = db.table("keys").select("*").eq("key", key_value).execute()
            if not res.data:
                return json_response(self, 200, {"valid": False, "reason": "Key not found"})

            k = res.data[0]

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
                    db.table("keys").update({"hwid": hwid}).eq("id", k["id"]).execute()

            db.table("keys").update({
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "active_hwid": hwid or k["hwid"]
            }).eq("id", k["id"]).execute()

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

        # PATCH /api/keys/<id>
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

            db = get_supabase()
            res = db.table("keys").update(update_data).eq("id", key_id).execute()
            if not res.data:
                return json_response(self, 404, {"detail": "Key not found"})
            return json_response(self, 200, res.data[0])

        return json_response(self, 404, {"detail": "Not found"})

    def do_DELETE(self):
        path = self.path.split("?")[0]

        # DELETE /api/keys/<id>
        if path.startswith("/api/keys/"):
            if not check_auth(self):
                return json_response(self, 401, {"detail": "Unauthorized"})
            key_id = path.replace("/api/keys/", "")
            db = get_supabase()
            db.table("keys").delete().eq("id", key_id).execute()
            return json_response(self, 200, {"success": True})

        return json_response(self, 404, {"detail": "Not found"})

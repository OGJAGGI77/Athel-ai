import json
import os
import socket
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler

URL = "https://api.you.com/v1/answer"


class handler(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length", 0))
            query = json.loads(self.rfile.read(size) or b"{}").get("query", "")
            query = str(query).strip()
        except Exception:
            return self._send(400, {"error": "The request was not valid."})

        if not query:
            return self._send(400, {"error": "Type a question first."})
        if len(query) > 1000:
            return self._send(400, {"error": "Keep the question under 1000 characters."})

        key = os.environ.get("YDC_API_KEY")
        if not key:
            return self._send(500, {"error": "YDC_API_KEY is not set in Vercel settings."})

        header = os.environ.get("YDC_AUTH_HEADER", "X-API-Key")
        prefix = os.environ.get("YDC_AUTH_PREFIX", "")

        req = urllib.request.Request(
            URL,
            data=json.dumps({"query": query}).encode(),
            headers={header: prefix + key, "Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=25) as res:
                data = json.loads(res.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                msg = "You.com rejected the API key. Check the key and header name in Vercel settings."
            elif e.code == 429:
                msg = "Too many requests. Wait a moment and ask again."
            else:
                msg = f"You.com returned an error ({e.code})."
            return self._send(502, {"error": msg + " [" + str(e.code) + ": " + e.read().decode(errors="ignore")[:200] + "]"})
        except (socket.timeout, TimeoutError):
            return self._send(504, {"error": "You.com took too long to answer. Ask again."})
        except Exception:
            return self._send(502, {"error": "Could not reach You.com. Ask again in a moment."})

        return self._send(200, {"answer": data.get("answer", "")})

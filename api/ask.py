import json
import os
import socket
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler

URL = "https://you.com"


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
            data=json.dumps({"query": query, "stream": False}).encode(),
            headers={
                header: prefix + key.strip(),
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=25) as res:
                raw_text = res.read().decode("utf-8", errors="replace").strip()
                if not raw_text:
                    return self._send(502, {"error": f"You.com returned an empty response (Status {res.status})."})
                try:
                    data = json.loads(raw_text)
                except json.JSONDecodeError:
                    # Handle Server-Sent Events (SSE) if You.com streamed chunks anyway
                    chunks = []
                    for line in raw_text.splitlines():
                        if line.startswith("data:"):
                            part = line[5:].strip()
                            if part and part != "[DONE]":
                                try:
                                    obj = json.loads(part)
                                    chunks.append(obj.get("answer") or obj.get("text") or obj.get("delta", ""))
                                except Exception:
                                    pass
                    if chunks:
                        return self._send(200, {"answer": "".join(chunks)})
                    return self._send(502, {"error": f"Unexpected response from You.com: {raw_text[:200]}"})
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")[:150]
            if e.code in (401, 403):
                msg = f"You.com rejected the API key ({e.code}): {err_body}"
            elif e.code == 429:
                msg = "Too many requests. Wait a moment and ask again."
            else:
                msg = f"You.com returned an error ({e.code}): {err_body}"
            return self._send(502, {"error": msg})
        except (socket.timeout, TimeoutError):
            return self._send(504, {"error": "You.com took too long to answer. Ask again."})
        except Exception as err:
            return self._send(502, {"error": f"Connection error: {type(err).__name__} - {str(err)}"})

        answer = data.get("answer") or data.get("output") or data.get("text") or ""
        if not answer:
            return self._send(502, {"error": f"No answer field found in JSON: {str(data)[:200]}"})

        return self._send(200, {"answer": answer})

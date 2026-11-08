from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import secrets
import threading
from urllib.parse import urlsplit

import requests


def valid_audio_url(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme == "https" and not parsed.username and not parsed.password and parsed.port in {None, 443} and bool(parsed.hostname) and parsed.hostname.endswith(".googlevideo.com")


class AudioProxy:
    """Loopback-only media transport for Qt's native player (not a browser-facing API).

    No arbitrary URL endpoint, directory service or persisted signed URL. Requests/redirects are
    restricted to resolver-issued Google audio; a per-session random capability guards the socket.
    Range/HEAD support permits seeking. Neither cookies nor authorization headers are forwarded.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.streams: dict[str, tuple[str, dict]] = {}
        owner = self
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *args):
                pass
            def do_HEAD(self):
                self.serve(head=True)
            def do_GET(self):
                self.serve(head=False)
            def serve(self, head):
                with owner.lock:
                    stream = owner.streams.get(self.path)
                if stream is None:
                    self.send_error(404)
                    return
                url, supplied = stream
                headers = {key: value for key, value in supplied.items() if key.casefold() in {"user-agent", "referer", "origin", "accept"}}
                if self.headers.get("Range"):
                    headers["Range"] = self.headers["Range"]
                response = None
                try:
                    with requests.Session() as session:
                        # Anonymous audio only; no environment-supplied authentication/netrc.
                        session.trust_env = False
                        for _ in range(5):
                            if not valid_audio_url(url):
                                raise ValueError("Not an authorized audio origin")
                            response = session.request("HEAD" if head else "GET", url, headers=headers, stream=True, timeout=(10, 30), allow_redirects=False)
                            if response.status_code not in {301, 302, 303, 307, 308}:
                                break
                            url = response.headers.get("Location", "")
                            response.close()
                        if response.status_code not in {200, 206, 416}:
                            self.send_error(502, "Audio provider rejected this stream")
                            return
                        self.send_response(response.status_code)
                        for key in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                            if key in response.headers:
                                self.send_header(key, response.headers[key])
                        self.send_header("Connection", "close")
                        self.end_headers()
                        if not head:
                            for chunk in response.iter_content(64 * 1024):
                                if chunk:
                                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception:
                    self.close_connection = True
                finally:
                    if response is not None:
                        response.close()
                    self.close_connection = True
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def register(self, url: str, headers: dict) -> str:
        if not valid_audio_url(url):
            raise ValueError("Only accessible provider-issued HTTPS audio is accepted")
        token = "/" + secrets.token_urlsafe(32)
        with self.lock:
            self.streams.clear()
            self.streams[token] = (url, headers)
        return f"http://127.0.0.1:{self.server.server_port}{token}"

    def close(self):
        with self.lock:
            self.streams.clear()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

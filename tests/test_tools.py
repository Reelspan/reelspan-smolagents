"""Runs the tools against a local stand-in for the API (no network)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from reelspan import Reelspan

from reelspan_smolagents import ReelspanProfilesTool, ReelspanTextTool, ReelspanVideoTool, reelspan_tools

SEEN: list = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def _reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _record(self):
        n = int(self.headers.get("Content-Length") or 0)
        SEEN.append({"method": self.command, "path": self.path, "headers": dict(self.headers), "body": self.rfile.read(n)})

    def do_GET(self):  # noqa: N802
        self._record()
        if self.headers.get("Authorization") != "Bearer rs_test":
            return self._reply(401, {"message": "Invalid API key", "error_code": "UNAUTHORIZED"})
        if self.path.startswith("/v1/profiles"):
            return self._reply(200, {"profiles": [{"username": "acme", "display_name": "Acme", "social_accounts": {"x": {"h": 1}, "tiktok": ""}}, {"username": "other", "social_accounts": {}}]})
        if self.path.startswith("/v1/posts/status"):
            return self._reply(200, {"status": "completed", "results": [{"platform": "x", "success": True, "url": "https://x.com/1", "raw": {"big": 1}}]})
        self._reply(404, {"message": "Not found", "error_code": "NOT_FOUND"})

    def do_POST(self):  # noqa: N802
        self._record()
        if self.path == "/v1/posts/text":
            return self._reply(202, {"success": True, "request_id": "req_1"})
        if self.path == "/v1/posts/video":
            return self._reply(202, {"success": True, "job_id": "job_1"})
        self._reply(404, {"message": "Not found"})


@pytest.fixture(scope="module")
def base():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def client(base):
    return Reelspan(api_key="rs_test", base_url=base)


def test_text_tool_posts_and_waits(client):
    out = ReelspanTextTool(client=client)(text="Hello", platforms=["x"], profile="acme")
    assert out == {"request_id": "req_1", "status": "completed", "results": [{"platform": "x", "success": True, "url": "https://x.com/1"}]}
    body = json.loads(next(s for s in SEEN if s["path"] == "/v1/posts/text")["body"])
    assert body["user"] == "acme" and body["platform"] == ["x"] and body["title"] == "Hello"


def test_pinned_profile_and_comma_platforms(client):
    out = ReelspanVideoTool(client=client, profile="acme")(video="https://cdn.example.com/a.mp4", platforms="tiktok, youtube", profile="other", scheduled_date="2026-12-01T09:00:00Z")
    assert out["job_id"] == "job_1"
    body = SEEN[-1]["body"].decode("latin1")
    assert 'name="user"\r\n\r\nacme' in body
    assert body.count('name="platform[]"') == 2
    assert ReelspanProfilesTool(client=client, profile="acme")() == [{"username": "acme", "name": "Acme", "networks": ["x"]}]


def test_allowed_networks_and_api_errors(client, base):
    with pytest.raises(ValueError, match="not allowed: x"):
        ReelspanTextTool(client=client, platforms=["linkedin"])(text="hi", platforms=["x"], profile="acme")
    err = ReelspanProfilesTool(client=Reelspan(api_key="nope", base_url=base))()
    assert err["error"] is True and err["status"] == 401 and err["code"] == "UNAUTHORIZED"


def test_tool_set_and_schema(client):
    tools = reelspan_tools(client=client)
    assert len(tools) == 8
    assert {t.name for t in reelspan_tools(client=client, read_only=True)}.isdisjoint({"reelspan_text", "reelspan_video", "reelspan_photos"})
    for t in tools:
        t.validate_arguments()
        assert t.output_type == "object"

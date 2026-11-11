"""Hugging Face smolagents tools for Reelspan: let an agent publish to every major social network.

>>> from smolagents import CodeAgent, InferenceClientModel
>>> from reelspan_smolagents import reelspan_tools
>>> agent = CodeAgent(tools=reelspan_tools(profile="acme"), model=InferenceClientModel())
"""

from __future__ import annotations

import contextlib
import json
import os
from typing import Any, Dict, Iterator, List, Optional, Sequence

from reelspan import Reelspan, ReelspanError
from smolagents import Tool

__version__ = "0.1.0"

PLATFORMS = (
    "tiktok", "youtube", "instagram", "facebook", "x", "threads", "linkedin", "pinterest", "bluesky", "reddit",
    "google_business", "telegram", "discord", "slack", "mastodon", "devto", "hashnode",
    "wordpress", "sandbox",
)
MCP_URL = "https://api.reelspan.com/mcp"


def _compact(value: Any, depth: int = 0) -> Any:
    if isinstance(value, list):
        return [_compact(v, depth + 1) for v in value[:100]]
    if isinstance(value, dict):
        return {k: ("…" if depth > 6 else _compact(v, depth + 1)) for k, v in value.items() if v is not None and k not in ("raw", "usage")}
    return value


class _ReelspanTool(Tool):
    """Shared client, pinned profile, allowed networks and waiting."""

    output_type = "object"
    skip_forward_signature_validation = False

    def __init__(self, client: Optional[Reelspan] = None, profile: Optional[str] = None, platforms: Optional[Sequence[str]] = None, wait: bool = True, wait_timeout: float = 300.0):
        self.client = client
        self.profile = profile
        self.allowed = list(platforms) if platforms else list(PLATFORMS)
        self.wait = wait
        self.wait_timeout = wait_timeout
        super().__init__()

    def setup(self) -> None:
        if self.client is None:
            self.client = Reelspan()
        self.is_initialized = True

    def _c(self) -> Reelspan:
        if self.client is None:
            self.setup()
        return self.client  # type: ignore[return-value]

    def _who(self, profile: Optional[str]) -> str:
        who = self.profile or profile
        if not who:
            raise ValueError("Which profile? Call reelspan_profiles and pass its username as profile.")
        return who

    def _platforms(self, platforms: Any) -> List[str]:
        if isinstance(platforms, str):
            platforms = [p.strip() for p in platforms.split(",") if p.strip()]
        bad = [p for p in platforms or [] if p not in self.allowed]
        if not platforms or bad:
            raise ValueError(f"Choose networks from: {', '.join(self.allowed)}" + (f" (not allowed: {', '.join(bad)})" if bad else ""))
        return list(platforms)

    def _call(self, fn: Any, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        try:
            return _compact(fn(*args, **kwargs))
        except ReelspanError as e:
            return {"error": True, "status": e.status, "code": e.code, "message": str(e)}

    def _finish(self, r: Dict[str, Any]) -> Dict[str, Any]:
        if self.wait and r.get("request_id") and not r.get("job_id") and not r.get("results") and not r.get("error"):
            return {"request_id": r["request_id"], **self._call(self._c().posts.wait, r["request_id"], timeout=self.wait_timeout)}
        return r


_PROFILE = {"type": "string", "description": "The profile username (from reelspan_profiles)", "nullable": True}
_PLATFORMS = {"type": "array", "description": f"Networks to post to, e.g. ['x', 'linkedin']. Any of: {', '.join(PLATFORMS)}"}
_SCHEDULE = {"type": "string", "description": "Publish later: ISO-8601 date-time. Leave empty to post now.", "nullable": True}
_TZ = {"type": "string", "description": "IANA timezone for scheduled_date, e.g. Europe/Berlin", "nullable": True}
_SETTINGS = {"type": "object", "description": 'Network settings, e.g. {"privacy_level": "PUBLIC_TO_EVERYONE"}', "nullable": True}


class ReelspanProfilesTool(_ReelspanTool):
    name = "reelspan_profiles"
    description = "Lists Reelspan profiles (brands) and the networks each has connected. Use it first to find the profile username."
    inputs: Dict[str, Any] = {}

    def forward(self) -> Any:
        r = self._call(self._c().profiles.list)
        if r.get("error"):
            return r
        rows = [{"username": p["username"], "name": p.get("display_name"), "networks": [k for k, v in (p.get("social_accounts") or {}).items() if v]} for p in r.get("profiles", [])]
        return [p for p in rows if p["username"] == self.profile] if self.profile else rows


class ReelspanTextTool(_ReelspanTool):
    name = "reelspan_text"
    description = "Publishes (or schedules) a text post to social networks. Long text becomes a thread on X and Bluesky. Returns each network's result and link."
    inputs = {
        "text": {"type": "string", "description": "The post text"},
        "platforms": _PLATFORMS,
        "profile": _PROFILE,
        "scheduled_date": _SCHEDULE,
        "timezone": _TZ,
        "first_comment": {"type": "string", "description": "Posted as the first comment", "nullable": True},
        "settings": _SETTINGS,
    }

    def forward(self, text: str, platforms: List[str], profile: Optional[str] = None, scheduled_date: Optional[str] = None, timezone: Optional[str] = None, first_comment: Optional[str] = None, settings: Optional[dict] = None) -> Any:
        return self._finish(self._call(self._c().posts.text, self._who(profile), self._platforms(platforms), text, scheduled_date=scheduled_date, timezone=timezone, first_comment=first_comment, extra=settings, async_upload=True))


class ReelspanVideoTool(_ReelspanTool):
    name = "reelspan_video"
    description = "Publishes (or schedules) a video to social networks from a public URL (Google Drive and Dropbox links work) or a local file path."
    inputs = {
        "video": {"type": "string", "description": "Public https URL or local path of the video"},
        "platforms": _PLATFORMS,
        "caption": {"type": "string", "description": "Caption, or the YouTube title", "nullable": True},
        "profile": _PROFILE,
        "scheduled_date": _SCHEDULE,
        "timezone": _TZ,
        "settings": _SETTINGS,
    }

    def forward(self, video: str, platforms: List[str], caption: Optional[str] = None, profile: Optional[str] = None, scheduled_date: Optional[str] = None, timezone: Optional[str] = None, settings: Optional[dict] = None) -> Any:
        return self._finish(self._call(self._c().posts.video, self._who(profile), self._platforms(platforms), video, caption, scheduled_date=scheduled_date, timezone=timezone, extra=settings, async_upload=True))


class ReelspanPhotosTool(_ReelspanTool):
    name = "reelspan_photos"
    description = "Publishes (or schedules) one photo or a carousel, in order, to social networks, from public URLs or local paths."
    inputs = {
        "photos": {"type": "array", "description": "Public URLs or local paths, in order"},
        "platforms": _PLATFORMS,
        "caption": {"type": "string", "description": "Caption", "nullable": True},
        "profile": _PROFILE,
        "scheduled_date": _SCHEDULE,
        "timezone": _TZ,
        "settings": _SETTINGS,
    }

    def forward(self, photos: List[str], platforms: List[str], caption: Optional[str] = None, profile: Optional[str] = None, scheduled_date: Optional[str] = None, timezone: Optional[str] = None, settings: Optional[dict] = None) -> Any:
        return self._finish(self._call(self._c().posts.photos, self._who(profile), self._platforms(platforms), photos, caption, scheduled_date=scheduled_date, timezone=timezone, extra=settings, async_upload=True))


class ReelspanStatusTool(_ReelspanTool):
    name = "reelspan_status"
    description = "Each network's result for a post, by request_id (or job_id for a scheduled post)."
    inputs = {"request_id": {"type": "string", "description": "The request_id", "nullable": True}, "job_id": {"type": "string", "description": "A scheduled post's job_id", "nullable": True}}

    def forward(self, request_id: Optional[str] = None, job_id: Optional[str] = None) -> Any:
        return self._call(self._c().posts.status, request_id=request_id, job_id=job_id)


class ReelspanHistoryTool(_ReelspanTool):
    name = "reelspan_history"
    description = "Recent posts, one row per network, newest first."
    inputs = {"profile": _PROFILE, "platform": {"type": "string", "description": "Only this network", "nullable": True}, "limit": {"type": "integer", "description": "10, 20 or 50", "nullable": True}}

    def forward(self, profile: Optional[str] = None, platform: Optional[str] = None, limit: Optional[int] = None) -> Any:
        q = {k: v for k, v in {"profile_username": self.profile or profile, "platform": platform, "limit": limit or 20}.items() if v}
        return self._call(self._c().posts.history, **q).get("history", [])


class ReelspanAnalyticsTool(_ReelspanTool):
    name = "reelspan_analytics"
    description = "Followers, reach and engagement of a profile per network; with days, a day-by-day history."
    inputs = {"profile": _PROFILE, "days": {"type": "integer", "description": "Day-by-day history of this many days", "nullable": True}}

    def forward(self, profile: Optional[str] = None, days: Optional[int] = None) -> Any:
        who = self._who(profile)
        return self._call(self._c().analytics.history, who, days=days) if days else self._call(self._c().analytics.account, who)


class ReelspanScheduledTool(_ReelspanTool):
    name = "reelspan_scheduled"
    description = "Posts waiting for their scheduled time."
    inputs = {"profile": _PROFILE}

    def forward(self, profile: Optional[str] = None) -> Any:
        who = self.profile or profile
        return self._call(self._c().scheduled.list, **({"profile_username": who} if who else {}))


WRITE = (ReelspanTextTool, ReelspanVideoTool, ReelspanPhotosTool)
READ = (ReelspanProfilesTool, ReelspanStatusTool, ReelspanHistoryTool, ReelspanAnalyticsTool, ReelspanScheduledTool)


def reelspan_tools(client: Optional[Reelspan] = None, profile: Optional[str] = None, platforms: Optional[Sequence[str]] = None, read_only: bool = False, wait: bool = True) -> List[Tool]:
    """Every Reelspan tool, sharing one client. `profile` pins them to one profile; `read_only` drops posting."""
    client = client or Reelspan()
    classes = READ if read_only else READ + WRITE
    return [cls(client=client, profile=profile, platforms=platforms, wait=wait) for cls in classes]


@contextlib.contextmanager
def reelspan_mcp_tools(api_key: Optional[str] = None, url: str = MCP_URL) -> Iterator[List[Tool]]:
    """Every tool of Reelspan's hosted MCP server (needs `pip install "smolagents[mcp]"`).

    >>> with reelspan_mcp_tools() as tools:
    ...     agent = CodeAgent(tools=tools, model=model)
    """
    from smolagents import ToolCollection

    key = api_key or os.environ.get("REELSPAN_API_KEY")
    if not key:
        raise ValueError("Pass api_key or set REELSPAN_API_KEY")
    params = {"url": url, "transport": "streamable-http", "headers": {"Authorization": f"Bearer {key}"}}
    with ToolCollection.from_mcp(params, trust_remote_code=True) as collection:
        yield list(collection.tools)


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


__all__ = [
    "reelspan_tools",
    "reelspan_mcp_tools",
    "ReelspanProfilesTool",
    "ReelspanTextTool",
    "ReelspanVideoTool",
    "ReelspanPhotosTool",
    "ReelspanStatusTool",
    "ReelspanHistoryTool",
    "ReelspanAnalyticsTool",
    "ReelspanScheduledTool",
    "PLATFORMS",
    "__version__",
]

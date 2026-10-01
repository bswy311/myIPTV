"""历史记录：给每条流累计成功/失败次数，实现「自动剔除 + 冷却后自动复活」。"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Stream


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class History:
    """基于 JSON 的历史库，记录每条 URL 的稳定性，驱动剔除与复活。"""

    def __init__(self, path: Path, blacklist_after: int = 4, blacklist_hours: int = 72,
                 keep_days: int = 60) -> None:
        self.path = Path(path)
        self.blacklist_after = int(blacklist_after)
        self.blacklist_hours = int(blacklist_hours)
        self.keep_days = int(keep_days)
        self.entries: dict[str, dict] = {}
        self.dirty = False

    # ---------- 持久化 ----------
    def load(self) -> "History":
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.entries = data.get("streams", {}) if isinstance(data, dict) else {}
            except (json.JSONDecodeError, OSError):
                self.entries = {}
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": iso(now_utc()),
            "blacklist_after": self.blacklist_after,
            "blacklist_hours": self.blacklist_hours,
            "streams": self.entries,
        }
        # 原子写入，避免中途中断写坏文件
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    # ---------- 查询 ----------
    def get(self, url: str) -> dict:
        return self.entries.get(url) or {}

    def is_blacklisted(self, url: str, now: datetime | None = None) -> bool:
        ent = self.entries.get(url)
        if not ent:
            return False
        until = parse_iso(ent.get("blacklist_until", ""))
        if not until:
            return False
        return (now or now_utc()) < until

    def apply(self, stream: Stream) -> None:
        """把历史统计回填到 stream 上，供评分使用。"""
        ent = self.entries.get(stream.url)
        if not ent:
            return
        stream.fail_streak = int(ent.get("fail_streak", 0))
        stream.ok_count = int(ent.get("ok_count", 0))

    # ---------- 记录 ----------
    def record(self, stream: Stream, now: datetime | None = None) -> None:
        now = now or now_utc()
        ent = self.entries.setdefault(
            stream.url,
            {
                "name": stream.name,
                "ok_count": 0,
                "fail_count": 0,
                "fail_streak": 0,
                "first_seen": iso(now),
            },
        )
        ent["name"] = stream.display or stream.name or ent.get("name", "")
        ent["last_check"] = iso(now)

        if stream.ok:
            ent["ok_count"] = int(ent.get("ok_count", 0)) + 1
            ent["fail_streak"] = 0
            ent["last_ok"] = iso(now)
            ent["latency_ms"] = round(stream.latency_ms, 1)
            ent["resolution"] = stream.resolution
            ent["kind"] = stream.kind
            ent["blacklist_until"] = ""
        else:
            ent["fail_count"] = int(ent.get("fail_count", 0)) + 1
            streak = int(ent.get("fail_streak", 0)) + 1
            ent["fail_streak"] = streak
            ent["last_error"] = stream.error
            if streak >= self.blacklist_after:
                ent["blacklist_until"] = iso(now + timedelta(hours=self.blacklist_hours))

        self.dirty = True

    def prune(self, now: datetime | None = None) -> int:
        """清理长期未出现的记录。"""
        now = now or now_utc()
        cutoff = now - timedelta(days=self.keep_days)
        drop = [
            url
            for url, ent in self.entries.items()
            if (parse_iso(ent.get("last_check", "")) or now) < cutoff
        ]
        for url in drop:
            del self.entries[url]
        if drop:
            self.dirty = True
        return len(drop)

    def stats(self) -> dict:
        total = len(self.entries)
        bl = sum(1 for u in self.entries if self.is_blacklisted(u))
        alive = sum(1 for e in self.entries.values() if int(e.get("fail_streak", 0)) == 0
                    and int(e.get("ok_count", 0)) > 0)
        return {"tracked": total, "blacklisted": bl, "healthy": alive}

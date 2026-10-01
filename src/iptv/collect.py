"""采集层：拉取公开 IPTV 列表并解析成统一的 Stream 列表。"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import httpx

from .models import SourceStat, Stream

# #EXTINF:-1 tvg-id="a" tvg-name="b" group-title="c",显示名
_EXTINF_RE = re.compile(
    r"^#EXTINF:\s*(?P<dur>-?\d+(?:\.\d+)?)\s*(?P<rest>.*)$", re.IGNORECASE
)
_ATTR_RE = re.compile(
    r"([A-Za-z0-9_.\-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s,]+))"
)
_URL_LIKE = re.compile(r"^(https?|rtmp|rtsp|rtp|udp|mms|file)://", re.IGNORECASE)


def _split_title(rest: str) -> tuple[str, str]:
    """把 `attrs,title` 拆开：取最后一个不在引号内的逗号。"""
    in_quote: str | None = None
    last = -1
    for i, ch in enumerate(rest):
        if in_quote:
            if ch == in_quote:
                in_quote = None
        elif ch in "\"'":
            in_quote = ch
        elif ch == ",":
            last = i
    if last == -1:
        return rest, ""
    return rest[:last], rest[last + 1 :].strip()


def _parse_attrs(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in _ATTR_RE.finditer(raw):
        key = m.group(1).lower()
        val = m.group(2) or m.group(3) or m.group(4) or ""
        out[key] = val.strip()
    return out


def parse_m3u(text: str, source_name: str, base_dir: Path | None = None) -> list[Stream]:
    streams: list[Stream] = []
    ext: dict[str, str] = {}
    title = ""
    opts: dict[str, str] = {}
    group_tag = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.upper().startswith("#EXTM3U"):
            continue

        if line.upper().startswith("#EXTINF"):
            m = _EXTINF_RE.match(line)
            rest = m.group("rest") if m else line.split(":", 1)[-1]
            attrs_part, title = _split_title(rest)
            ext = _parse_attrs(attrs_part)
            continue

        if line.upper().startswith("#EXTGRP:"):
            group_tag = line.split(":", 1)[1].strip()
            continue

        if line.upper().startswith("#EXTVLCOPT:"):
            body = line.split(":", 1)[1].strip()
            if "=" in body:
                k, v = body.split("=", 1)
                opts[k.strip().lower()] = v.strip()
            continue

        if line.startswith("#"):
            # KODIPROP / EXT-X-* 等其它指令，忽略
            continue

        # ---- 到这里是 URL 行 ----
        url = line
        if base_dir is not None and not _URL_LIKE.match(url):
            url = str(base_dir / url)

        if not _URL_LIKE.match(url):
            continue

        streams.append(
            Stream(
                url=url,
                name=title or ext.get("tvg-name", "") or "",
                source=source_name,
                tvg_id=ext.get("tvg-id", ""),
                tvg_name=ext.get("tvg-name", ""),
                tvg_logo=ext.get("tvg-logo", "") or ext.get("logo", ""),
                group=ext.get("group-title", "") or group_tag,
                referrer=opts.get("http-referrer", ""),
                user_agent=opts.get("http-user-agent", ""),
            )
        )
        ext, title, opts, group_tag = {}, "", {}, ""

    return streams


def parse_plain(text: str, source_name: str, base_dir: Path | None = None) -> list[Stream]:
    """解析 `频道名,url` 或 `url` 逐行的纯文本列表。"""
    streams: list[Stream] = []
    current_group = ""

    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line or line.startswith("//"):
            continue

        name, url = "", ""
        if "," in line:
            left, right = line.split(",", 1)
            left, right = left.strip(), right.strip()
            if right.lower().startswith("#genre#"):
                current_group = left
                continue
            if _URL_LIKE.match(right):
                name, url = left, right
            elif _URL_LIKE.match(left):
                name, url = right, left
        elif _URL_LIKE.match(line):
            url = line

        if not url:
            continue
        if base_dir is not None and not _URL_LIKE.match(url):
            url = str(base_dir / url)
        if not _URL_LIKE.match(url):
            continue

        streams.append(Stream(url=url, name=name, group=current_group, source=source_name))

    return streams


def parse_content(text: str, source_name: str, base_dir: Path | None = None) -> list[Stream]:
    head = text[:4000].upper()
    if "#EXTM3U" in head or "#EXTINF" in head:
        return parse_m3u(text, source_name, base_dir)
    return parse_plain(text, source_name, base_dir)


async def fetch_source(
    client: httpx.AsyncClient, src, timeout: float
) -> tuple[list[Stream], SourceStat]:
    name = src.get("name") or src.get("url", "")
    url = src.get("url") or ""
    stat = SourceStat(name=name, url=url)
    source_timeout = float(src.get("timeout") or timeout)
    base_dir: Path | None = None

    try:
        if url.startswith("file://"):
            path = Path(url[7:])
            base_dir = path.parent
            text = path.read_text(encoding="utf-8", errors="ignore")
        elif _URL_LIKE.match(url) and not url.lower().startswith(("http://", "https://")):
            stat.error = "非 HTTP 协议，跳过"
            return [], stat
        elif not _URL_LIKE.match(url):
            path = Path(url)
            if not path.is_absolute():
                path = Path.cwd() / path
            if not path.exists():
                stat.error = "本地文件不存在"
                return [], stat
            base_dir = path.parent
            text = path.read_text(encoding="utf-8", errors="ignore")
        else:
            resp = await client.get(url, timeout=source_timeout, follow_redirects=True)
            resp.raise_for_status()
            text = resp.text
    except Exception as exc:  # noqa: BLE001 - 单个源失败不能影响整体
        stat.error = f"{type(exc).__name__}: {exc}"[:200]
        return [], stat

    stat.fetched = len(text)
    streams = parse_content(text, name, base_dir)
    stat.parsed = len(streams)
    return streams, stat


async def collect_all(cfg, on_progress=None) -> tuple[list[Stream], list[SourceStat]]:
    """并发拉取所有启用的采集源，返回原始流列表与各源统计。"""
    sources = [s for s in (cfg.sources or []) if s.get("enabled", True)]
    if not sources:
        return [], []

    headers = {"User-Agent": cfg.network.get("user_agent") or "Mozilla/5.0"}
    timeout = float(cfg.network.get("timeout") or 10)

    streams: list[Stream] = []
    stats: list[SourceStat] = []

    async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
        tasks = [fetch_source(client, s, timeout) for s in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for src, res in zip(sources, results):
        if isinstance(res, BaseException):
            stats.append(
                SourceStat(
                    name=src.get("name", ""), url=src.get("url", ""), error=str(res)[:200]
                )
            )
            continue
        src_streams, stat = res
        stats.append(stat)
        streams.extend(src_streams)

    if on_progress:
        for st in stats:
            if st.error:
                on_progress(f"  [x] {st.name:<20} 失败: {st.error}")
            else:
                on_progress(f"  [v] {st.name:<20} {st.parsed:>5} 条")

    return streams, stats


def load_local(path: str | Path, source_name: str = "local") -> list[Stream]:
    p = Path(path)
    return parse_content(p.read_text(encoding="utf-8", errors="ignore"), source_name, p.parent)

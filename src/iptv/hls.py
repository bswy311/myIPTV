"""极简 HLS 清单解析器。

只需要支撑「探测」这一件事，所以只解析用得到的标签：
  #EXT-X-STREAM-INF / #EXT-X-MEDIA ?  -> 子清单（码率、分辨率）
  #EXTINF                             -> 分片
  #EXT-X-MAP                          -> 初始化分片（fMP4）
不引入第三方依赖，避免不同 Python 版本上的安装问题。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

_ATTR_RE = re.compile(r'([A-Za-z0-9\-]+)\s*=\s*(?:"([^"]*)"|([^,]*))')


@dataclass
class Segment:
    uri: str = ""
    duration: float = 0.0     # #EXTINF 里声明的时长（秒），算码率要用


@dataclass
class Variant:
    uri: str = ""
    bandwidth: int = 0
    resolution: str = ""


@dataclass
class Playlist:
    variants: list[Variant] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    init_segment: str = ""
    is_master: bool = False
    is_endlist: bool = False
    target_duration: float = 0.0


def parse_attributes(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in _ATTR_RE.finditer(text):
        key = m.group(1).upper()
        value = m.group(2) if m.group(2) is not None else (m.group(3) or "")
        out[key] = value.strip().strip('"')
    return out


def _to_int(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _to_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_resolution(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    m = re.match(r"^(\d+)\s*[xX*]\s*(\d+)$", value)
    return f"{m.group(1)}x{m.group(2)}" if m else ""


def parse_playlist(content: str) -> Playlist:
    """解析 m3u8 文本。行内联的 BOM / 空行 / 注释都能容忍。"""
    pl = Playlist()
    lines = [ln.strip().lstrip("\ufeff") for ln in (content or "").splitlines()]

    pending_variant: dict[str, str] | None = None
    pending_duration = 0.0
    expect_segment = False

    for line in lines:
        if not line:
            continue

        if line.startswith("#"):
            tag, _, body = line.partition(":")
            tag = tag.upper()
            body = body.strip()

            if tag == "#EXT-X-STREAM-INF":
                pl.is_master = True
                pending_variant = parse_attributes(body)
            elif tag == "#EXTINF":
                expect_segment = True
                pending_duration = _to_float(body.split(",", 1)[0])
            elif tag == "#EXT-X-MAP":
                attrs = parse_attributes(body)
                if attrs.get("URI"):
                    pl.init_segment = attrs["URI"]
            elif tag == "#EXT-X-ENDLIST":
                pl.is_endlist = True
            elif tag == "#EXT-X-TARGETDURATION":
                pl.target_duration = _to_float(body)
            continue

        # 非 # 开头 → URI 行
        if pending_variant is not None:
            pl.variants.append(
                Variant(
                    uri=line,
                    bandwidth=_to_int(
                        pending_variant.get("BANDWIDTH")
                        or pending_variant.get("AVERAGE-BANDWIDTH")
                        or "0"
                    ),
                    resolution=_normalize_resolution(pending_variant.get("RESOLUTION", "")),
                )
            )
            pending_variant = None
            expect_segment = False
            continue

        if expect_segment:
            pl.segments.append(Segment(uri=line, duration=pending_duration))
            expect_segment = False
            pending_duration = 0.0
            continue

        # 少数清单直接跟 URI（无 EXTINF），一并收集以免漏判
        if not pl.is_master:
            pl.segments.append(Segment(uri=line, duration=0.0))

    return pl


def is_hls(content: str) -> bool:
    return "#EXTM3U" in (content or "")[:2048]


def best_variant(pl: Playlist) -> Variant | None:
    if not pl.variants:
        return None
    return max(pl.variants, key=lambda v: v.bandwidth)


def absolute(base: str, uri: str) -> str:
    return urljoin(base, uri) if uri else ""

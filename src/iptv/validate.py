"""探测层：真正拉取流数据来判断直播源是否可用。

判定原则（HTTP 200 远远不够）：
  * HLS(.m3u8) —— 拉清单 → 选最高码率子清单 → 再拉第一个分片，确认真能出流
  * TS        —— 读前 64KB，校验 MPEG-TS 同步字节 0x47
  * MP4/FLV/DASH/Audio —— 校验文件头魔数
  * text/html —— 直接判死（很多失效源会返回 200 + 门户/报错页）
"""

from __future__ import annotations

import asyncio
import time
from urllib.parse import urlparse

import httpx

from . import hls
from .history import History
from .models import ProbeResult, Stream

HTML_HINTS = ("text/html", "text/xml", "application/xhtml")
HLS_HINTS = ("mpegurl", "m3u")

# 单个请求的墙钟硬上限（秒），可由 config.validate.request_hard_timeout 覆盖
DEFAULT_HARD_TIMEOUT = 15.0


def scheme_of(url: str) -> str:
    try:
        return (urlparse(url).scheme or "").lower()
    except ValueError:
        return ""


def guess_kind(url: str, content_type: str) -> str:
    ct = (content_type or "").lower().split(";")[0].strip()
    path = url.split("?", 1)[0].split("#", 1)[0].lower()

    if "mpegurl" in ct or path.endswith((".m3u8", ".m3u")):
        return "hls"
    if "mp2t" in ct or path.endswith(".ts"):
        return "ts"
    if "mp4" in ct or path.endswith((".mp4", ".m4s", ".m4v")):
        return "mp4"
    if "flv" in ct or path.endswith(".flv"):
        return "flv"
    if "dash" in ct or path.endswith(".mpd"):
        return "dash"
    if "webm" in ct or path.endswith(".webm"):
        return "webm"
    if ct.startswith("audio/") or path.endswith((".mp3", ".aac", ".ogg")):
        return "audio"
    if path.endswith(".m3u8"):
        return "hls"
    return "other"


def build_headers(stream: Stream, cfg) -> dict[str, str]:
    headers = {"User-Agent": cfg.network.get("user_agent") or "Mozilla/5.0"}
    if stream.user_agent:
        headers["User-Agent"] = stream.user_agent
    if stream.referrer:
        headers["Referer"] = stream.referrer
        try:
            parts = urlparse(stream.referrer)
            if parts.scheme and parts.netloc:
                headers["Origin"] = f"{parts.scheme}://{parts.netloc}"
        except ValueError:
            pass
    headers["Accept"] = "*/*"
    return headers


def _hard_timeout() -> float:
    """单个 HTTP 请求的墙钟硬上限。

    必须要有：光靠 httpx 的空闲超时挡不住「慢速滴流」的服务器——
    只要每 8 秒内发一点数据，连接就永远不会超时，整轮检测会被拖死。
    """
    return float(DEFAULT_HARD_TIMEOUT)


async def _read_head(
    client: httpx.AsyncClient,
    url: str,
    limit: int,
    headers: dict,
    timeout: float,
    hard: float | None = None,
) -> tuple[int, dict[str, str], bytes, str]:
    """流式 GET，最多读取 limit 字节后立即断开，避免下整部电影。

    外面再包一层 asyncio.wait_for 作为墙钟上限，双保险。
    """

    async def _do() -> tuple[int, dict[str, str], bytes, str]:
        async with client.stream(
            "GET", url, headers=headers, timeout=timeout, follow_redirects=True
        ) as resp:
            status = resp.status_code
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            final_url = str(resp.url)
            buf = bytearray()
            if status < 400:
                try:
                    async for chunk in resp.aiter_bytes(16384):
                        buf.extend(chunk)
                        if len(buf) >= limit:
                            break
                except httpx.HTTPError:
                    # 已经读到部分数据也没关系，交给后面的内容校验判断
                    pass
            return status, hdrs, bytes(buf), final_url

    budget = hard if hard else _hard_timeout()
    try:
        return await asyncio.wait_for(_do(), timeout=budget)
    except asyncio.TimeoutError as exc:
        raise httpx.ReadTimeout(f"请求超过 {budget:.0f}s 墙钟上限") from exc


def _resolve(base: str, uri: str) -> str:
    return hls.absolute(base, uri)


async def _validate_hls(
    client: httpx.AsyncClient,
    url: str,
    cfg,
    headers: dict,
    timeout: float,
    manifest_limit: int,
    seg_limit: int,
    seg_timeout: float,
    min_seg: int,
    deep: bool,
    hard: float | None = None,
) -> ProbeResult:
    status, hdrs, body, final = await _read_head(
        client, url, manifest_limit, headers, timeout, hard
    )
    if status >= 400:
        return ProbeResult(False, "hls", status, error=f"HTTP {status}")

    ctype = hdrs.get("content-type", "").lower()
    text = body.decode("utf-8", errors="ignore")

    if not hls.is_hls(text):
        if any(h in ctype for h in HTML_HINTS):
            return ProbeResult(False, "hls", status, error="返回 HTML 而非播放列表")
        return ProbeResult(False, "hls", status, error="不是有效的 HLS 清单")

    playlist = hls.parse_playlist(text)
    base = final
    resolution, bandwidth = "", 0

    # 主清单 → 沿最高码率一路下钻（最多 3 层，防循环）
    depth = 0
    while playlist.is_master and playlist.variants and depth < 3:
        best = hls.best_variant(playlist)
        if best is None:
            break
        if best.resolution:
            resolution = best.resolution
        bandwidth = best.bandwidth or bandwidth

        sub_url = hls.absolute(base, best.uri)
        if not sub_url:
            return ProbeResult(False, "hls", status, error="子清单地址为空")

        s2, _, body2, final2 = await _read_head(
            client, sub_url, manifest_limit, headers, timeout, hard
        )
        if s2 >= 400:
            return ProbeResult(False, "hls", s2, error=f"子清单 HTTP {s2}")

        base = final2
        playlist = hls.parse_playlist(body2.decode("utf-8", errors="ignore"))
        depth += 1

    if not deep:
        return ProbeResult(True, "hls", status, resolution=resolution, bandwidth=bandwidth)

    # 取第一个分片（或 fMP4 初始化分片）验证能不能真正出流
    seg_uri = playlist.segments[0] if playlist.segments else playlist.init_segment
    if not seg_uri:
        return ProbeResult(False, "hls", status, error="清单里没有可用分片")

    seg_url = hls.absolute(base, seg_uri)
    try:
        s3, _, body3, _ = await _read_head(
            client, seg_url, seg_limit, headers, seg_timeout, hard
        )
    except httpx.HTTPError as exc:
        return ProbeResult(False, "hls", status, error=f"分片请求失败: {exc}"[:120])

    if s3 >= 400:
        return ProbeResult(False, "hls", s3, error=f"分片 HTTP {s3}")
    if len(body3) < min_seg:
        return ProbeResult(False, "hls", s3, error=f"分片过小({len(body3)}B)")

    return ProbeResult(True, "hls", status, resolution=resolution, bandwidth=bandwidth)


async def probe(
    client: httpx.AsyncClient, stream: Stream, cfg, timeout: float | None = None
) -> ProbeResult:
    v = cfg.validate
    net = cfg.network
    timeout = timeout or float(net.get("timeout") or 8)
    headers = build_headers(stream, cfg)

    manifest_limit = int(v.get("manifest_max_bytes") or 524288)
    seg_limit = int(v.get("segment_bytes") or 65536)
    seg_timeout = float(v.get("segment_timeout") or timeout)
    min_seg = int(v.get("min_segment_bytes") or 1024)
    deep = bool(v.get("deep", True))
    hard = float(v.get("request_hard_timeout") or DEFAULT_HARD_TIMEOUT)
    allowed = [str(k).lower() for k in (v.get("allowed_kinds") or [])]

    t0 = time.perf_counter()
    try:
        # 先按 URL 猜类型；HLS 走深检
        kind_guess = guess_kind(stream.url, "")

        if kind_guess == "hls":
            res = await _validate_hls(
                client, stream.url, cfg, headers, timeout,
                manifest_limit, seg_limit, seg_timeout, min_seg, deep, hard,
            )
            res.latency_ms = (time.perf_counter() - t0) * 1000
            return res

        status, hdrs, body, final = await _read_head(
            client, stream.url, max(seg_limit, 188 * 8), headers, timeout, hard
        )
        latency = (time.perf_counter() - t0) * 1000
        ctype = hdrs.get("content-type", "")
        kind = guess_kind(final or stream.url, ctype)

        if status >= 400:
            return ProbeResult(False, kind, status, latency, error=f"HTTP {status}")

        # 200 但返回网页 → 典型失效源
        if any(h in ctype.lower() for h in HTML_HINTS) and b"#EXTM3U" not in body:
            return ProbeResult(False, kind, status, latency, error="返回 HTML 页面")

        # 服务端说是 m3u8，那就按 HLS 再检一次
        if kind == "hls":
            res = await _validate_hls(
                client, stream.url, cfg, headers, timeout,
                manifest_limit, seg_limit, seg_timeout, min_seg, deep, hard,
            )
            res.latency_ms = latency
            return res

        if allowed and kind not in allowed:
            return ProbeResult(False, kind, status, latency, error=f"类型不允许: {kind}")

        if kind == "ts":
            if len(body) < 188:
                return ProbeResult(False, kind, status, latency, error="数据不足 188 字节")
            if body[0] != 0x47 or (len(body) >= 377 and body[188] != 0x47):
                return ProbeResult(False, kind, status, latency, error="TS 同步字节校验失败")
        elif kind == "mp4":
            if b"ftyp" not in body[:64]:
                return ProbeResult(False, kind, status, latency, error="缺少 ftyp 文件头")
        elif kind == "flv":
            if not body.startswith(b"FLV"):
                return ProbeResult(False, kind, status, latency, error="缺少 FLV 文件头")
        elif kind == "dash":
            if b"<MPD" not in body[:4096] and b"<?xml" not in body[:64]:
                return ProbeResult(False, kind, status, latency, error="不是有效的 MPD")
        elif kind == "webm":
            if not body.startswith(b"\x1a\x45\xdf\xa3"):
                return ProbeResult(False, kind, status, latency, error="缺少 WebM 文件头")
        elif kind in ("audio", "other"):
            if len(body) < min_seg:
                return ProbeResult(False, kind, status, latency, error=f"数据过小({len(body)}B)")
        else:
            return ProbeResult(False, kind, status, latency, error=f"未知类型: {kind}")

        return ProbeResult(True, kind, status, latency)

    except httpx.TimeoutException:
        return ProbeResult(False, "other", 0, (time.perf_counter() - t0) * 1000, error="超时")
    except httpx.HTTPError as exc:
        return ProbeResult(
            False, "other", 0, (time.perf_counter() - t0) * 1000, error=f"{type(exc).__name__}"[:60]
        )
    except Exception as exc:  # noqa: BLE001 - 任何异常都视为不可用，绝不中断整体
        return ProbeResult(
            False, "other", 0, (time.perf_counter() - t0) * 1000, error=f"{type(exc).__name__}: {exc}"[:120]
        )


def compute_score(stream: Stream) -> float:
    """延迟越低、清晰度越高、历史越稳，分数越高。"""
    score = 1000.0
    score -= min(stream.latency_ms, 6000.0) * 0.08          # 最多扣 480
    score += min(stream.height, 1080) * 0.22                 # 最多加 237
    if stream.kind == "hls":
        score += 40.0                                        # HLS 兼容性最好
    if stream.bandwidth:
        score += min(stream.bandwidth / 1_000_000.0, 8.0) * 5.0
    score += min(stream.ok_count, 20) * 4.0                  # 历史稳定加分
    score -= stream.fail_streak * 120.0
    return round(score, 1)


async def probe_all(
    streams: list[Stream], cfg, history: History, on_progress=None, concurrency: int | None = None
) -> list[Stream]:
    concurrency = int(concurrency or cfg.network.get("concurrency") or 100)
    timeout = float(cfg.network.get("timeout") or 8)
    connect_timeout = float(cfg.network.get("connect_timeout") or 5)
    retries = int(cfg.network.get("retries") or 0)
    total_timeout = float(cfg.network.get("total_timeout") or 0)
    verify = bool(cfg.network.get("verify_ssl", False))
    proxy = cfg.network.get("proxy") or None

    limits = httpx.Limits(
        max_connections=concurrency, max_keepalive_connections=max(concurrency // 2, 10)
    )
    timeouts = httpx.Timeout(timeout, connect=connect_timeout)

    kwargs = dict(
        limits=limits,
        timeout=timeouts,
        follow_redirects=True,
        verify=verify,
        headers={"User-Agent": cfg.network.get("user_agent") or "Mozilla/5.0"},
        http2=False,
    )
    if proxy:
        kwargs["proxy"] = proxy

    sem = asyncio.Semaphore(concurrency)
    total = len(streams)
    done = 0

    async with httpx.AsyncClient(**kwargs) as client:

        async def _attempt(st: Stream) -> ProbeResult:
            result = await probe(client, st, cfg)
            for _ in range(retries):
                if result.ok:
                    break
                # 只对超时/连接类错误重试，HTTP 4xx 说明源本身有问题
                if result.status and 400 <= result.status < 500:
                    break
                result = await probe(client, st, cfg)
            return result

        async def worker(st: Stream) -> None:
            async with sem:
                if history.is_blacklisted(st.url):
                    st.skipped = True
                    st.error = "已拉黑（冷却中）"
                    return

                t0 = time.perf_counter()
                try:
                    # 整体墙钟上限：任何一条流都不能拖住整轮检测
                    if total_timeout > 0:
                        result = await asyncio.wait_for(
                            _attempt(st), timeout=total_timeout
                        )
                    else:
                        result = await _attempt(st)
                except asyncio.TimeoutError:
                    result = ProbeResult(
                        False,
                        "other",
                        0,
                        (time.perf_counter() - t0) * 1000,
                        error=f"整体超时(>{total_timeout:.0f}s)",
                    )
                except Exception as exc:  # noqa: BLE001 - 绝不让单条流中断整轮
                    result = ProbeResult(
                        False,
                        "other",
                        0,
                        (time.perf_counter() - t0) * 1000,
                        error=f"{type(exc).__name__}: {exc}"[:120],
                    )

                st.ok = result.ok
                st.kind = result.kind
                st.status = result.status
                st.latency_ms = round(result.latency_ms, 1)
                st.resolution = result.resolution
                st.height = result.height
                st.bandwidth = result.bandwidth
                st.error = result.error
                st.score = compute_score(st) if result.ok else 0.0
                history.record(st)

        tasks = [asyncio.create_task(worker(s)) for s in streams]
        for fut in asyncio.as_completed(tasks):
            await fut
            done += 1
            if on_progress and (done % 25 == 0 or done == total):
                alive = sum(1 for s in streams if s.ok)
                on_progress(done, total, alive)

    return streams

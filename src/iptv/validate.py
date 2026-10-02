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

from . import hls, tsinfo
from .history import History
from .models import ProbeResult, Stream

HTML_HINTS = ("text/html", "text/xml", "application/xhtml")
HLS_HINTS = ("mpegurl", "m3u")

# 纯音频容器特征。
# 为什么要单独判断：广播电台也大量用 HLS 分发（如 cnr.cn 的卫星播流），
# 对播放器来说能正常拉流、速度还很快，于是会极大地混进电视列表里——
# 实际点开只有声音没画面。（用户就因为这个吃过亏：“吉林乡村”看着像电视频道，
# 其实是广播台。）
_AUDIO_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\x1aE\xdf\xa3", "WebM/Matroska 容器"),
    (b"OggS", "Ogg 容器"),
    (b"#!AMR", "AMR 音频"),
    (b"ID3", "MP3 音频"),
)


def sniff_audio(head: bytes) -> str:
    """分片头部看起来是纯音频就返回原因，否则返回空串。"""
    if not head:
        return ""
    for magic, why in _AUDIO_MAGIC:
        if head.startswith(magic):
            return why
    # ADTS 裸 AAC：同步字 0xFFF，第二字节高 4 位为 0xF
    if head[0] == 0xFF and len(head) > 1 and (head[1] & 0xF0) == 0xF0:
        return "AAC 裸流"
    return ""


# 低于这个码率的“视领”几乎不可能存在，只可能是广播。
DEFAULT_AUDIO_MAX_KBPS = 400.0

# 第一个分片里留多少字节做样本（容器魔数 + TS 音轨体检）。
# 256KB 约 1400 个 TS 包，足够拿到 PAT/PMT 并估出 PID 占比。
SNIFF_BYTES = 262144

# 分辨率档位。
# 为什么不用 height × 系数：720x576 这类标清源的码率往往比高清还高，
# 用线性系数（1080p 只比 576p 高 60 分）经常把标清顶到第一条线路上。
_RES_TIERS: tuple[tuple[int, float], ...] = (
    (1800, 340.0),   # 4K / 2K
    (1000, 300.0),   # 1080p
    (700, 200.0),    # 720p
    (500, 30.0),     # 720x576 / 480p 等标清
    (1, 0.0),        # 更低
)
_RES_UNKNOWN = 150.0   # 清单没声明分辨率：不奖不罚，落在 720p 与标清之间


def resolution_score(height: int) -> float:
    """分辨率得分。标清（720x576 等）会被明显压低。"""
    if height <= 0:
        return _RES_UNKNOWN
    for floor, bonus in _RES_TIERS:
        if height >= floor:
            return bonus
    return _RES_UNKNOWN


# 720p 及以上算高清（用户的要求：非高清一律往后排）
HD_MIN_HEIGHT = 720


def resolution_rank(height: int) -> int:
    """同频道内线路的**硬档位**：0 = 高清或未知，1 = 实测非高清。

    为什么要硬档位而不是只靠扣分：标清源的码率常常比高清还高
    （实测有 720x576 的源跑到 4Mbps），评分里那 270 分的分辨率差距
    压不住「码率 + 速度」的双重加分，标清还是会被顶到第一条线路上。

    height=0（没解出分辨率）**不**当作非高清：fMP4 / HEVC 这类容器
    本来就解不出 SPS，而它们里面 4K 的不少（HEVC 几乎都是 4K 源），
    误降权的损失比收益大。
    """
    return 1 if 0 < height < HD_MIN_HEIGHT else 0


def _audio_min_kbps(cfg) -> float:
    """音轨码率低于多少算「残缺」（validate.audio_min_kbps）。"""
    if cfg is None:
        return tsinfo.DEFAULT_AUDIO_MIN_KBPS
    try:
        return float(cfg.validate.get("audio_min_kbps") or tsinfo.DEFAULT_AUDIO_MIN_KBPS)
    except (AttributeError, TypeError, ValueError):
        return tsinfo.DEFAULT_AUDIO_MIN_KBPS


def audio_bad_for(audio_kbps: float, cfg=None) -> bool:
    """是否判为音轨残缺。

    只认「**真测出了**低码率」这一种情况（kbps > 0 且低于阈值）。

    早期版本还把「PMT 里声明了音轨但样本里一个包都没抓到」也算残缺，
    结果误标了 20 个正常频道：BBC News / France 24 / CNA / CCTV-1 …
    原因是 fMP4 这类非 TS 内容很容易撞出假的 PAT/PMT。
    宁漏勿错——音轨本来就不是排序重点，误伤正常高清源代价更大。
    """
    return tsinfo.is_bad_audio(audio_kbps, _audio_min_kbps(cfg))


def looks_audio(
    declared_kbps: float,
    measured_kbps: float,
    resolution: str,
    threshold: float = DEFAULT_AUDIO_MAX_KBPS,
) -> bool:
    """靠码率判断是不是广播。

    为什么要多这一道：cnr.cn 这类卫星播流用的是 **MPEG-TS 容器**，
    开头也是 0x47 同步字节，光看容器与视频 TS 完全一样（sniff_audio 识别不了）。
    但它们的码率只有两百多 kbps——真实视频频道不可能这么低。

    只在「没有任何分辨率声明」且「至少有一个码率数据」时才下结论，
    避免把信息不足的流误杀（长春综合的码率就是测不出来的 0）。
    """
    if resolution:
        return False                      # 声明了分辨率，肯定是视频
    candidates = [x for x in (declared_kbps, measured_kbps) if x and x > 0]
    if not candidates:
        return False                      # 拿不到码率，不下结论
    return max(candidates) < threshold

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


def _limit(deadline: float | None, cap: float) -> float:
    """把单个请求的墙钟上限压到「外层剩余预算」和 cap 里的较小值。

    为什么必须这样：外层用 asyncio.wait_for(probe, budget) 兜底，一旦它超时就会
    cancel 掉整个协程，**已经下载到的字节数也一并丢掉**，于是一个正常情况下能测出
    速度的源被当成「整体超时」误杀。

    内层自己看着 deadline 提前收工，外层那道保险就永远不会触发。
    """
    if not deadline:
        return cap
    return max(0.4, min(cap, deadline - time.perf_counter()))


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


async def _download_timed(
    client: httpx.AsyncClient,
    url: str,
    max_bytes: int,
    headers: dict,
    timeout: float,
    hard: float | None = None,
    sniff: bytearray | None = None,
) -> tuple[int, int, float, bool]:
    """下载分片并计时，最多读 max_bytes。

    返回 (status, 字节数, 耗时ms, 是否被截断)。
    测带宽必须真的下载数据——只看 HTTP 状态码和响应头完全看不出会不会卡。
    无论超时还是中途报错，都返回已经读到的字节数和耗时，这样即使慢也有数据可用于
    计算速度（而不是当成失败直接丢掉）。

    「是否被截断」很重要：截断意味着这一段没下完，它只能用来算**速度**，
    不能用来算**码率**（字节数不足，除出来的码率会偏小、把余量虚抬）。

    传了 sniff 就把开头几十字节拷进去，用来判断容器类型（识别广播台）。
    """
    stats = {"status": 0, "n": 0}
    truncated = False
    t0 = time.perf_counter()

    async def _do() -> None:
        async with client.stream(
            "GET", url, headers=headers, timeout=timeout, follow_redirects=True
        ) as resp:
            stats["status"] = resp.status_code
            if resp.status_code >= 400:
                return
            try:
                async for chunk in resp.aiter_bytes(32768):
                    if sniff is not None and len(sniff) < SNIFF_BYTES:
                        sniff.extend(chunk[: SNIFF_BYTES - len(sniff)])
                    stats["n"] += len(chunk)
                    if stats["n"] >= max_bytes:
                        break
            except httpx.HTTPError:
                pass

    budget = hard if hard else _hard_timeout()
    try:
        await asyncio.wait_for(_do(), timeout=budget)
    except asyncio.TimeoutError:
        truncated = True
    except httpx.HTTPError:
        pass

    return stats["status"], stats["n"], (time.perf_counter() - t0) * 1000.0, truncated


async def _measure_hls(
    client: httpx.AsyncClient,
    playlist,
    base: str,
    status: int,
    resolution: str,
    bandwidth: int,
    cfg,
    headers: dict,
    seg_timeout: float,
    min_seg: int,
    hard: float | None,
    deadline: float | None = None,
) -> ProbeResult:
    """连续下载若干个分片，测出实际码率、下载速度和稳定性。

    这是判断「能不能流畅看」的关键：
      speed_kbps   —— 实测下载速度
      bitrate_kbps —— 视频本身码率（用已完整下载的分片字节数 ÷ 时长）
      headroom     —— speed / bitrate，越大越不容易卡

    deadline 是外层给的墙钟截止时刻。每个分片的硬超时都会被压到「剩余预算」以内，
    保证循环一定能自己走完并 return，而不是被外层 cancel 掉、连已测到的数据都丢掉。
    """
    v = cfg.validate

    segs = list(playlist.segments)
    if not segs and playlist.init_segment:
        segs = [hls.Segment(uri=playlist.init_segment, duration=0.0)]
    if not segs:
        return ProbeResult(False, "hls", status, resolution=resolution,
                           bandwidth=bandwidth, error="清单里没有可用分片")

    want = max(1, int(v.get("bw_segments") or 3))
    sample_bytes = max(262144, int(v.get("bw_sample_bytes") or 2_400_000))
    min_speed = float(v.get("min_speed_kbps") or 0)
    drop_audio = bool(v.get("drop_audio", True))
    cap = hard or _hard_timeout()

    total_bytes = 0
    total_ms = 0.0
    full_bytes = 0          # 完整读完的分片字节数（用来算码率，不受截断影响）
    full_dur = 0.0
    ok_segments = 0
    attempted = 0           # 真的发起过的分片数（稳定性 = ok / attempted）
    ts_prof: tsinfo.TsProfile | None = None   # TS 体检结果，音轨码率靠它算

    targets = segs[:want]
    for seg in targets:
        if total_bytes >= sample_bytes:
            break
        seg_url = hls.absolute(base, seg.uri)
        if not seg_url:
            continue

        left = deadline - time.perf_counter() if deadline else cap
        if left <= 0.4:
            # 预算耗尽。已经拿到数据就带着它正常返回，交给速度阈值判断；
            # 一点没拿到才判失败。绝不能在这里被外层 cancel。
            if ok_segments:
                break
            return ProbeResult(False, "hls", status, resolution=resolution,
                               bandwidth=bandwidth, error="测速超时(未取到数据)")

        hard_seg = min(cap, left)
        soft = max(0.4, min(seg_timeout, hard_seg))

        # 按「总预算」分配：第一个分片给足，尽量完整读完才能算出真实码率
        budget = min(sample_bytes, max(sample_bytes - total_bytes, 262144))
        attempted += 1
        # 第一个分片顺便留一段样本：既用来嗅容器类型（识别广播台），
        # 也用来给 TS 做音轨体检（解析 PAT/PMT，数各 PID 的包数）
        sniff = bytearray() if ok_segments == 0 else None
        st, n, ms, cut = await _download_timed(
            client, seg_url, budget, headers, soft, hard_seg, sniff
        )
        if st and st >= 400:
            if ok_segments == 0:
                return ProbeResult(False, "hls", st, resolution=resolution,
                                   bandwidth=bandwidth, error=f"分片 HTTP {st}")
            break
        if n < min_seg:
            break

        # 广播电台也大量用 HLS 分发，速度还很快，会被当成好源混进电视列表。
        # 点开只有声音没画面，所以这里直接判死。
        if sniff is not None:
            head = bytes(sniff)
            if drop_audio:
                why = sniff_audio(head[:16])
                if why:
                    return ProbeResult(False, "audio", status, resolution=resolution,
                                       bandwidth=bandwidth,
                                       error=f"纯音频流（{why}），不是电视频道")
            # 音轨体检：音轨码率远低于正常值的源，听着就是唦唦的噪音（CCTV-5+ 就踩过）
            prof = tsinfo.profile(head)
            if prof.ok:
                ts_prof = prof

        total_bytes += n
        total_ms += ms
        # 只有「服务端主动发完、且没被墙钟截断」的分片才能拿来算码率
        if not cut and n < budget and seg.duration > 0:
            full_bytes += n
            full_dur += seg.duration
        ok_segments += 1

    if ok_segments == 0 or total_bytes < min_seg:
        return ProbeResult(False, "hls", status, resolution=resolution,
                           bandwidth=bandwidth, error="分片数据不足")

    # 清单里没声明分辨率时，用从 TS 里解出来的真实分辨率补上。
    # 实测只有 9.6% 的源带 RESOLUTION（197 条可用流里只有 19 条），
    # 不补这一下，「720x576 往后排」就基本不起作用。
    if not resolution and ts_prof and ts_prof.resolution:
        resolution = ts_prof.resolution

    speed_kbps = total_bytes * 8.0 / max(total_ms, 1.0)
    if full_dur > 0:
        bitrate_kbps = full_bytes * 8.0 / full_dur / 1000.0
    elif bandwidth:
        bitrate_kbps = bandwidth / 1000.0
    else:
        bitrate_kbps = 0.0

    # 音轨码率 = 整条流码率 × 音轨包占比（不需要额外测时长）
    audio_kbps = round(ts_prof.audio_kbps(bitrate_kbps), 1) if ts_prof else 0.0
    audio_codec = ts_prof.audio_codec if ts_prof else ""
    audio_share = round(ts_prof.audio_share, 5) if ts_prof else 0.0
    # 音轨残缺：只有真测出低码率才算（CCTV-5+ 实测 23.8k，听着是唣唣的噪音）
    audio_bad = audio_bad_for(audio_kbps, cfg)

    requested = max(attempted, 1)
    stability = round(ok_segments / requested * 100.0, 1)

    # 码率维度的广播识别（TS 容器的音频流容器特征与视频一样，只能靠码率区分）
    if drop_audio:
        audio_max = float(v.get("audio_max_kbps") or DEFAULT_AUDIO_MAX_KBPS)
        if looks_audio(bandwidth / 1000.0, bitrate_kbps, resolution, audio_max):
            return ProbeResult(False, "audio", status, resolution=resolution,
                               bandwidth=bandwidth,
                               bitrate_kbps=round(bitrate_kbps, 1),
                               speed_kbps=round(speed_kbps, 1),
                               stability=stability,
                               audio_kbps=audio_kbps, audio_codec=audio_codec,
                               audio_share=audio_share, audio_bad=audio_bad,
                               error=f"纯音频流（码率仅 {max(bandwidth / 1000.0, bitrate_kbps):.0f}k，"
                                     f"应为广播），不是电视频道")

    if min_speed > 0 and speed_kbps < min_speed:
        return ProbeResult(False, "hls", status, resolution=resolution, bandwidth=bandwidth,
                           bitrate_kbps=round(bitrate_kbps, 1), speed_kbps=round(speed_kbps, 1),
                           stability=stability, audio_kbps=audio_kbps,
                           audio_codec=audio_codec, audio_share=audio_share,
                           audio_bad=audio_bad,
                           error=f"带宽不足 {speed_kbps:.0f}kbps")

    return ProbeResult(True, "hls", status, resolution=resolution, bandwidth=bandwidth,
                       bitrate_kbps=round(bitrate_kbps, 1), speed_kbps=round(speed_kbps, 1),
                       stability=stability, audio_kbps=audio_kbps,
                       audio_codec=audio_codec, audio_share=audio_share,
                       audio_bad=audio_bad)


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
    measure: bool = False,
    deadline: float | None = None,
) -> ProbeResult:
    status, hdrs, body, final = await _read_head(
        client, url, manifest_limit, headers, timeout, _limit(deadline, hard or _hard_timeout())
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
            client, sub_url, manifest_limit, headers, timeout,
            _limit(deadline, hard or _hard_timeout()),
        )
        if s2 >= 400:
            return ProbeResult(False, "hls", s2, error=f"子清单 HTTP {s2}")

        base = final2
        playlist = hls.parse_playlist(body2.decode("utf-8", errors="ignore"))
        depth += 1

    if not deep and not measure:
        return ProbeResult(True, "hls", status, resolution=resolution, bandwidth=bandwidth)

    if measure:
        return await _measure_hls(
            client, playlist, base, status, resolution, bandwidth,
            cfg, headers, seg_timeout, min_seg, hard, deadline,
        )

    # 第一阶段：只读第一个分片的前 seg_limit 字节，确认真能出流
    # （便宜、可以高并发；带宽留到第二阶段低并发去测）
    seg_uri = playlist.segments[0].uri if playlist.segments else playlist.init_segment
    if not seg_uri:
        return ProbeResult(False, "hls", status, error="清单里没有可用分片")

    seg_url = hls.absolute(base, seg_uri)
    try:
        s3, _, body3, _ = await _read_head(
            client, seg_url, seg_limit, headers, seg_timeout,
            _limit(deadline, hard or _hard_timeout()),
        )
    except httpx.HTTPError as exc:
        return ProbeResult(False, "hls", status, error=f"分片请求失败: {exc}"[:120])

    if s3 >= 400:
        return ProbeResult(False, "hls", s3, error=f"分片 HTTP {s3}")
    if len(body3) < min_seg:
        return ProbeResult(False, "hls", s3, error=f"分片过小({len(body3)}B)")

    return ProbeResult(True, "hls", status, resolution=resolution, bandwidth=bandwidth)


async def probe(
    client: httpx.AsyncClient,
    stream: Stream,
    cfg,
    timeout: float | None = None,
    measure: bool = False,
    budget: float | None = None,
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
    # 整次探测的墙钟截止时刻。传下去之后，内层每个请求都会自己压小超时，
    # 于是 probe_all 里那道 asyncio.wait_for 只是个永远不该被触发的保险。
    deadline = t0 + budget if budget and budget > 0 else None
    try:
        # 先按 URL 猜类型；HLS 走深检
        kind_guess = guess_kind(stream.url, "")

        if kind_guess == "hls":
            res = await _validate_hls(
                client, stream.url, cfg, headers, timeout,
                manifest_limit, seg_limit, seg_timeout, min_seg, deep, hard, measure,
                deadline,
            )
            res.latency_ms = (time.perf_counter() - t0) * 1000
            return res

        status, hdrs, body, final = await _read_head(
            client, stream.url, max(seg_limit, 188 * 8), headers, timeout,
            _limit(deadline, hard),
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
                manifest_limit, seg_limit, seg_timeout, min_seg, deep, hard, measure,
                deadline,
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
    """评分：**带宽余量优先，再看画质，音轨有毛病直接降权**。

    之前以延迟为主，结果「能出流但只有 200kbps」的源能排到前面——点开能播、
    实际一直转圈。现在改成：供得上数据 > 画质 > 延迟。
    """
    score = 1000.0

    headroom = stream.headroom
    if headroom <= 0 and stream.bitrate_kbps > 0:
        headroom = stream.speed_kbps / stream.bitrate_kbps

    score += min(headroom, 6.0) * 80.0                     # 带宽余量，最多 +480
    score += min(stream.speed_kbps / 1000.0, 12.0) * 20.0  # 绝对速度，最多 +240
    score += min(stream.bitrate_kbps, 8000.0) * 0.02       # 码率（画质），最多 +160
    score += resolution_score(stream.height)               # 分辨率档位，标清被压到最低
    score += (stream.stability / 100.0) * 120.0            # 稳定性，最多 +120
    score -= min(stream.latency_ms, 5000.0) * 0.02         # 延迟只做微调，最多 -100
    score += min(stream.ok_count, 20) * 4.0                # 历史稳定加分
    score -= stream.fail_streak * 120.0
    # 音轨残缺的源（视频很高清、声音是噪音）降权
    if stream.audio_bad:
        score -= tsinfo.BAD_AUDIO_PENALTY
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

    # 第二阶段（带宽测速）必须低并发，否则自己把带宽占满，测出来全是慢的
    do_bw = bool(cfg.validate.get("bw_enabled", True))
    bw_concurrency = max(1, int(cfg.validate.get("bw_concurrency") or 8))
    bw_total_timeout = float(cfg.validate.get("bw_total_timeout") or 90)

    limits = httpx.Limits(
        max_connections=max(concurrency, bw_concurrency),
        max_keepalive_connections=max(concurrency // 2, 10),
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

    n_first = len(streams)

    async with httpx.AsyncClient(**kwargs) as client:

        async def run_phase(items, conc, measure, base_done, total, phase_limit, label):
            sem = asyncio.Semaphore(conc)
            done = 0
            if on_progress and items:
                on_progress(base_done, total, sum(1 for s in streams if s.ok), label)

            async def _attempt(st: Stream, deadline: float) -> ProbeResult:
                # 重试共用同一份预算：否则「一次探测用满预算、重试再来一份」，
                # 外层 wait_for 一定会把它判成整体超时，白跑一趟。
                async def once() -> ProbeResult:
                    left = deadline - time.perf_counter() if deadline else 0.0
                    return await probe(
                        client, st, cfg, measure=measure,
                        budget=left if deadline else phase_limit,
                    )

                result = await once()
                for _ in range(retries):
                    if result.ok:
                        break
                    # 只对超时/连接类错误重试，HTTP 4xx 说明源本身有问题
                    if result.status and 400 <= result.status < 500:
                        break
                    # 剩下的预算不够再跑一轮了，直接罢手
                    if deadline and deadline - time.perf_counter() < 1.0:
                        break
                    result = await once()
                return result

            async def worker(st: Stream) -> None:
                async with sem:
                    if history.is_blacklisted(st.url):
                        st.skipped = True
                        st.error = "已拉黑（冷却中）"
                        return

                    t0 = time.perf_counter()
                    limit = phase_limit if measure else total_timeout
                    deadline = t0 + limit if limit > 0 else 0.0
                    try:
                        # 整体墙钟上限：最后一道保险。内层已经看着 deadline 提前收工，
                        # 正常情况这里永远不会被触发。
                        if limit > 0:
                            result = await asyncio.wait_for(
                                _attempt(st, deadline), timeout=limit + 0.5
                            )
                        else:
                            result = await _attempt(st, 0.0)
                    except asyncio.TimeoutError:
                        result = ProbeResult(
                            False, "other", 0, (time.perf_counter() - t0) * 1000,
                            error=f"整体超时(>{limit:.0f}s)",
                        )
                    except Exception as exc:  # noqa: BLE001 - 绝不让单条流中断整轮
                        result = ProbeResult(
                            False, "other", 0, (time.perf_counter() - t0) * 1000,
                            error=f"{type(exc).__name__}: {exc}"[:120],
                        )

                    st.ok = result.ok
                    st.kind = result.kind
                    st.status = result.status
                    st.latency_ms = round(result.latency_ms, 1)
                    st.resolution = result.resolution
                    st.height = result.height
                    st.bandwidth = result.bandwidth
                    st.bitrate_kbps = result.bitrate_kbps
                    st.speed_kbps = result.speed_kbps
                    st.stability = result.stability
                    st.headroom = round(result.headroom, 2)
                    st.audio_kbps = result.audio_kbps
                    st.audio_codec = result.audio_codec
                    st.audio_share = result.audio_share
                    st.audio_bad = result.audio_bad
                    st.error = result.error
                    st.score = compute_score(st) if result.ok else 0.0
                    history.record(st)

            tasks = [asyncio.create_task(worker(s)) for s in items]
            for fut in asyncio.as_completed(tasks):
                await fut
                done += 1
                if on_progress and (done % 25 == 0 or done == len(items)):
                    on_progress(base_done + done, total, sum(1 for s in streams if s.ok), label)

        # ---- 第一阶段：可达性。高并发，但每个流只读几十 KB ----
        await run_phase(streams, concurrency, False, 0, n_first, total_timeout, "可达性")

        # ---- 第二阶段：带宽测速。**必须低并发** ----
        # 如果和第一阶段一样开 200 并发，等于同时从 200 个服务器下载，
        # 把自己的带宽占满，测出来每个源都只有几百 kbps，结论全是错的。
        alive = [s for s in streams if s.ok]
        if do_bw and alive:
            await run_phase(
                alive, bw_concurrency, True, n_first, n_first + len(alive),
                bw_total_timeout, "带宽测速",
            )

    return streams

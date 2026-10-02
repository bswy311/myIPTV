"""带宽测速与评分的回归测试。

直接运行（无需 pytest）：
    python tests/test_bandwidth.py
"""

from __future__ import annotations

import asyncio
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from iptv import hls  # noqa: E402
from iptv.models import Stream  # noqa: E402
from iptv.validate import _measure_hls, compute_score  # noqa: E402

MEDIA_PLAYLIST = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:6
#EXTINF:6.000,
seg0.ts
#EXTINF:6.000,
seg1.ts
#EXTINF:5.760,
seg2.ts
"""

MASTER_PLAYLIST = """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=1200000,RESOLUTION=1280x720
720/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=4000000,RESOLUTION=1920x1080
1080/index.m3u8
"""


def test_media_playlist_parses_segment_durations():
    """算码率要靠 #EXTINF 的时长，必须解析出来。"""
    pl = hls.parse_playlist(MEDIA_PLAYLIST)
    assert not pl.is_master
    assert [s.uri for s in pl.segments] == ["seg0.ts", "seg1.ts", "seg2.ts"]
    assert pl.segments[0].duration == 6.0
    assert abs(pl.segments[2].duration - 5.76) < 1e-6


def test_master_playlist_parsing_unaffected():
    pl = hls.parse_playlist(MASTER_PLAYLIST)
    assert pl.is_master
    assert pl.segments == []
    best = hls.best_variant(pl)
    assert best is not None
    assert best.bandwidth == 4000000
    assert best.resolution == "1920x1080"


def test_score_prefers_bandwidth_headroom_over_latency():
    """核心回归：这是「能打开但一直转圈」的根因。

    以前按延迟排序，B 会比 A 分高；现在必须反过来。
    """
    # A：速度充足（余量 3x），但延迟偏高
    a = Stream(url="a", ok=True, kind="hls", latency_ms=1800,
               speed_kbps=9000, bitrate_kbps=3000, height=1080, stability=100)
    # B：延迟很低，但速度喂不饱码率（余量 0.6x），实际会卡
    b = Stream(url="b", ok=True, kind="hls", latency_ms=120,
               speed_kbps=900, bitrate_kbps=1500, height=720, stability=100)

    assert compute_score(a) > compute_score(b), (
        compute_score(a), compute_score(b)
    )


def test_score_rewards_stability():
    good = Stream(url="g", ok=True, kind="hls", speed_kbps=8000,
                  bitrate_kbps=3000, height=1080, stability=100)
    flaky = Stream(url="f", ok=True, kind="hls", speed_kbps=8000,
                   bitrate_kbps=3000, height=1080, stability=33)
    assert compute_score(good) > compute_score(flaky)


def test_score_rewards_higher_bitrate_at_same_headroom():
    hi = Stream(url="hi", ok=True, kind="hls", speed_kbps=12000,
                bitrate_kbps=4000, height=1080, stability=100)
    lo = Stream(url="lo", ok=True, kind="hls", speed_kbps=3000,
                bitrate_kbps=1000, height=576, stability=100)
    assert compute_score(hi) > compute_score(lo)


# ---------------------------------------------------------------------------
# 墙钟预算（回归：曾经把好源批量误判成「整体超时」）
# ---------------------------------------------------------------------------


class _FakeCfg:
    def __init__(self, validate: dict):
        self.validate = validate
        self.network: dict = {}


class _FakeResp:
    """按固定码率吐数据的假响应。payload 可以指定开头的容器特征字节。"""

    CHUNK = 32768

    def __init__(self, kbps: float, payload: bytes = b""):
        self.status_code = 200
        self._payload = payload
        self._first = True
        self._delay = self.CHUNK * 8.0 / (kbps * 1000.0) if kbps else 0.0

    async def aiter_bytes(self, _n: int):
        for _ in range(100000):
            if self._delay:
                await asyncio.sleep(self._delay)
            if self._first and self._payload:
                self._first = False
                pad = b"\x47" * max(0, self.CHUNK - len(self._payload))
                yield self._payload + pad
            else:
                yield b"\x47" * self.CHUNK

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeClient:
    def __init__(self, kbps: float, payload: bytes = b""):
        self._kbps = kbps
        self._payload = payload

    def stream(self, *_a, **_kw):
        return _FakeResp(self._kbps, self._payload)


async def _measure_with_budget(kbps: float, budget: float, payload: bytes = b""):
    cfg = _FakeCfg({"bw_segments": 2, "bw_sample_bytes": 700000,
                    "min_speed_kbps": 100, "drop_audio": True})
    t0 = time.perf_counter()
    res = await _measure_hls(
        _FakeClient(kbps, payload), hls.parse_playlist(MEDIA_PLAYLIST),
        "http://example.com/", 200, "", 0,
        cfg, {}, 8.0, 1024, 25.0,
        time.perf_counter() + budget,
    )
    return res, time.perf_counter() - t0


def test_sniff_audio_recognizes_radio_containers():
    """广播台也会用 HLS 分发，速度还很快，不识别就会混进电视列表。

    实例：cnr.cn 的「吉林乡村」（satellitepull.cnr.cn/live/wxjlxcgb）
    实际是吉林乡村广播——看着像电视频道，点开只有声音没画面。
    """
    from iptv.validate import sniff_audio

    assert sniff_audio(b"\x1aE\xdf\xa3" + b"\x00" * 12).startswith("WebM")
    assert sniff_audio(b"OggS\x00\x02\x00\x00") == "Ogg 容器"
    assert sniff_audio(b"ID3\x04\x00\x00\x00") == "MP3 音频"
    assert sniff_audio(b"\xff\xf1\x50\x80\x00") == "AAC 裸流"

    # 真正的视频分片不能误判
    assert sniff_audio(b"G" + b"\x00" * 187) == ""            # MPEG-TS
    assert sniff_audio(b"\x00\x00\x00\x18ftypmp42") == ""     # MP4
    assert sniff_audio(b"") == ""


def test_measure_hls_drops_audio_only_stream():
    """纯音频流要被判死，并且 kind 标成 audio 方便排查。"""
    res, _ = asyncio.run(
        _measure_with_budget(800, 2.0, b"\x1aE\xdf\xa3" + b"\x00" * 8)
    )
    assert not res.ok
    assert res.kind == "audio"
    assert "纯音频流" in (res.error or "")


def test_measure_hls_keeps_normal_video_stream():
    """对照：普通 TS 视频流不能被音频检测误杀。"""
    res, _ = asyncio.run(_measure_with_budget(800, 1.0, b"G" + b"\x00" * 187))
    assert res.ok, res.error


def test_looks_audio_by_bitrate():
    """cnr.cn 的广播流是 TS 容器，光看容器跟视频一样，只能靠码率区分。

    实例：吉林乡村 235kbps、吉林卫视(cnr链路) 232kbps，两者都是广播；
    而长春综合的码率测不出来（0），不能因此就把它当广播杀掉。
    """
    from iptv.validate import looks_audio

    # 广播：码率几百 kbps，没有分辨率声明
    assert looks_audio(228.0, 235.0, "") is True
    assert looks_audio(0.0, 232.0, "") is True
    assert looks_audio(300.0, 0.0, "") is True

    # 视频：任何一条就不该 判为广播
    assert looks_audio(2000.0, 0.0, "") is False      # 声明的就是视频码率
    assert looks_audio(228.0, 235.0, "1280x720") is False  # 有分辨率就是视频
    assert looks_audio(0.0, 3000.0, "") is False
    assert looks_audio(0.0, 0.0, "") is False         # 信息不足，不下结论


def test_measure_hls_finishes_within_budget_and_keeps_data():
    """回归：预算不够时必须自己收工，并且保留已经测到的数据。

    修复前的行为：_measure_hls 让每个分片各等满 segment_timeout(8s)，
    两个分片最坏 16s，超过外层 12s 墙钟；外层 asyncio.wait_for 一 cancel，
    连已经下到的字节也一起丢，于是一个 800kbps 完全能看的源被记成「整体超时」。
    """
    res, elapsed = asyncio.run(_measure_with_budget(800, 1.0))

    assert elapsed < 3.0, f"没有按预算收工，耗时 {elapsed:.1f}s"
    assert res.ok, f"应判可用，实际 error={res.error!r}"
    assert 500 <= res.speed_kbps <= 1200, f"速度估算不准: {res.speed_kbps}"
    assert res.stability == 100.0, f"只试了 1 个分片不该算不稳定: {res.stability}"


def test_measure_hls_tiny_budget_returns_failure_not_hang():
    """预算极小且服务器极慢时，也要快速返回失败，而不是干等 segment_timeout。"""
    res, elapsed = asyncio.run(_measure_with_budget(8, 0.5))

    assert elapsed < 2.0, f"慢速流拖了 {elapsed:.1f}s"
    assert not res.ok


def test_probe_all_smoke():
    """冒烟测试：probe_all 两个阶段都要能跑通，不报 NameError 这类低级错误。

    之前把 run_phase 的参数改了名却漏改 worker 里的引用，单元测试全绿、
    真跑起来每一条流都 NameError —— 因为这个测试缺位。
    """
    from iptv.history import History
    from iptv.models import Stream
    from iptv.validate import probe_all

    cfg = _FakeCfg.__new__(_FakeCfg)
    cfg.validate = {
        "bw_enabled": True, "bw_concurrency": 2, "bw_total_timeout": 2,
        "bw_segments": 2, "bw_sample_bytes": 262144, "min_speed_kbps": 1,
        "deep": True, "manifest_max_bytes": 4096, "segment_bytes": 4096,
        "segment_timeout": 2.0, "request_hard_timeout": 3.0,
        "min_segment_bytes": 1024, "allowed_kinds": ["hls"],
    }
    cfg.network = {
        "concurrency": 2, "timeout": 2.0, "connect_timeout": 1.0,
        "retries": 1, "total_timeout": 3, "verify_ssl": False,
    }

    root = ROOT / "tools"
    root.mkdir(exist_ok=True)
    hist_path = root / "_smoke_history.json"
    if hist_path.exists():
        hist_path.unlink()

    # 连不上的端口：能快速失败，但足以把两个阶段的 worker 路径都走一遍
    streams = [Stream(url=f"http://127.0.0.1:1/s{i}.m3u8") for i in range(3)]
    asyncio.run(probe_all(streams, cfg, History(hist_path), concurrency=2))

    assert all(s.ok is False for s in streams)
    assert all(s.error for s in streams), "失败必须带上原因"
    hist_path.unlink(missing_ok=True)


def _run() -> int:
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())

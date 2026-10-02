"""画质与音轨的回归测试。

覆盖两个线上踩过的坑：
  1. 720x576 这类标清源靠「码率更高」顶到了第一条线路上（用户要求往后排）。
  2. CCTV-5+ 某条线路视频 2.9Mbps 很漂亮，音轨却只有 23.8kbps，放出来是唣唣的噪音。

直接运行（无需 pytest）：
    python tests/test_quality.py
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from iptv import h264, tsinfo  # noqa: E402
from iptv.models import Stream  # noqa: E402
from iptv.publish import group_by_channel  # noqa: E402
from iptv.validate import compute_score, resolution_score  # noqa: E402

# ---------------------------------------------------------------------------
# 真实流的 SPS（从线上源抓的，不是自己造的）——
# 用来验证解析器和真实编码器对得上，而不是「我的写入器跟我的解析器自洽」。
# ---------------------------------------------------------------------------

# CCTV-5 湖南电信 153.0.171.163（profile 100 High，走 chroma_format_idc 分支）
REAL_SPS_1080_A = bytes.fromhex(
    "67640029ac2b403c0223ef011000003e80000c350e00000301eb5500002b07a6ef2e0f8e1750"
)
# CCTV-5 聚合源 yang-1989
REAL_SPS_1080_B = bytes.fromhex(
    "27640028ac2d900780227e5c0440000003004000000f3a1000f420000b71b2f7be0ed0e18c90"
)
# Arirang TV 45.162.64.114（720x540，走裁剪分支）
REAL_SPS_720_540 = bytes.fromhex("674d401f9652816822fde022000007d00001d4c108")

# ---------------------------------------------------------------------------
# 合成一段 MPEG-TS，用来测音轨体检（不联网）
# ---------------------------------------------------------------------------

VIDEO_PID = 0x101
AUDIO_PID = 0x102
PMT_PID = 0x100


def _packet(pid: int, payload: bytes, pusi: bool = False) -> bytes:
    b1 = ((pid >> 8) & 0x1F) | (0x40 if pusi else 0)
    head = bytes([0x47, b1, pid & 0xFF, 0x10 | 0x01])   # afc=01 仅净荷, cc=1
    return head + payload[:184].ljust(184, b"\xFF")


def _pat_section(prog: int = 1) -> bytes:
    body = bytes([prog >> 8, prog & 0xFF, 0xE0 | (PMT_PID >> 8), PMT_PID & 0xFF])
    sec_len = 5 + len(body) + 4
    head = bytes([0x00, 0xB0 | (sec_len >> 8), sec_len & 0xFF,
                  0x00, 0x01, 0xC1, 0x00, 0x00])
    return head + body + b"\x00\x00\x00\x00"           # CRC32 占位


def _pmt_section(streams: list[tuple[int, int]], pcr_pid: int = VIDEO_PID) -> bytes:
    es = b""
    for stype, pid in streams:
        es += bytes([stype, 0xE0 | (pid >> 8), pid & 0xFF, 0xF0, 0x00])
    sec_len = 9 + len(es) + 4
    head = bytes([0x02, 0xB0 | (sec_len >> 8), sec_len & 0xFF,
                  0x00, 0x01, 0xC1, 0x00, 0x00,
                  0xE0 | (pcr_pid >> 8), pcr_pid & 0xFF, 0xF0, 0x00])
    return head + es + b"\x00\x00\x00\x00"             # CRC32 占位


def build_ts(n_video: int, n_audio: int, audio_type: int = 0x0F,
             total: int = 2000, declare_audio: bool = True,
             sps: bytes = b"") -> bytes:
    pmt_streams: list[tuple[int, int]] = [(0x1B, VIDEO_PID)]
    if declare_audio:
        pmt_streams.insert(0, (audio_type, AUDIO_PID))
    out = [
        _packet(0, b"\x00" + _pat_section(), True),
        _packet(PMT_PID, b"\x00" + _pmt_section(pmt_streams), True),
    ]
    for i in range(n_video):
        if i == 0 and sps:
            # 第一个视频包带上 SPS（起始码 + NAL），后面跟一个假的 IDR
            body = b"\x00\x00\x00\x01" + sps + b"\x00\x00\x00\x01\x65"
            out.append(_packet(VIDEO_PID, body + b"\x00" * 64))
        else:
            out.append(_packet(VIDEO_PID, b"\x00" * 184))
    out += [_packet(AUDIO_PID, b"\x00" * 184) for _ in range(n_audio)]
    while len(out) < total:                            # 补空包
        out.append(_packet(0x1FFF, b"\xFF" * 184))
    return b"".join(out)


# ---------------------------------------------------------------------------
# 手工构造 SPS：覆盖用户实际关心的 720x576 标清
# ---------------------------------------------------------------------------

class _BitWriter:
    def __init__(self) -> None:
        self.bits: list[int] = []

    def u(self, n: int, v: int) -> None:
        for i in range(n - 1, -1, -1):
            self.bits.append((v >> i) & 1)

    def ue(self, v: int) -> None:
        m = v + 1
        n = m.bit_length() - 1
        self.bits += [0] * n
        self.u(n + 1, m)

    def rbsp(self) -> bytes:
        self.bits.append(1)                       # rbsp_stop_one_bit
        while len(self.bits) % 8:
            self.bits.append(0)
        out = bytearray()
        for i in range(0, len(self.bits), 8):
            byte = 0
            for bit in self.bits[i:i + 8]:
                byte = (byte << 1) | bit
            out.append(byte)
        return bytes(out)


def _escape(data: bytes) -> bytes:
    """插防竞争字节，和 h264.unescape 配对。"""
    out = bytearray()
    zeros = 0
    for x in data:
        if zeros >= 2 and x <= 3:
            out.append(3)
            zeros = 0
        out.append(x)
        zeros = zeros + 1 if x == 0 else 0
    return bytes(out)


def make_sps(width: int, height: int) -> bytes:
    """造一个 Baseline profile 的 SPS；高度不足 16 的倍数时用裁剪补上。"""
    if width % 16:
        raise ValueError("宽度必须是 16 的倍数")
    w_units, h_units = width // 16, height // 16
    rem = height % 16
    crop_units = (16 - rem) // 2 if rem else 0
    if rem:
        h_units += 1

    bw = _BitWriter()
    bw.u(8, 66)       # profile_idc = Baseline（没有 chroma_format_idc 分支）
    bw.u(8, 0)        # constraint flags
    bw.u(8, 31)       # level_idc
    bw.ue(0)          # seq_parameter_set_id
    bw.ue(0)          # log2_max_frame_num_minus4
    bw.ue(2)          # pic_order_cnt_type = 2
    bw.ue(1)          # max_num_ref_frames
    bw.u(1, 0)        # gaps_in_frame_num_value_allowed_flag
    bw.ue(w_units - 1)
    bw.ue(h_units - 1)
    bw.u(1, 1)        # frame_mbs_only_flag
    bw.u(1, 1)        # direct_8x8_inference_flag
    if crop_units:
        bw.u(1, 1)    # frame_cropping_flag
        bw.ue(0)
        bw.ue(0)
        bw.ue(0)
        bw.ue(crop_units)      # frame_crop_bottom_offset，单位是 CropUnitY
    else:
        bw.u(1, 0)
    bw.u(1, 0)        # vui_parameters_present_flag
    return bytes([0x67]) + _escape(bw.rbsp())


# ---------------------------------------------------------------------------
# 1. 标清降权
# ---------------------------------------------------------------------------

def test_resolution_score_orders_hd_above_sd():
    assert resolution_score(2160) > resolution_score(1080)
    assert resolution_score(1080) > resolution_score(720)
    assert resolution_score(720) > resolution_score(576)


def test_resolution_score_punishes_720x576():
    """720x576 是标清，必须被明显压低。"""
    assert resolution_score(576) < 50
    assert resolution_score(480) <= resolution_score(576)


def test_unknown_resolution_is_not_treated_as_sd():
    """清单没声明分辨率（height=0）不能当成标清，否则误伤一片源。"""
    assert resolution_score(0) > resolution_score(576)


# ---------------------------------------------------------------------------
# H.264 SPS 真实分辨率解析
# ---------------------------------------------------------------------------

def test_parse_sps_real_1080p_samples():
    """真实流里的 SPS 要解对（profile 100 High，走 chroma_format_idc 分支）。"""
    assert h264.parse_sps(REAL_SPS_1080_A) == (1920, 1080)
    assert h264.parse_sps(REAL_SPS_1080_B) == (1920, 1080)


def test_parse_sps_real_720x540_sample():
    """真实流里的非 1080p（走裁剪分支）。"""
    assert h264.parse_sps(REAL_SPS_720_540) == (720, 540)


def test_parse_sps_720x576():
    """用户实际关心的那种标清：720x576。"""
    assert h264.parse_sps(make_sps(720, 576)) == (720, 576)


def test_parse_sps_handles_cropping():
    """1080 不是 16 的倍数，必须靠裁剪才能还原。"""
    assert h264.parse_sps(make_sps(1920, 1080)) == (1920, 1080)
    assert h264.parse_sps(make_sps(1280, 720)) == (1280, 720)


def test_parse_sps_rejects_garbage():
    assert h264.parse_sps(b"") is None
    assert h264.parse_sps(b"\x67") is None
    assert h264.parse_sps(b"\x65" + b"\x00" * 40) is None      # 不是 SPS(7)
    assert h264.parse_sps(b"\x67" + b"\xff" * 40) is None      # 解出天方夜谭的尺寸


def test_find_sps_skips_bad_candidates():
    """碰到解不出来的候选要接着找下一个，不能被一个假起始码卡死。"""
    junk = b"\x00\x00\x01\x67\xff\xff\xff\xff\xff\xff\xff\xff"
    good = b"\x00\x00\x01" + make_sps(720, 576) + b"\x00\x00\x01\x65"
    assert h264.find_resolution(junk + b"\x11" * 32 + good) == (720, 576)
    assert h264.find_resolution(b"\x11" * 4096) is None


def test_ts_profile_resolution_from_sps():
    """清单不声明分辨率时，TS 体检要从 SPS 把真实分辨率解出来。"""
    data = build_ts(n_video=400, n_audio=40, sps=make_sps(720, 576))
    prof = tsinfo.profile(data)

    assert prof.ok, prof.note
    assert prof.resolution == "720x576"
    assert prof.height == 576
    assert resolution_score(prof.height) < 50


def test_ts_profile_resolution_for_hd():
    data = build_ts(n_video=400, n_audio=40, sps=make_sps(1920, 1080))
    prof = tsinfo.profile(data)

    assert prof.resolution == "1920x1080"
    assert compute_score(Stream(ok=True, height=prof.height, speed_kbps=9000,
                                bitrate_kbps=3000, stability=100)) > \
        compute_score(Stream(ok=True, height=576, speed_kbps=9000,
                             bitrate_kbps=3000, stability=100))


def test_sd_source_ranks_below_hd_even_with_higher_bitrate():
    """回归：标清源以前能靠更高的码率顶到前面。"""
    hd = Stream(url="hd", ok=True, kind="hls", resolution="1920x1080", height=1080,
                speed_kbps=9000, bitrate_kbps=3000, stability=100)
    sd = Stream(url="sd", ok=True, kind="hls", resolution="720x576", height=576,
                speed_kbps=9000, bitrate_kbps=4000, stability=100)

    assert compute_score(hd) > compute_score(sd), (
        compute_score(hd), compute_score(sd)
    )


# ---------------------------------------------------------------------------
# 2. 音轨体检
# ---------------------------------------------------------------------------

def test_ts_profile_reads_audio_track():
    """正常源：音轨占比 4% 左右，估出的码率和实测（CCTV-5 136k）同一量级。"""
    data = build_ts(n_video=2000, n_audio=80)
    prof = tsinfo.profile(data)

    assert prof.ok, prof.note
    assert prof.has_video
    assert prof.audio_pids == (AUDIO_PID,)
    assert prof.audio_codec == "aac"          # stream_type 0x0F
    assert abs(prof.audio_share - 80 / 2080) < 0.005

    kbps = prof.audio_kbps(2900.0)            # 2.9Mbps 的流
    assert 100 < kbps < 125, kbps             # ≈111.5
    assert not tsinfo.is_bad_audio(kbps)


def test_ts_profile_catches_starved_audio():
    """回归：CCTV-5+ 那条 —— 视频 2.9Mbps，音轨只有 23.8k，听着是噪音。"""
    data = build_ts(n_video=2000, n_audio=17)
    prof = tsinfo.profile(data)
    kbps = prof.audio_kbps(2900.0)

    assert 20 < kbps < 30, kbps
    assert tsinfo.is_bad_audio(kbps)


def test_ts_profile_without_audio_track():
    """PMT 里根本没声明音轨。"""
    data = build_ts(n_video=600, n_audio=0, declare_audio=False)
    prof = tsinfo.profile(data)

    assert prof.ok
    assert prof.audio_pids == ()
    assert "没有音轨" in prof.note
    assert prof.audio_kbps(2900.0) == 0.0
    assert not tsinfo.is_bad_audio(0.0)       # 没数据 → 不下结论


def test_ts_profile_flags_declared_but_empty_audio_track():
    """PMT 声明了音轨却一个包都没有（静音轨）—— 也算音轨残缺。"""
    data = build_ts(n_video=600, n_audio=0, declare_audio=True)
    prof = tsinfo.profile(data)

    assert prof.ok
    assert prof.audio_pids == (AUDIO_PID,)
    assert prof.audio_share == 0.0
    assert prof.dead_audio is True
    assert prof.audio_kbps(2900.0) == 0.0


def test_ts_profile_rejects_garbage():
    assert not tsinfo.profile(b"").ok
    assert not tsinfo.profile(b"not a ts stream at all" * 5000).ok
    # TS 同步字对了但没有 PAT
    assert not tsinfo.profile(b"\x47" * 200000).ok


def test_is_bad_audio_threshold():
    assert tsinfo.is_bad_audio(23.8) is True
    assert tsinfo.is_bad_audio(64.0) is False
    assert tsinfo.is_bad_audio(0.0) is False     # 未知不算坏
    assert tsinfo.is_bad_audio(50.0, threshold=48.0) is False


def test_bad_audio_source_scores_lower():
    good = Stream(url="g", ok=True, kind="hls", height=1080, speed_kbps=9000,
                  bitrate_kbps=3000, stability=100, audio_kbps=136.0)
    bad = Stream(url="b", ok=True, kind="hls", height=1080, speed_kbps=9000,
                 bitrate_kbps=3000, stability=100, audio_kbps=23.8, audio_bad=True)

    assert compute_score(good) - compute_score(bad) >= tsinfo.BAD_AUDIO_PENALTY


def test_bad_audio_line_sorted_last_within_channel():
    """同频道内，音轨残缺的线路必须排到最后 —— 这才是「往后排」。"""
    good = Stream(url="good", key="cctv5+", display="CCTV-5+", category="央视",
                  ok=True, kind="hls", height=1080, speed_kbps=9000,
                  bitrate_kbps=2900, stability=100, audio_kbps=256.0, score=900)
    bad = Stream(url="bad", key="cctv5+", display="CCTV-5+", category="央视",
                 ok=True, kind="hls", height=1080, speed_kbps=9000,
                 bitrate_kbps=3200, stability=100, audio_kbps=23.8,
                 audio_bad=True, score=1800)

    groups = group_by_channel([bad, good])
    assert [s.url for s in groups["cctv5+"]] == ["good", "bad"]


def test_unknown_audio_does_not_go_last():
    """没测到音轨（非 TS 容器）的源不能被误排到最后。"""
    known = Stream(url="known", key="k", ok=True, kind="hls", height=1080,
                   speed_kbps=9000, bitrate_kbps=3000, stability=100,
                   audio_kbps=136.0, score=1000)
    unknown = Stream(url="unknown", key="k", ok=True, kind="hls", height=1080,
                     speed_kbps=9000, bitrate_kbps=3000, stability=100,
                     audio_kbps=0.0, score=1500)

    groups = group_by_channel([known, unknown])
    assert [s.url for s in groups["k"]] == ["unknown", "known"]


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
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
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())

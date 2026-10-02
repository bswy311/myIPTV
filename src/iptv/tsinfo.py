"""MPEG-TS 体检：判断一条 TS 流的音轨是否正常。

为什么需要它：IPTV 头端偶尔会推出「音轨残缺」的流——视频码率很高、跑分很漂亮，
看着是最该排第一的那条线路，但音轨只有二十几 kbps（正常 128~256），
解出来是一路唦唦的白噪音。

实测案例（同一家源的两个频道）：
    CCTV-5    音轨 136.2 kbps / 平均帧长 363 B   —— 正常
    CCTV-5+   音轨  23.8 kbps / 平均帧长  63.5 B —— 有噪音
两者视频码率都在 2.9 Mbps 上下，光看视频挑不出来。

这里只做包级统计，不解码、不依赖第三方库：解析 PAT/PMT 拿到音视频 PID，
再数一遍各 PID 的包数，就能估出音轨码率。
"""

from __future__ import annotations

from dataclasses import dataclass

from . import h264

# PMT 里的 stream_type
AUDIO_TYPES = {0x03, 0x04, 0x0F, 0x11, 0x1C, 0x81, 0x83, 0x84, 0x85, 0x87, 0x8A}
VIDEO_TYPES = {0x01, 0x02, 0x1B, 0x24, 0x42}

CODEC_NAMES = {
    0x03: "mp2", 0x04: "mp2", 0x0F: "aac", 0x11: "aac", 0x1C: "aac",
    0x81: "ac3", 0x83: "truehd", 0x84: "eac3", 0x85: "dts", 0x87: "eac3", 0x8A: "dts",
}

NULL_PID = 0x1FFF


@dataclass
class TsProfile:
    """一条 TS 流的体检结果。"""

    ok: bool = False                  # PAT + PMT 都解析出来了
    has_video: bool = False
    audio_pids: tuple[int, ...] = ()
    audio_codec: str = ""
    audio_share: float = 0.0          # 音轨包数 / （总包数 - 空包数）
    scrambled: bool = False           # 净荷被加密（IPTV 头端加密频道）
    multi_audio: int = 0              # 音轨条数，>1 时播放器可能选错
    dead_audio: bool = False          # PMT 里声明了音轨，但一个包都没收到
    packets: int = 0                  # 统计到的有效包数
    width: int = 0                    # 从 H.264 SPS 解出的真实宽度
    height: int = 0                   # 从 H.264 SPS 解出的真实高度
    note: str = ""

    @property
    def resolution(self) -> str:
        """形如 "1920x1080"；没解出来就返回空串。"""
        return f"{self.width}x{self.height}" if self.width and self.height else ""

    def audio_kbps(self, total_kbps: float) -> float:
        """用「整条流码率 × 音轨包占比」估算音轨码率。

        音轨包占比和音轨字节占比几乎等价（每个 TS 包都是 188 字节），
        所以不需要额外测时长。
        """
        if not self.ok or not self.audio_pids or total_kbps <= 0:
            return 0.0
        return total_kbps * self.audio_share


# ------------------------------------------------------------------ TS 基础

def _payload_start(buf: bytes, off: int) -> int | None:
    """返回该 TS 包净荷起始偏移；无净荷返回 None。"""
    afc = (buf[off + 3] >> 4) & 0x03
    if afc == 1:                     # 01 = 仅净荷
        return off + 4
    if afc == 3:                     # 11 = 适配字段 + 净荷
        p = off + 5 + buf[off + 4]
        return p if p < off + 188 else None
    return None                      # 10 = 仅适配字段


def ts_start(buf: bytes) -> int:
    """找出 188 字节对齐的起点，找不到返回 -1。"""
    for cand in (0, 188, 376):
        if len(buf) > cand + 188 and buf[cand] == 0x47:
            return cand
    return -1


def ts_packets(buf: bytes, pids: set[int] | None = None):
    """产出 (pid, pusi, payload)。"""
    start = ts_start(buf)
    if start < 0:
        return
    for off in range(start, len(buf) - 187, 188):
        if buf[off] != 0x47:
            continue
        b1, b2 = buf[off + 1], buf[off + 2]
        pid = ((b1 & 0x1F) << 8) | b2
        if pids is not None and pid not in pids:
            continue
        p = _payload_start(buf, off)
        if p is not None:
            yield pid, bool(b1 & 0x40), buf[p: off + 188]


def scan_pids(buf: bytes) -> dict[int, dict]:
    """统计每个 PID：包数、是否被加扰、连续性计数器错误数、PUSI 数。"""
    out: dict[int, dict] = {}
    start = ts_start(buf)
    if start < 0:
        return out
    for off in range(start, len(buf) - 187, 188):
        if buf[off] != 0x47:
            continue
        b1, b2, b3 = buf[off + 1], buf[off + 2], buf[off + 3]
        pid = ((b1 & 0x1F) << 8) | b2
        d = out.setdefault(pid, {"n": 0, "scr": 0, "cc_err": 0, "pusi": 0, "last_cc": None})
        d["n"] += 1
        if (b3 >> 6) & 0x03:
            d["scr"] += 1
        if b1 & 0x40:
            d["pusi"] += 1
        if pid != NULL_PID:
            cc = b3 & 0x0F
            last = d["last_cc"]
            if last is not None and cc != (last + 1) % 16 and cc != last:
                d["cc_err"] += 1
            d["last_cc"] = cc
    return out


def _first_section(buf: bytes, pid: int, table_id: int) -> bytes | None:
    """取该 PID 上第一个以 table_id 开头的**完整** section。

    必须重组跨包 section：带多音轨/多字幕的频道（CCTV-1、BBC News 这类）
    PMT 轻松超过 184 字节，只读第一个 TS 包会解出错误的 ES 列表——
    实测后果是「音轨 PID 一个包都没有」，被误判成音轨残缺而白白降权 18 个源。
    """
    out = bytearray()
    expected = 0
    started = False
    for _pid, pusi, payload in ts_packets(buf, {pid}):
        if pusi:
            if not payload:
                continue
            body = payload[1 + payload[0]:]           # 跳过 pointer_field
            if len(body) < 3 or body[0] != table_id:
                started, out, expected = False, bytearray(), 0
                continue
            started = True
            out = bytearray(body)
            expected = 3 + (((body[1] & 0x0F) << 8) | body[2])
        elif started:
            out += payload
        if started and expected and len(out) >= expected:
            return bytes(out[:expected])
    return bytes(out) if started and expected and len(out) >= expected else None


def parse_pat(buf: bytes) -> dict[int, int]:
    """返回 {program_number: pmt_pid}。"""
    body = _first_section(buf, 0, 0x00)
    if body is None:
        return {}
    sec_len = ((body[1] & 0x0F) << 8) | body[2]
    end = min(3 + sec_len - 4, len(body))
    out: dict[int, int] = {}
    i = 8
    while i + 4 <= end:
        prog = (body[i] << 8) | body[i + 1]
        if prog:
            out[prog] = ((body[i + 2] & 0x1F) << 8) | body[i + 3]
        i += 4
    return out


def parse_pmt(buf: bytes, pmt_pid: int) -> list[tuple[int, int]]:
    """返回 [(stream_type, elementary_pid)]。"""
    body = _first_section(buf, pmt_pid, 0x02)
    if body is None or len(body) < 16:
        return []
    sec_len = ((body[1] & 0x0F) << 8) | body[2]
    end = min(3 + sec_len - 4, len(body))
    i = 12 + (((body[10] & 0x0F) << 8) | body[11])   # 跳过 program_info
    out: list[tuple[int, int]] = []
    while i + 5 <= end:
        out.append((body[i], ((body[i + 1] & 0x1F) << 8) | body[i + 2]))
        i += 5 + (((body[i + 3] & 0x0F) << 8) | body[i + 4])
    return out


# ------------------------------------------------------------------ 体检

def _concat_payloads(buf: bytes, pid: int) -> bytes:
    """把一个 PID 的所有净荷拼起来（PES 头会夹在中间，不影响找起始码）。"""
    out = bytearray()
    for _pid, _pusi, payload in ts_packets(buf, {pid}):
        out += payload
    return bytes(out)


# 低于这个包数就不下结论——PMT 可能还没出现，统计也没意义
MIN_BYTES = 65536


def profile(data: bytes) -> TsProfile:
    """给一段 TS 数据做体检。任何异常都返回 ok=False，绝不上抛。"""
    try:
        return _profile(data)
    except Exception as exc:  # noqa: BLE001 - 体检失败不能影响探测
        return TsProfile(note=f"解析异常 {type(exc).__name__}")


def _profile(data: bytes) -> TsProfile:
    if len(data) < MIN_BYTES:
        return TsProfile(note="数据太少")
    if ts_start(data) < 0:
        return TsProfile(note="不是 MPEG-TS")

    pat = parse_pat(data)
    if not pat:
        return TsProfile(note="没有 PAT")
    pmt_pid = next(iter(pat.values()))
    streams = parse_pmt(data, pmt_pid)
    if not streams:
        return TsProfile(note="没有 PMT")

    counts = scan_pids(data)
    total = sum(v["n"] for p, v in counts.items() if p != NULL_PID)
    if total <= 0:
        return TsProfile(note="没有有效包")

    a_pids = tuple(e for s, e in streams if s in AUDIO_TYPES)
    v_pids = tuple(e for s, e in streams if s in VIDEO_TYPES)
    a_pkts = sum(counts.get(p, {}).get("n", 0) for p in a_pids)
    scr = any(counts.get(p, {}).get("scr", 0) for p in a_pids + v_pids)
    codec = CODEC_NAMES.get(next((s for s, e in streams if s in AUDIO_TYPES), -1), "")

    # 真实分辨率：清单里往往不声明（实测只有 9.6% 的源带 RESOLUTION），
    # 所以从 H.264 的 SPS 里解 —— 没这一步「按分辨率排序」就是空转。
    width = height = 0
    h264_pid = next((e for s, e in streams if s == 0x1B), None)
    if h264_pid is not None and counts.get(h264_pid, {}).get("n", 0) > 20:
        got = h264.find_resolution(_concat_payloads(data, h264_pid))
        if got:
            width, height = got

    note = ""
    dead = bool(a_pids) and a_pkts == 0
    if not a_pids:
        note = "TS 里没有音轨"
    elif dead:
        note = "音轨在 PMT 里声明了，但一个包都没有"
    elif scr:
        note = "音轨已加密"
    elif len(a_pids) > 1:
        note = f"{len(a_pids)} 条音轨"

    return TsProfile(
        ok=True,
        has_video=bool(v_pids),
        audio_pids=a_pids,
        audio_codec=codec,
        audio_share=a_pkts / total,
        scrambled=scr,
        multi_audio=len(a_pids),
        dead_audio=dead,
        packets=total,
        width=width,
        height=height,
        note=note,
    )


# 音轨码率低于这个值就认为「音轨残缺」——正常电视伴音最低也有 64k，
# 实测的坏源是 23.8k。做成配置项（validate.audio_min_kbps）。
DEFAULT_AUDIO_MIN_KBPS = 40.0

# 音轨残缺的源扣多少分。这只是让报告里的排序也能反映出来；
# 真正保证「往后排」的是 publish 里显式的降档（见 _line_rank）。
BAD_AUDIO_PENALTY = 400.0


def is_bad_audio(kbps: float, threshold: float = DEFAULT_AUDIO_MIN_KBPS) -> bool:
    """音轨码率是否低得不正常。

    kbps <= 0 表示「没测得」（非 TS 流、数据不够），此时不下结论——
    判定未知为坏会把一大堆容器格式正常的源误伤。
    """
    return 0 < kbps < threshold

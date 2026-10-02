"""诊断脚本：解析 MPEG-TS，检查音轨与视频轨是否正常。

能查的问题：
  * 加扰（IPTV 加密会让声音变白噪音）
  * 音轨编码 / 采样率 / 声道数
  * 音轨帧数、平均帧长 -> 实际码率（码率异常低 = 音轨基本是空的）
  * 音轨 PES / 帧覆盖率（丢帧 = 卡顿 / 爆音）
  * 音轨同步字错误率（解码错误 = 噪音）

用法：
  python tools/tsprobe.py <url> [<url> ...]
  python tools/tsprobe.py --from-m3u <m3u路径或URL> <频道名正则>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import httpx  # noqa: E402

from iptv.hls import parse_playlist  # noqa: E402
from iptv import tsinfo as _lib     # noqa: E402

STREAM_TYPE = {
    0x01: "MPEG-1 视频", 0x02: "MPEG-2 视频",
    0x03: "MPEG-1 音频(MP2)", 0x04: "MPEG-2 音频(MP3)",
    0x06: "私有数据(PES)", 0x0F: "AAC (ADTS)", 0x11: "AAC (LATM)",
    0x15: "ID3 元数据", 0x1B: "H.264", 0x1C: "AAC (raw)",
    0x24: "HEVC/H.265", 0x42: "AVS", 0x81: "AC-3 (杜比)",
    0x83: "TrueHD", 0x84: "E-AC-3 (DVB)", 0x85: "DTS",
    0x86: "SCTE-35", 0x87: "E-AC-3 (杜比+)", 0x8A: "DTS-HD", 0x90: "PGS 字幕",
}
AUDIO_TYPES = {0x03, 0x04, 0x0F, 0x11, 0x1C, 0x81, 0x83, 0x84, 0x85, 0x87, 0x8A}
VIDEO_TYPES = {0x01, 0x02, 0x1B, 0x24, 0x42}

_AAC_SF = [96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050,
           16000, 12000, 11025, 8000, 7350, 0, 0, 0]
_MPEG1_SF = [44100, 48000, 32000, 0]
_MPEG2_SF = [22050, 24000, 16000, 0]
_MPEG1_L2_BR = [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0]
_MPEG2_L2_BR = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]


# ---------------------------------------------------------------- TS 层

def _payload_start(buf: bytes, off: int) -> int | None:
    afc = (buf[off + 3] >> 4) & 0x03
    if afc == 1:                     # 01 = 仅净荷
        return off + 4
    if afc == 3:                     # 11 = 适配字段 + 净荷
        p = off + 5 + buf[off + 4]
        return p if p < off + 188 else None
    return None                      # 10 = 仅适配字段


def _ts_start(buf: bytes) -> int:
    for cand in (0, 188, 376):
        if len(buf) > cand + 188 and buf[cand] == 0x47:
            return cand
    return -1


def ts_packets(buf: bytes, pids: set[int] | None = None):
    """产出 (pid, pusi, payload)。"""
    start = _ts_start(buf)
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


def parse_pat(buf: bytes) -> dict[int, int]:
    for _pid, _pusi, payload in ts_packets(buf, {0}):
        if not payload:
            continue
        body = payload[1 + payload[0]:]
        if len(body) < 12 or body[0] != 0x00:
            continue
        sec_len = ((body[1] & 0x0F) << 8) | body[2]
        end = min(3 + sec_len - 4, len(body))
        out: dict[int, int] = {}
        i = 8
        while i + 4 <= end:
            prog = (body[i] << 8) | body[i + 1]
            if prog:
                out[prog] = ((body[i + 2] & 0x1F) << 8) | body[i + 3]
            i += 4
        if out:
            return out
    return {}


def parse_pmt(buf: bytes, pmt_pid: int) -> list[tuple[int, int]]:
    for _pid, _pusi, payload in ts_packets(buf, {pmt_pid}):
        if not payload:
            continue
        body = payload[1 + payload[0]:]
        if len(body) < 16 or body[0] != 0x02:
            continue
        sec_len = ((body[1] & 0x0F) << 8) | body[2]
        end = min(3 + sec_len - 4, len(body))
        i = 12 + (((body[10] & 0x0F) << 8) | body[11])
        out: list[tuple[int, int]] = []
        while i + 5 <= end:
            st = body[i]
            out.append((st, ((body[i + 1] & 0x1F) << 8) | body[i + 2]))
            i += 5 + (((body[i + 3] & 0x0F) << 8) | body[i + 4])
        if out:
            return out
    return []


def scan_headers(buf: bytes) -> dict[int, dict]:
    """统计每个 PID 的包数 / 加扰控制 / 连续性计数器错误数。"""
    out: dict[int, dict] = {}
    start = _ts_start(buf)
    if start < 0:
        return out
    for off in range(start, len(buf) - 187, 188):
        if buf[off] != 0x47:
            continue
        b1, b2, b3 = buf[off + 1], buf[off + 2], buf[off + 3]
        pid = ((b1 & 0x1F) << 8) | b2
        d = out.setdefault(pid, {"n": 0, "scr": {}, "cc_err": 0, "last_cc": None})
        d["n"] += 1
        scr = (b3 >> 6) & 0x03
        d["scr"][scr] = d["scr"].get(scr, 0) + 1
        if pid != 0x1FFF:                      # 空包不检查连续性
            cc = b3 & 0x0F
            last = d["last_cc"]
            if last is not None and cc != (last + 1) % 16 and cc != last:
                d["cc_err"] += 1
            d["last_cc"] = cc
    return out


# ------------------------------------------------------- 音轨解复用

def demux_es(buf: bytes, pid: int) -> tuple[bytes, int]:
    """按 PUSI 精确解出基本流（ES），返回 (es_bytes, PES 包数)。

    用 PUSI 而不是搜 0x000001，避免在压缩数据里误判 PES 边界。
    """
    out = bytearray()
    pes = 0
    started = False
    for _pid, pusi, payload in ts_packets(buf, {pid}):
        if pusi:
            if len(payload) < 9 or payload[0] != 0 or payload[1] != 0 or payload[2] != 1:
                started = False
                continue
            if not (0xC0 <= payload[3] <= 0xEF):   # 只收音频/私有 PES
                started = False
                continue
            pes += 1
            out += payload[9 + payload[8]:]
            started = True
        elif started:
            out += payload
    return bytes(out), pes


def adts_stats(es: bytes) -> dict:
    """遍历 ADTS 帧：帧数、平均帧长、同步错误、采样率、声道。"""
    n = 0
    err = 0
    i = 0
    sf = 0
    ch = 0
    while i + 7 <= len(es):
        if es[i] == 0xFF and (es[i + 1] & 0xF0) == 0xF0:
            flen = ((es[i + 3] & 0x03) << 11) | (es[i + 4] << 3) | (es[i + 5] >> 5)
            if flen >= 7:
                if n == 0:
                    sf = _AAC_SF[(es[i + 2] >> 2) & 0x0F]
                    ch = ((es[i + 2] & 0x01) << 2) | (es[i + 3] >> 6)
                n += 1
                i += flen
                continue
        err += 1
        i += 1
    return {"frames": n, "avg": (len(es) / n if n else 0), "err": err,
            "samplerate": sf, "channels": ch, "spf": 1024}


def mp2_stats(es: bytes) -> dict:
    """遍历 MPEG 音频帧：帧数、码率、采样率、声道。"""
    n = 0
    err = 0
    i = 0
    br = sf = ch = 0
    while i + 4 <= len(es):
        if es[i] == 0xFF and (es[i + 1] & 0xE0) == 0xE0:
            ver = (es[i + 1] >> 3) & 0x03      # 3=MPEG1, 2=MPEG2
            layer = (es[i + 1] >> 1) & 0x03    # 2=Layer II
            bri = (es[i + 2] >> 4) & 0x0F
            sfi = (es[i + 2] >> 2) & 0x03
            pad = (es[i + 2] >> 1) & 0x01
            if ver in (2, 3) and layer == 2 and 0 < bri < 15 and sfi != 3:
                table = _MPEG1_L2_BR if ver == 3 else _MPEG2_L2_BR
                srt = _MPEG1_SF if ver == 3 else _MPEG2_SF
                kbps = table[bri]
                rate = srt[sfi]
                if kbps and rate:
                    if n == 0:
                        br, sf = kbps, rate
                        ch = 2 if (es[i + 3] >> 6) == 0 else 1
                    n += 1
                    i += (144 * kbps * 1000) // rate + pad
                    continue
        err += 1
        i += 1
    return {"frames": n, "avg": (len(es) / n if n else 0), "err": err,
            "bitrate": br, "samplerate": sf, "channels": ch, "spf": 1152}


# ---------------------------------------------------------------- 取流

def _client() -> httpx.Client:
    ua = "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    return httpx.Client(follow_redirects=True, verify=False, headers={"User-Agent": ua},
                        timeout=20)


def fetch_stream(url: str, client: httpx.Client, want: int = 3):
    """返回 (说明, ts字节, 已下载秒数)。"""
    r = client.get(url)
    r.raise_for_status()
    body = r.content

    if b"#EXTM3U" not in body[:400] and b"\x47" in body[:64]:
        return "裸 TS", body, 0.0

    text = body.decode("utf-8", "replace")
    if "#EXTM3U" not in text:
        return f"非 m3u8 (content-type={r.headers.get('content-type')})", b"", 0.0

    pl = parse_playlist(text)
    base = url
    if pl.is_master and pl.variants:
        best = max(pl.variants, key=lambda v: v.bandwidth)
        base = urljoin(url, best.uri)
        r2 = client.get(base)
        r2.raise_for_status()
        pl = parse_playlist(r2.text)

    blob = b""
    secs = 0.0
    for seg in pl.segments[:want]:
        try:
            rs = client.get(urljoin(base, seg.uri))
            if rs.status_code == 200 and rs.content:
                blob += rs.content
                secs += seg.duration or pl.target_duration or 0.0
        except Exception:  # noqa: BLE001
            pass
    return (f"{len(pl.segments)} 分片 / 每个 {pl.target_duration:.0f}s / 实取 {secs:.0f}s",
            blob, secs)


def analyze(url: str, client: httpx.Client) -> None:
    print(f"\n=== {url}")
    try:
        info, blob, secs = fetch_stream(url, client)
    except Exception as exc:  # noqa: BLE001
        print(f"  ✗ 拉流失败: {type(exc).__name__}: {exc}")
        return
    print(f"  清单: {info}")
    if not blob:
        print("  ✗ 无分片数据")
        return
    print(f"  已下载 {len(blob) / 1024:.0f} KB")

    pat = parse_pat(blob)
    if not pat:
        print(f"  ✗ PAT 解析失败（不是 TS 流） 头部: {blob[:32].hex(' ')}")
        print(f"    ASCII: {blob[:32]!r}")
        return
    hdr = scan_headers(blob)
    total_pkts = max(len(blob) // 188, 1)

    for prog, pmt_pid in pat.items():
        streams = parse_pmt(blob, pmt_pid)
        if not streams:
            continue
        print(f"  program={prog}  PMT_PID={pmt_pid}")
        a_pids = [(s, e) for s, e in streams if s in AUDIO_TYPES]
        v_pids = [(s, e) for s, e in streams if s in VIDEO_TYPES]

        for st, epid in streams:
            kind = "视频" if st in VIDEO_TYPES else ("音频" if st in AUDIO_TYPES else "其他")
            d = hdr.get(epid, {"n": 0, "scr": {}, "cc_err": 0})
            share = d["n"] / total_pkts * 100
            scr = max(d["scr"]) if d["scr"] else 0
            flag = "  ⚠ 已加扰" if scr else ""
            print(f"    PID {epid:5d} [{kind}] {STREAM_TYPE.get(st, f'0x{st:02X}')}"
                  f"  占比 {share:5.2f}%  包连续性错误 {d['cc_err']}{flag}")
            if scr:
                print("      !! 净荷加密，播放器解出来就是唦唦声")

        if len(a_pids) > 1:
            print(f"    ⚠ 有 {len(a_pids)} 条音轨，播放器可能选错")
        if not v_pids:
            print("    ⚠ 没有视频轨")

        # 库模块（src/iptv/tsinfo.py）的判定——它就是流水线里用的那套
        total_kbps = len(blob) * 8 / secs / 1000 if secs else 0.0
        lib = _lib.profile(blob)
        if lib.ok:
            kbps = lib.audio_kbps(total_kbps)
            bad = lib.dead_audio or _lib.is_bad_audio(kbps)
            print(f"    [库模块] 音轨 {lib.audio_codec or '-'} 占比 {lib.audio_share * 100:.2f}%"
                  f" -> 估算 {kbps:.1f} kbps，判定 {'⚠ 残缺（会被降权排到最后）' if bad else '正常'}"
                  f"{' / ' + lib.note if lib.note else ''}")
            print(f"    [库模块] SPS 真实分辨率 {lib.resolution or '没解出来'}")
        else:
            print(f"    [库模块] 未下结论：{lib.note}")

        for st, epid in a_pids:
            es, pes = demux_es(blob, epid)
            stt = adts_stats(es) if st in (0x0F, 0x11, 0x1C) else mp2_stats(es)
            kbps = len(es) * 8 / secs / 1000 if secs else 0
            rate = stt.get("samplerate") or 0
            expect = secs * rate / stt.get("spf", 1024) if rate and secs else 0
            print(f"    音轨 PID {epid}: ES {len(es) / 1024:.0f} KB / {pes} 个 PES / "
                  f"{stt['frames']} 帧")
            print(f"      实测码率 {kbps:6.1f} kbps | 平均帧长 {stt['avg']:5.1f} B | "
                  f"{rate} Hz {stt['channels']}ch")
            if stt.get("bitrate"):
                print(f"      帧头声明码率 {stt['bitrate']} kbps")
            if expect:
                cover = stt["frames"] / expect * 100
                mark = "  ⚠ 音轨大面积缺失！" if cover < 80 else ""
                print(f"      应有约 {expect:.0f} 帧，实有 {stt['frames']} 帧"
                      f"（覆盖 {cover:.0f}%）{mark}")
            if stt["err"]:
                ratio = stt["err"] / max(len(es), 1) * 100
                # 少量失步是正常的（PES 头、填充字节都会让游走器错位），
                # 实测 468KB 的 MP2 里有 800 字节失步（0.17%）完全不影响播放，
                # 所以按占比判断，不要一看有错就吓人。
                tail = ("  ← 占比偏高，可能影响解码"
                        if ratio > 2.0 else "  （占比低，通常无害）")
                print(f"      ⚠ 同步错误 {stt['err']} 字节 / {len(es)} 字节"
                      f"（{ratio:.2f}%）{tail}")


def extract_urls(src: str, pattern: str) -> list[str]:
    if re.match(r"^https?://", src):
        text = httpx.get(src, timeout=40, follow_redirects=True).text
    else:
        text = Path(src).read_text(encoding="utf-8", errors="replace")
    out: list[str] = []
    want = re.compile(pattern, re.I) if pattern else None
    name = ""
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("#EXTINF"):
            name = ln.split(",", 1)[-1]
        elif ln and not ln.startswith("#") and (want is None or want.search(name)):
            out.append(ln)
    return out


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    args = sys.argv[1:]
    if args and args[0] == "--from-m3u":
        urls = extract_urls(args[1], args[2] if len(args) > 2 else "")
        print(f"匹配到 {len(urls)} 条线路")
    else:
        urls = args
    if not urls:
        print("(无待测线路)")
        return
    with _client() as client:
        for u in urls:
            analyze(u, client)


if __name__ == "__main__":
    import warnings

    warnings.filterwarnings("ignore")
    main()

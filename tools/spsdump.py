"""从一条真实流里抓出 H.264 SPS 原文，用来给测试做固定用例。

用法：python tools/spsdump.py <url> [<url> ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from iptv import h264, tsinfo  # noqa: E402
from tsprobe import _client, fetch_stream  # noqa: E402


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    with _client() as client:
        for url in sys.argv[1:]:
            print(f"\n=== {url}")
            try:
                info, blob, secs = fetch_stream(url, client, want=2)
            except Exception as exc:  # noqa: BLE001
                print(f"  拉流失败: {type(exc).__name__}: {exc}")
                continue
            if not blob:
                print(f"  无数据（{info}）")
                continue

            pat = tsinfo.parse_pat(blob)
            if not pat:
                print("  不是 TS 流")
                continue
            streams = tsinfo.parse_pmt(blob, next(iter(pat.values())))
            pid = next((e for s, e in streams if s == 0x1B), None)
            if pid is None:
                print(f"  没有 H.264 视频轨（{streams}）")
                continue

            es = b"".join(p for _p, _u, p in tsinfo.ts_packets(blob, {pid}))
            nal = h264.find_sps(es)
            if not nal:
                print("  没找到可解析的 SPS")
                continue
            print(f"  SPS NAL ({len(nal)} 字节): {nal.hex()}")
            print(f"  解析结果: {h264.parse_sps(nal)}")


if __name__ == "__main__":
    import warnings

    warnings.filterwarnings("ignore")
    main()

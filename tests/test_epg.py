"""EPG（节目单）相关回归测试。

直接运行（无需 pytest）：
    python tests/test_epg.py
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from iptv.config import load_config  # noqa: E402
from iptv.epg import _looks_like_epg  # noqa: E402


def test_epg_url_is_reachable_domain():
    """EPG 主地址不能是实测已失效的域名。

    回归：配置里原来写的是 https://live.fanmingming.cn/e.xml，
    实测 ConnectTimeout（可能改了域名或遭 DNS 污染），
    播放器上的表现就是「节目单加载失败」。
    现在改成自己托管到 Pages + jsDelivr 兜底。
    """
    cfg = load_config()
    url = str(cfg.output.get("epg_url") or "")
    assert url, "output.epg_url 不能为空"

    primary = url.split(",")[0].strip()
    assert "live.fanmingming.cn" not in primary, (
        "主地址不该是已失效的 fanmingming 域名，实际: " + primary
    )
    assert "github.io" in primary or "jsdelivr" in primary, primary

    # 至少要有两个来源（自己托管 + 第三方镜像），一个挂了还有得用
    assert len([u for u in url.split(",") if u.strip()]) >= 2, url


def test_epg_mirror_list_is_configured():
    """自己托管要有镜像列表，且把国内可达性最好的 jsDelivr 放在前面。"""
    cfg = load_config()
    mirrors = [str(u) for u in (cfg.output.get("epg_mirrors") or []) if str(u).strip()]
    assert mirrors, "output.epg_mirrors 不能为空"
    assert any("jsdelivr" in m for m in mirrors), mirrors
    # raw.githubusercontent.com 和 fanmingming 自家域名实测都不稳，不该排第一
    assert "jsdelivr" in mirrors[0], mirrors


def test_epg_self_host_enabled():
    cfg = load_config()
    assert cfg.output.get("epg_self_host", True) is True, "建议开启自托管 EPG"


def test_epg_gitignore_excludes_downloaded_copy():
    """下回来的 EPG 只发布、不提交（7MB 且每天变，会让 git 历史膨胀）。"""
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "output/e.xml" in text, ".gitignore 要排除 output/e.xml"


def test_looks_like_epg():
    """内容校验：必须足够大且像 XMLTV，避免把错误页当节目单发布出去。"""
    assert _looks_like_epg(b"<?xml version='1.0'?><tv>" + b" " * 200_000) is True
    assert _looks_like_epg(b"<tv>" + b" " * 200_000) is True
    # 太小 / 是网页 / 空
    assert _looks_like_epg(b"<?xml version='1.0'?>") is False
    assert _looks_like_epg(b"<html>404 not found</html>" + b" " * 200_000) is False
    assert _looks_like_epg(b"") is False


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

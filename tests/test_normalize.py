"""频道名归一化与筛选的回归测试。

直接运行（无需 pytest）：
    python tests/test_normalize.py
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from iptv.config import load_config  # noqa: E402
from iptv.models import Stream  # noqa: E402
from iptv.normalize import (  # noqa: E402
    canonical_key,
    categorize,
    clean_name,
    dedupe,
    display_name,
    matches_filter,
    normalize,
    source_modes,
)


def test_clean_name():
    assert clean_name("CCTV-1 综合 高清") == "CCTV1综合"
    assert clean_name("湖南卫视[高清]") == "湖南卫视"
    assert clean_name("CCTV5+ 体育赛事") == "CCTV5+体育赛事"


def test_canonical_key_merges_variants():
    variants = ["CCTV-1", "cctv1", "CCTV1 高清", "CCTV-1 综合", "央视一套"]
    keys = {canonical_key(v) for v in variants}
    assert keys == {"cctv1"}, keys

    assert canonical_key("CCTV5+ 体育") == "cctv5+"
    assert canonical_key("CCTV-5+ 高清") == "cctv5+"
    assert canonical_key("湖南卫视高清") == "湖南卫视"
    assert canonical_key("北京卫视 4K") == "北京卫视"


def test_canonical_key_keeps_distinct_channels_apart():
    assert canonical_key("凤凰卫视中文台") != canonical_key("凤凰卫视资讯台")
    assert canonical_key("CCTV-5") != canonical_key("CCTV-5+")


def test_dedupe_by_url():
    items = [
        Stream(url="http://a/1.m3u8", name="CCTV1"),
        Stream(url="http://a/1.m3u8", name="CCTV1 高清"),
        Stream(url="http://a/2.m3u8", name="CCTV1"),
    ]
    assert len(dedupe(items)) == 2


def test_normalize_and_categorize():
    cfg = load_config()
    streams = [
        Stream(url="http://a/1", name="CCTV-5 体育"),
        Stream(url="http://a/2", name="CCTV-1 综合"),
        Stream(url="http://a/3", name="湖南卫视高清"),
        Stream(url="http://a/4", name="翡翠台"),
        Stream(url="http://a/5", name="五星体育"),
    ]
    normalize(streams, cfg)

    keys = {s.name: s.key for s in streams}
    assert keys["CCTV-5 体育"] == "cctv5"
    assert keys["CCTV-1 综合"] == "cctv1"
    assert keys["湖南卫视高清"] == "湖南卫视"

    cats = {s.name: s.category for s in streams}
    assert cats["CCTV-5 体育"] == "体育", cats
    assert cats["CCTV-1 综合"] == "央视", cats
    assert cats["湖南卫视高清"] == "卫视", cats
    assert cats["翡翠台"] == "港澳台", cats


def test_display_name_cleans_quality_marks():
    assert display_name("CCTV-1 (720p)") == "CCTV-1"
    assert display_name("CCTV-9 (576i)") == "CCTV-9"
    assert display_name("湖南卫视高清") == "湖南卫视"
    assert display_name("CCTV-4K HD (1080p)") == "CCTV-4K"
    assert display_name("凤凰卫视中文台") == "凤凰卫视中文台"
    # 画质写在名字里的频道不能被削掉
    assert display_name("CCTV-4K") == "CCTV-4K"
    assert display_name("CCTV5+ 体育") == "CCTV5+ 体育"


def test_english_channel_names_are_localized():
    # iptv-org 用的是英文名，需要映射成中文并和中文写法归并成同一频道
    assert canonical_key("Beijing Satellite TV") == "北京卫视"
    assert canonical_key("北京卫视") == "北京卫视"
    assert canonical_key("Hunan TV") == "湖南卫视"
    assert canonical_key("Jiangsu Satellite TV") == "江苏卫视"
    assert canonical_key("Zhejiang Satellite TV") == "浙江卫视"
    assert canonical_key("Dragon TV") == "东方卫视"
    assert canonical_key("TVB Jade") == "翡翠台"

    assert display_name("Beijing Satellite TV") == "北京卫视"
    assert display_name("Hunan TV (1080p)") == "湖南卫视"

    # 非中国频道不能被误改
    assert display_name("Okko Sport") == "Okko Sport"
    assert display_name("NBA TV") == "NBA TV"


def test_per_source_filter_override():
    cfg = load_config()
    modes = source_modes(cfg)
    # 源自带 range，声明 all 后不再受中文关键词限制
    assert modes.get("iptv-org-cn") == "all"

    en = Stream(url="u", name="Beijing Satellite TV", source="iptv-org-cn")
    assert matches_filter(en, cfg, modes) is True

    # 同一个频道名，来自需要关键词筛选的源时会被挡掉
    assert matches_filter(en, cfg, {}) is False

    # exclude 规则任何模式下都生效
    bad = Stream(url="u", name="Test Channel 测试", source="iptv-org-cn")
    assert matches_filter(bad, cfg, modes) is False


def test_resolution_marks_do_not_pollute_key():
    # 2160p 曾经漏在正则外，导致 key 变成 hunantv2160p，频道归不进“卫视”
    assert canonical_key("Hunan TV (2160p)") == "湖南卫视"
    assert canonical_key("Hebei TV (2160p)") == "河北卫视"
    assert canonical_key("Shenzhen Satellite TV (2160p)") == "深圳卫视"
    assert clean_name("Hunan TV (2160p)") == "HunanTV"

    # 不能为了去掉分辨率而误伤含数字的台名
    assert canonical_key("TV1000") == "tv1000"
    assert clean_name("TV1000") == "TV1000"


def test_filter_include_and_exclude():
    cfg = load_config()
    assert matches_filter(Stream(url="u", name="CCTV-1 综合"), cfg) is True
    assert matches_filter(Stream(url="u", name="湖南卫视"), cfg) is True
    assert matches_filter(Stream(url="u", name="ATV Test 测试"), cfg) is False
    assert matches_filter(Stream(url="u", name="Random Shopping"), cfg) is False


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
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())

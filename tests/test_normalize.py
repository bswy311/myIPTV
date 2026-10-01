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
    channel_sort,
    clean_name,
    dedupe,
    display_name,
    epg_id,
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
    # 央视分类排在体育之前，所以 CCTV-5 归「央视」，保证央视那组 1~17 是完整的
    assert cats["CCTV-5 体育"] == "央视", cats
    assert cats["CCTV-1 综合"] == "央视", cats
    # 非央视的体育频道仍然归体育
    assert cats["五星体育"] == "体育", cats
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


def test_annotation_and_variant_marks_are_stripped():
    # iptv-org 的标注不应该出现在电视上
    assert display_name("CCTV+ 1 [Not 24/7]") == "CCTV+ 1"
    assert display_name("Beijing Satellite TV [Geo-blocked]") == "北京卫视"
    # 上游的编码/帧率变体应归并成同一频道，作为备用线路
    assert canonical_key("北京卫视 HEVC") == "北京卫视"
    assert canonical_key("北京卫视 50 FPS") == "北京卫视"
    assert canonical_key("北京卫视") == "北京卫视"


def test_cctv_4k_8k_not_destroyed_by_noise_regex():
    # 回归：4K/8K 曾被画质清洗规则当成后缀删掉，使 CCTV-4K 退化成 CCTV
    assert canonical_key("CCTV-4K") == "cctv4k"
    assert canonical_key("CCTV-8K") == "cctv8k"
    assert canonical_key("CCTV-16 4K") == "cctv16"
    assert display_name("CCTV-4K") == "CCTV-4K"


def test_cctv_display_names_are_full():
    cfg = load_config()
    streams = [Stream(url="u", name="CCTV-1"), Stream(url="u2", name="CCTV5+")]
    normalize(streams, cfg)
    assert streams[0].display == "CCTV-1 综合"
    assert streams[1].display == "CCTV-5+ 体育赛事"


def test_epg_ids_match_the_epg_file():
    # 必须和 e.xml 里的 channel id 完全一致，否则节目单匹配不上
    assert epg_id("cctv1") == "CCTV1"
    assert epg_id("cctv5+") == "CCTV5+"
    assert epg_id("cctv4k") == "CCTV4K"
    assert epg_id("北京卫视") == "北京卫视"
    assert epg_id("湖南卫视") == "湖南卫视"
    # 没有节目单的频道返回空
    assert epg_id("吉林都市频道") == ""


def test_channel_sort_fixes_lexicographic_order():
    cfg = load_config()
    names = [f"CCTV-{i}" for i in range(1, 18)] + ["CCTV-5+", "CCTV-4K"]
    streams = [Stream(url=f"u{i}", name=n) for i, n in enumerate(names)]
    normalize(streams, cfg)
    ordered = [s.display for s in sorted(streams, key=channel_sort)]

    assert ordered[0] == "CCTV-1 综合"
    assert ordered[1] == "CCTV-2 财经"
    assert ordered[2] == "CCTV-3 综艺"
    assert ordered[4] == "CCTV-5 体育"
    # CCTV-5+ 紧跟在 CCTV-5 后面，而不是排到最后
    assert ordered[5] == "CCTV-5+ 体育赛事"
    assert ordered[6] == "CCTV-6 电影"
    # 字典序会把 CCTV-10 排到 CCTV-2 前面，这里必须不是那样
    assert ordered.index("CCTV-9 纪录") < ordered.index("CCTV-10 科教")
    assert ordered.index("CCTV-10 科教") < ordered.index("CCTV-17 农业农村")
    assert ordered[-1].startswith("CCTV-4K")


def test_cctv_paid_channels_localized_and_sorted_last():
    cfg = load_config()
    paid = ["CCTV-Billiards", "CCTV-Storm Football", "CCTV-Health", "CCTV-Weapon & Technology"]
    streams = [Stream(url=f"u{i}", name=n)
               for i, n in enumerate(paid + ["CCTV-1", "CCTV-17"])]
    normalize(streams, cfg)

    displays = {s.display for s in streams}
    assert {"央视台球", "央视风云足球", "央视卫生健康", "央视兵器科技"} <= displays

    ordered = [s.display for s in sorted(streams, key=channel_sort)]
    assert ordered[0] == "CCTV-1 综合"
    assert ordered[1] == "CCTV-17 农业农村"
    # 回归：无编号的央视频道曾被当作 0 权重，排到 CCTV-1 前面
    assert ordered.index("央视台球") > ordered.index("CCTV-17 农业农村")


def test_local_channel_whitelist():
    """外省地级市/县级台应被过滤，只留吉林省台和长春台。"""
    cfg = load_config()
    modes = {"src": "all"}   # 模拟 filter: all 的源，此时只剩 exclude 和本地台白名单生效

    def mk(name, group):
        return Stream(url="u", name=name, group=group, source="src")

    assert matches_filter(mk("吉林都市频道", "吉林台"), cfg, modes) is True
    assert matches_filter(mk("长春综合频道", "长春台"), cfg, modes) is True
    assert matches_filter(mk("浙江少儿频道", "浙江台"), cfg, modes) is False
    assert matches_filter(mk("黑龙江都市频道", "黑龙江台"), cfg, modes) is False
    assert matches_filter(mk("上虞新闻综合频道", "浙江台"), cfg, modes) is False
    # 卫视台不是地方台，不受白名单影响
    assert matches_filter(mk("北京卫视", "卫视台"), cfg, modes) is True


def test_satellite_sort_puts_jilin_near_heilongjiang():
    cfg = load_config()
    streams = [Stream(url=f"u{i}", name=n) for i, n in enumerate(
        ["广东卫视", "吉林卫视", "北京卫视", "黑龙江卫视", "湖南卫视"])]
    normalize(streams, cfg)
    ordered = [s.display for s in sorted(streams, key=channel_sort)]
    # 行政区划顺序：北京 → 吉林 → 黑龙江，吉林应该在黑龙江前面
    assert ordered.index("黑龙江卫视") - ordered.index("吉林卫视") == 1
    assert ordered.index("北京卫视") < ordered.index("吉林卫视")
    assert ordered.index("吉林卫视") < ordered.index("湖南卫视")


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

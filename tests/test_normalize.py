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


def test_published_group_order():
    """输出分组顺序必须是约定的这个顺序，且不再包含「体育」。"""
    cfg = load_config()
    order = list(cfg.get("output_order") or [])
    assert order[:6] == ["央视", "卫视", "吉林", "长春", "港澳台", "国际新闻"], order
    assert "体育" not in order, order

    # 分类定义里也要保留「吉林」——现在上游没有可用省台，这组是空的，
    # 但保留着以后出现了新源才会自动归到这里。
    names = [c.get("name") for c in (cfg.categories or [])]
    assert "吉林" in names, names
    assert "长春" in names, names

    # 体育整类丢弃（配置层面），但分类定义保留，方便以后恢复
    assert "体育" in [str(x) for x in (cfg.filter.get("drop_categories") or [])]
    assert "体育" in names, names


def test_exact_list_keeps_only_named_channels():
    """国际新闻用 exact 精确名单，只留最主流电视台的英语主频。

    背景：原来靠 bbc / cnn / dw / cnbc / cna 这类通配关键词，
    结果把 BBC Earth、BBC Drama、BBC One、CNBC Awaaz、CNN TURK、
    DW Arabic、Sky News Arabia、Al Jazeera Mubasher 一起捞了进来
    （实测国际新闻组有 87 个频道）。
    """
    cfg = load_config()

    def cat_of(name: str) -> str:
        st = Stream(url="u", name=name, source="src")
        st.key = canonical_key(name)
        st.display = display_name(name)
        return categorize(st, cfg.categories)

    # 名单内的主流英语新闻台
    for n in ("BBC News", "CNN", "Al Jazeera English", "France 24 English",
              "DW English", "Euronews English", "Sky News", "Reuters TV",
              "NHK World-Japan", "CNA (Singapore)", "Arirang TV",
              "Bloomberg TV", "CNBC UK", "NBC News NOW", "Fox News Channel"):
        assert cat_of(n) == "国际新闻", f"{n} 应归国际新闻，实际 {cat_of(n)}"
        st = Stream(url="u", name=n, source="src")
        # 不传 modes，让全局 filter.mode=include 生效
        assert matches_filter(st, cfg) is True, f"{n} 应通过筛选"

    # 以前被误收的，现在既不该归类到国际新闻，也不该通过筛选
    for n in ("BBC Earth", "BBC Drama", "BBC One", "BBC Alba", "BBC Scotland",
              "BBC News Africa", "BBC News Hindi", "BBC Arabic", "BBC Persian",
              "CBBC", "CNBC Awaaz", "CNBC Arabiya", "CNN TURK", "CNN Prima News",
              "DW Arabic", "DW Russian", "Sky News Arabia", "Sky News Extra 1",
              "Al Jazeera Mubasher", "Al Jazeera 2", "Euronews Greek",
              "France 24 Arabic", "Arirang Radio", "Bloomberg TV Mongolia",
              "CNA Originals", "Fox News Radio", "CBS News Miami",
              "NHK World Premium", "SABC News"):
        assert cat_of(n) != "国际新闻", f"{n} 不该归到国际新闻"
        st = Stream(url="u", name=n, source="src")
        assert matches_filter(st, cfg) is False, f"{n} 不该通过筛选"


def test_hongkong_taiwan_keywords_not_too_broad():
    """jade / pearl / phoenix 这类宽泛词会误收无关频道。

    实例：Al Jadeed（黎巴嫩）、Golden Jade、98.1 Pearl FM（广播）、
    ABC 15 Phoenix AZ（美国凤凰城地方台）。
    真正的频道靠中文关键词和本地化名命中就够了。
    """
    cfg = load_config()

    def cat_of(name: str) -> str:
        st = Stream(url="u", name=name)
        st.key = canonical_key(name)
        st.display = display_name(name)
        return categorize(st, cfg.categories)

    # 真正的港澳台频道必须归对
    for n in ("翡翠台", "TVB Jade", "明珠台", "TVB Pearl",
              "Phoenix Hong Kong", "凤凰中文", "香港卫视", "纬来体育"):
        assert cat_of(n) == "港澳台", f"{n} 应归港澳台，实际 {cat_of(n)}"

    # 这些不该被误收
    for n in ("Al Jadeed", "Golden Jade", "98.1 Pearl FM",
              "ABC 15 Phoenix AZ (KNXV)"):
        assert cat_of(n) != "港澳台", f"{n} 不该归到港澳台"


def test_substring_keywords_do_not_cause_false_positives():
    """短关键词是子串匹配，很容易误伤。

    踩过的坑：
      - `tvb` 命中 FTV (Bolivia)（ftvbolivia）和 Red Bull TV BR（redbulltvbr）
      - `f1`  命中 TF1（法一）
      - `jade` 命中黎巴嫩的 Al Jadeed
    这些都不能再出现在关键词里。
    """
    cfg = load_config()
    flt = cfg.filter
    # 筛选关键词和分类关键词都要检查：曾经只删了 include_keywords 里的 tvb，
    # 分类表里还留着，结果 FTV (Bolivia) 被 sport 放行后又被 tvb 归到了港澳台。
    all_kw = [str(k).lower() for k in (flt.get("include_keywords") or [])]
    for cat in (cfg.categories or []):
        all_kw += [str(k).lower() for k in (cat.get("keywords") or [])]
    # 精确名单也不该出现这些短词
    all_kw += [str(x).lower() for cat in (cfg.categories or [])
               for x in (cat.get("exact") or [])]
    for bad in ("tvb", "f1", "jade", "pearl", "phoenix"):
        assert bad not in all_kw, f"关键词里不该有裸的 {bad}"

    # 这些必须被筛掉
    for n in ("FTV (Bolivia)", "Red Bull TV BR", "TF1", "Al Jadeed",
              "98.1 Pearl FM", "ABC 15 Phoenix AZ (KNXV)"):
        st = Stream(url="u", name=n)
        assert matches_filter(st, cfg) is False, f"{n} 不该通过筛选"

    # 而且就算它们从别的路径混进来（比如 group 里带 sport 被放行），
    # 分类也不能把它们归到港澳台，否则会被当成正经频道发布出去。
    def cat_of(name: str, group: str = "") -> str:
        st = Stream(url="u", name=name, group=group)
        st.key = canonical_key(name)
        st.display = display_name(name)
        return categorize(st, cfg.categories)

    assert cat_of("FTV (Bolivia)", "Sports") != "港澳台"
    assert cat_of("Red Bull TV BR", "Outdoor;Sports") != "港澳台"

    # 真正的 TVB 频道仍然要留下（靠本地化名 + 中文关键词）
    for n in ("TVB Jade", "TVB Pearl", "翡翠台", "明珠台"):
        st = Stream(url="u", name=n)
        assert matches_filter(st, cfg) is True, f"{n} 应该通过筛选"


def test_annotation_is_stripped_from_key():
    """上游标注不能进归一化键，否则同一个台会变成两个频道。

    实例：CNA (Singapore) [Geo-blocked] 的键曾是 cnasingaporegeoblocked，
    于是“CNA”和“CNA (Singapore)”在列表里各占一条。
    """
    # 标注本身不该进键
    assert clean_name("湖南卫视[Geo-blocked]") == "湖南卫视"
    assert canonical_key("CCTV-1 [Not 24/7]") == canonical_key("CCTV-1")

    # CNA 的两种写法靠配置里的 aliases 归并（normalize() 会读这个表）
    cfg = load_config()
    aliases = {str(k).lower(): str(v)
               for k, v in (cfg.normalize.get("aliases") or {}).items()}
    assert canonical_key("CNA", aliases) == canonical_key("CNA (Singapore)", aliases)
    assert canonical_key("CNA (Singapore)", aliases) == "cna"


def test_cgtn_documentary_variants():
    """「纪录」和「记录」两种写法要归并到同一个键。"""
    assert canonical_key("CGTN纪录") == canonical_key("CGTN记录")
    assert canonical_key("CGTN记录") == "cgtndocumentary"
    assert canonical_key("CGTN 记录") == "cgtndocumentary"
    assert canonical_key("CGTN English") == "cgtn"
    assert canonical_key("CGTN英语") == "cgtn"


def test_unknown_channel_falls_back_to_end_of_group():
    """认不出键的频道不能排到分组最前面。

    「河北4K」的键被削成裸省名「河北」，兜底排序以前是 0.0，
    比 CCTV-1 的 10、北京卫视的 0 还小，于是排到了第一位。
    """
    cfg = load_config()

    def sort_of(name: str) -> float:
        st = Stream(url="u", name=name)
        st.key = canonical_key(name)
        st.display = display_name(name)
        return channel_sort(st)[0]

    hebei_tv = sort_of("河北卫视")
    hebei_4k = sort_of("河北4K")
    beijing = sort_of("北京卫视")
    unknown = sort_of("某个不认识的地方台")

    assert hebei_tv < hebei_4k <= hebei_tv + 1, (hebei_tv, hebei_4k)
    assert beijing < hebei_4k, (beijing, hebei_4k)
    assert unknown > hebei_4k, (unknown, hebei_4k)


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


def test_english_named_channels_survive_include_filter():
    """回归：英文名的中文频道不能在 include 模式下被误杀。

    iptv-org 用英文名（Beijing Satellite TV），而 include_keywords 写的是中文。
    曾经靠把这些源设成 filter: all 绕过去；后来所有源统一改成 include，
    结果 iptv-org-cn 的 122 条只剩 17 条 ——
    北京/湖南/东方/江苏/浙江/深圳卫视全部消失。
    正确做法是匹配前先本地化：Beijing Satellite TV → 北京卫视 → 命中「卫视」。

    这里的断言是「不变式」而不是「实现方式」：不管用什么手段，
    这些频道都必须能通过筛选。
    """
    cfg = load_config()
    modes = source_modes(cfg)

    for name in (
        "Beijing Satellite TV",
        "Hunan TV",
        "Dragon TV",
        "Jiangsu Satellite TV",
        "Zhejiang Satellite TV",
        "Shenzhen Satellite TV",
    ):
        st = Stream(url="u", name=name, source="iptv-org-cn")
        assert matches_filter(st, cfg, modes) is True, f"{name} 被误杀"

    # 不管有没有 per-source override，都不该被挡
    en = Stream(url="u", name="Beijing Satellite TV", source="iptv-org-cn")
    assert matches_filter(en, cfg, modes) is True
    assert matches_filter(en, cfg) is True

    # 白名单意图不能被破坏：真正的杂台仍要挡掉
    junk = Stream(url="u", name="Random Shopping Channel", source="iptv-org-cn")
    assert matches_filter(junk, cfg, modes) is False

    # exclude 规则任何模式下都生效
    bad = Stream(url="u", name="Test Channel 测试", source="iptv-org-cn")
    assert matches_filter(bad, cfg, modes) is False


def test_per_source_filter_override():
    """sources[].filter 覆盖全局 filter.mode 的机制。

    用合成配置而不是真实 config.yaml，这样用户改配置不会把这个测试弄挂。
    """

    class _Cfg:
        def __init__(self, filter_cfg, sources, categories=None):
            self.filter = filter_cfg
            self.sources = sources
            self.categories = categories or []

    cfg = _Cfg(
        filter_cfg={
            "mode": "include",
            "include_keywords": ["卫视"],
            "exclude_keywords": ["test"],
        },
        sources=[
            {"name": "src-all", "filter": "all"},
            {"name": "src-inc", "filter": "include"},
            {"name": "src-default"},
        ],
    )
    modes = source_modes(cfg)
    assert modes.get("src-all") == "all"
    assert modes.get("src-inc") == "include"
    assert "src-default" not in modes      # 没写 filter 的不进表

    # 声明 all 的源：不受 include_keywords 限制
    other = Stream(url="u", name="Some Unlisted Channel", source="src-all")
    assert matches_filter(other, cfg, modes) is True
    # 同一个频道，来自声明 include 的源时被挡掉
    assert matches_filter(
        Stream(url="u", name="Some Unlisted Channel", source="src-inc"), cfg, modes
    ) is False
    # 没写 filter 的源走全局 mode=include
    assert matches_filter(
        Stream(url="u", name="Some Unlisted Channel", source="src-default"), cfg, modes
    ) is False

    # exclude 在任何模式下都生效
    assert matches_filter(
        Stream(url="u", name="Test Channel", source="src-all"), cfg, modes
    ) is False


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


def test_current_config_excludes_the_reported_bad_entries():
    """锁住两处人工排除（都是用户实测反馈的）：

    1. 「黑龙江卫视」的 0143_1 实际播的是辽宁卫视 —— 按 URL 路径排掉。
       注意**不能**顺手把同频道另一路也排掉，否则黑龙江卫视会整个消失。
    2. 河北4K 用户不要，但不能误伤河北卫视。
    """
    cfg = load_config()
    modes = source_modes(cfg)

    wrong = Stream(
        url="http://36.136.38.87:9901/tsfile/live/0143_1.m3u8?key=txiptv&playlive=1",
        name="黑龙江卫视",
    )
    assert not matches_filter(wrong, cfg, modes)

    keep = Stream(
        url="http://120.198.95.220:9901/tsfile/live/1049_1.m3u8?key=txiptv&playlive=1",
        name="黑龙江卫视",
    )
    assert matches_filter(keep, cfg, modes), "同频道剩下的线路要保住"

    assert not matches_filter(Stream(url="u", name="河北4K"), cfg, modes)
    assert matches_filter(Stream(url="u2", name="河北卫视"), cfg, modes)


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


def test_cctv_paid_channels_by_chinese_name_sorted_last():
    """回归：中文名的央视付费频道曾跑到 CCTV-1 前面。

    vbskycn 这类源给的是纯中文名（兵器科技 / 风云剧场 / CCTV怀旧剧场），
    canonical_key 认不出来就退化成裸键，channel_sort 的兜底分支是
    (0.0, display)，比 CCTV-1 的 10 还小 —— 于是这两个频道排到了最前面。
    """
    assert canonical_key("兵器科技") == "cctvweapon&technology"
    assert canonical_key("风云剧场") == "cctvstormtheater"
    assert canonical_key("央视台球") == "cctvbilliards"
    assert canonical_key("CCTV怀旧剧场") == "cctvnostalgiatheater"

    # 同一个台的中英文写法要归并成同一频道（否则列表里会出现两条怀旧剧场）
    assert canonical_key("央视怀旧剧场") == canonical_key("CCTV怀旧剧场")
    assert canonical_key("CCTV-怀旧剧场") == canonical_key("央视怀旧剧场")
    assert canonical_key("央视怀旧剧场") == canonical_key("CCTV-Nostalgia Theater")

    cfg = load_config()
    streams = [Stream(url=f"u{i}", name=n) for i, n in enumerate(
        ["兵器科技", "风云剧场", "CCTV怀旧剧场", "CCTV-1", "CCTV-17"]
    )]
    normalize(streams, cfg)
    ordered = [s.display for s in sorted(streams, key=channel_sort)]

    assert ordered[0] == "CCTV-1 综合", ordered
    assert ordered[1] == "CCTV-17 农业农村", ordered
    assert ordered.index("央视兵器科技") > ordered.index("CCTV-17 农业农村")
    assert ordered.index("央视风云剧场") > ordered.index("CCTV-17 农业农村")
    assert ordered.index("央视怀旧剧场") > ordered.index("CCTV-17 农业农村")
    # 怀旧剧场只应出现一次
    assert ordered.count("央视怀旧剧场") == 1, ordered


def test_cgtn_languages_stay_separate():
    """回归：CGTN 各语种台曾被并成一个频道。

    canonical_key 里是 re.search(r"(cgtn)([a-z]*)", low)，中文后缀不在 [a-z] 里，
    于是 CGTN法语 / 西语 / 阿语 / 纪录 全部退化成无后缀的 "cgtn"，
    六个语种台被并成一个，电视上统一显示「CGTN法语」但播的可能是英语。
    """
    pairs = [
        ("CGTN", "cgtn"),
        ("CGTN法语", "cgtnfrench"),
        ("CGTN French", "cgtnfrench"),
        ("CGTN西语", "cgtnspanish"),
        ("CGTN Spanish", "cgtnspanish"),
        ("CGTN阿语", "cgtnarabic"),
        ("CGTN Arabic", "cgtnarabic"),
        ("CGTN俄语", "cgtnrussian"),
        ("CGTN纪录", "cgtndocumentary"),
    ]
    for name, want in pairs:
        assert canonical_key(name) == want, f"{name} -> {canonical_key(name)}"

    names = ["CGTN", "CGTN法语", "CGTN西语", "CGTN阿语", "CGTN俄语", "CGTN纪录"]
    keys = {canonical_key(n) for n in names}
    assert len(keys) == len(names), f"语种台被并在一起了: {keys}"

    # 显示名要能区分语种，不能全是「CGTN法语」
    cfg = load_config()
    streams = [Stream(url=f"u{i}", name=n) for i, n in enumerate(names)]
    normalize(streams, cfg)
    displays = {s.display for s in streams}
    assert len(displays) == len(names), displays
    assert "CGTN 英语" in displays and "CGTN 法语" in displays, displays


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

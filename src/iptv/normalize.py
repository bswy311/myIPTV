"""频道名归一化：把「CCTV-1 综合」「cctv1高清」「CCTV1」合并成同一频道。"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

from .models import Stream

# 分辨率标记。不能简单地写成 \d{3,4}，否则会误伤 TV1000 这类含数字的台名，
# 所以要求带 p/i 后缀，或者正好落在常见视频高度白名单里。
_RES_RE = (
    r"(?<![a-z0-9])"
    r"(?:\d{3,4}[pi]|2160|1440|1280|1080|960|900|854|720|640|576|540|480|406|404|400|360|288|240|180)"
    r"(?![a-z0-9])"
)

# 画质/线路等噪声后缀
_NOISE_RE = re.compile(
    r"(?:"
    r"超高清|高清|超清|标清|蓝光|流畅|极速|"
    r"线路\s*\d*|备用\s*\d*|镜像\s*\d*|主源|备源|测试源|"
    r"(?<![a-z])(?:uhd|fhd|hd|sd|4k|8k|2k)(?![a-z])|"
    r"[（(\[【]?\s*" + _RES_RE + r"\s*[)）\]】]?|"
    r"\(backup\)"
    r")",
    re.IGNORECASE,
)

# 标点与空白
_PUNCT_RE = re.compile(r"[\s\-_—–·・.,，、|/\\\[\]【】()（）<>《》!！?？:：;；'\"*#]+")

# 地方卫视：必须“卫视”结尾，「凤凰卫视中文台」这种子频道不能被误并
_SAT_RE = re.compile(r"^([\u4e00-\u9fa5]{2,4})卫视$")

# 中文数字（央视一套 / 中央五台）
_CN_NUM = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
    "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12,
    "十三": 13, "十四": 14, "十五": 15, "十六": 16, "十七": 17,
}

# ---------------------------------------------------------------
# 英文频道名本地化
# ---------------------------------------------------------------
# iptv-org 等英文列表用的是 "Beijing Satellite TV" 这类名字，直接显示对中文用户
# 不友好，而且跟另一个源里的 "北京卫视" 无法归并成同一频道的备用线路。
_PROVINCE_EN = {
    "beijing": "北京", "shanghai": "上海", "tianjin": "天津", "chongqing": "重庆",
    "hebei": "河北", "shanxi": "山西", "liaoning": "辽宁", "jilin": "吉林",
    "heilongjiang": "黑龙江", "jiangsu": "江苏", "zhejiang": "浙江", "anhui": "安徽",
    "fujian": "福建", "jiangxi": "江西", "shandong": "山东", "henan": "河南",
    "hubei": "湖北", "hunan": "湖南", "guangdong": "广东", "guangxi": "广西",
    "hainan": "海南", "sichuan": "四川", "guizhou": "贵州", "yunnan": "云南",
    "xizang": "西藏", "tibet": "西藏", "shaanxi": "陕西", "gansu": "甘肃",
    "qinghai": "青海", "ningxia": "宁夏", "xinjiang": "新疆",
    "neimonggol": "内蒙古", "innermongolia": "内蒙古", "neimenggu": "内蒙古",
    "shenzhen": "深圳", "xiamen": "厦门", "yanbian": "延边", "bingtuan": "兵团",
    "southern": "南方",
}

# 不能靠规则推导的、需要硬编码的别名（键：去掉非字母数字后的全小写名）
_EN2ZH_EXACT = {
    "dragontv": "东方卫视",
    "dragontvinternational": "东方卫视国际",
    "goldeneaglecartoon": "金鹰卡通",
    "youmancartoonchannel": "优漫卡通",
    "phoenixchinesechannel": "凤凰卫视中文台",
    "phoenixinfonews": "凤凰卫视资讯台",
    "phoenixhongkong": "凤凰卫视香港台",
    "phoenixhk": "凤凰卫视香港台",
    "tvbjade": "翡翠台",
    "tvbpearl": "明珠台",
    "tvbnews": "无线新闻台",
    "tvbfinance": "无线财经台",
    "jade": "翡翠台",
    "pearl": "明珠台",
    "cctvplus1": "CCTV+1",
    "cctvplus2": "CCTV+2",
    "chinacentraltelevision": "央视",
    "chinaglobaltelevisionnetwork": "CGTN",
}

# 形如 XxxSatelliteTV / XxxSatelliteChannel / XxxTV 的英文名
_EN_SAT_RE = re.compile(
    r"^(?P<region>[a-z]+?)(?:satellitetv|satellitetvhd|satellitechannel|satellite)$"
)
_EN_TV_RE = re.compile(r"^(?P<region>[a-z]+?)(?:tv|television)$")


def _en_to_zh(name: str) -> str | None:
    """把 iptv-org 风格的英文频道名转成中文。识别不了就返回 None。"""
    low = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    if not low:
        return None
    if low in _EN2ZH_EXACT:
        return _EN2ZH_EXACT[low] or None

    for pattern in (_EN_SAT_RE, _EN_TV_RE):
        m = pattern.match(low)
        if m:
            region = m.group("region")
            zh = _PROVINCE_EN.get(region)
            if zh:
                return f"{zh}卫视"
    return None


def clean_name(name: str) -> str:
    s = unicodedata.normalize("NFKC", name or "").strip()
    s = _NOISE_RE.sub("", s)
    s = _PUNCT_RE.sub("", s)
    return s.strip()


def canonical_key(name: str, aliases: dict[str, str] | None = None) -> str:
    """生成频道归一化键。同一频道的不同写法应得到相同结果。"""
    s = clean_name(name)
    if not s:
        return ""

    low = s.lower()

    # 央视：CCTV1 / CCTV-1 / CCTV5+ / 央视1台
    m = re.search(r"(?:cctv|央视|中央电视(?:台)?)\s*-?\s*(\d{1,2})(\+|plus|加)?", low)
    if m:
        num = int(m.group(1))
        plus = "+" if m.group(2) else ""
        return f"cctv{num}{plus}"

    # 央视中文数字：央视一套 / 中央五台
    m = re.search(r"(?:cctv|央视|中央电视(?:台)?)\s*-?\s*([一二三四五六七八九十]+)\s*(?:套|台|频道)?", s)
    if m and m.group(1) in _CN_NUM:
        return f"cctv{_CN_NUM[m.group(1)]}"

    # CGTN 系列
    m = re.search(r"(cgtn)([a-z]*)", low)
    if m:
        return f"cgtn{m.group(2)}"

    # 地方卫视：北京卫视 / 湖南卫视高清 → 北京卫视
    m = _SAT_RE.match(s)
    if m:
        return f"{m.group(1)}卫视"

    # 英文频道名（Beijing Satellite TV / Hunan TV）
    zh = _en_to_zh(low)
    if zh:
        return canonical_key(zh, aliases)

    # 其它已知别名（如 翡翠台 / TVB Jade / 凤凰中文台）
    if aliases:
        for alias, target in aliases.items():
            if alias and alias.lower() in low:
                return target

    return low


# 括号内（或括号前）的画质标记，如 CCTV-1 (720p)、湖南卫视【高清】
_BRACKET_NOISE_RE = re.compile(
    r"[（(\[【]\s*"
    r"(?:超高清|高清|超清|标清|蓝光|流畅|4k|8k|uhd|fhd|hd|sd|\d{3,4}[pi]?)"
    r"\s*[)）\]】]",
    re.IGNORECASE,
)

# 结尾的画质标记，如 “湖南卫视高清”、“CCTV-4K HD”
_TRAILING_NOISE_RE = re.compile(
    r"\s*(?:超高清|高清|超清|标清|蓝光|备用|主源|uhd|fhd|hd|sd)\s*$",
    re.IGNORECASE,
)


def display_name(raw: str) -> str:
    """生成适合电视界面显示的频道名。

    比 canonical_key 温和得多：只剔除括号内/结尾的画质标记，
    避免把 “CCTV-4K” 这种把画质写进名字的频道削成 “CCTV”。
    """
    s = unicodedata.normalize("NFKC", raw or "").strip()
    if not s:
        return raw or ""
    prev = None
    while prev != s:
        prev = s
        s = _BRACKET_NOISE_RE.sub("", s)
        s = _TRAILING_NOISE_RE.sub("", s)
        s = re.sub(r"[（(\[【]\s*[)）\]】]", "", s)
        s = re.sub(r"\s{2,}", " ", s).strip(" -–—·|,，")

    zh = _en_to_zh(s)
    if zh:
        return zh
    return s or (raw or "").strip()


def categorize(stream: Stream, categories: list) -> str:
    """按配置的 categories 顺序归类，命中第一条即返回。"""
    haystack = f"{stream.name} {stream.tvg_name} {stream.group} {stream.key}".lower()
    for cat in categories:
        name = cat.get("name") or ""
        for kw in cat.get("keywords") or []:
            if kw and str(kw).lower() in haystack:
                return name
    return categories[-1].get("name", "其他") if categories else "其他"


def source_modes(cfg) -> dict[str, str]:
    """收集每个采集源自己的筛选模式（sources[].filter）。

    iptv-org 的 countries/cn.m3u 本身就是中文频道范围，用中文关键词再去卡它
    只会把 Beijing Satellite TV 这类英文名误杀，所以这种源直接声明 filter: all。
    """
    modes: dict[str, str] = {}
    for src in cfg.sources or []:
        name = src.get("name") or ""
        mode = (src.get("filter") or "").strip().lower()
        if name and mode in ("all", "include"):
            modes[name] = mode
    return modes


def matches_filter(stream: Stream, cfg, modes: dict[str, str] | None = None) -> bool:
    """按 filter 配置判断是否保留该频道。"""
    flt = cfg.filter
    mode = (flt.get("mode") or "include").lower()
    if modes:
        override = modes.get(stream.source or "")
        if override:
            mode = override

    haystack = f"{stream.name} {stream.tvg_name} {stream.group}".lower()
    url_low = (stream.url or "").lower()

    for kw in flt.get("exclude_url_keywords") or []:
        if kw and str(kw).lower() in url_low:
            return False

    for kw in flt.get("exclude_keywords") or []:
        if kw and str(kw).lower() in haystack:
            return False

    if mode == "all":
        return True

    keywords = flt.get("include_keywords") or []
    if not keywords:
        return True
    return any(kw and str(kw).lower() in haystack for kw in keywords)


def _pick_display(names: Counter[str], key: str, overrides: dict[str, str]) -> str:
    """从同一频道的多个原始名里挑一个最规范的，再清洗成显示名。"""
    if key in overrides:
        return overrides[key]
    if not names:
        return key

    # 优先：本身就不带画质标记的 > 出现次数多的 > 名字短的
    ranked = sorted(
        names.items(),
        key=lambda kv: (
            kv[0] != display_name(kv[0]),   # 需要清洗的排后面
            -kv[1],
            len(kv[0]),
        ),
    )
    raw = ranked[0][0] or key
    return display_name(raw)


def normalize(streams: list[Stream], cfg) -> list[Stream]:
    """就地填充 key / display / category，并返回同一列表。"""
    aliases = {str(k).lower(): str(v) for k, v in (cfg.normalize.get("aliases") or {}).items()}
    overrides = {str(k): str(v) for k, v in (cfg.normalize.get("display_overrides") or {}).items()}
    categories = cfg.categories or []

    name_pool: dict[str, Counter] = defaultdict(Counter)

    for st in streams:
        st.key = canonical_key(st.name or st.tvg_name, aliases)
        if not st.key:
            st.key = clean_name(st.url)[:40] or st.url[:40]
        name_pool[st.key][st.name or st.tvg_name or st.key] += 1

    for st in streams:
        st.display = _pick_display(name_pool.get(st.key, Counter()), st.key, overrides)
        st.category = categorize(st, categories)

    return streams


def dedupe(streams: list[Stream]) -> list[Stream]:
    """按 URL 去重，保留首次出现的（先来的源优先级更高）。"""
    seen: set[str] = set()
    out: list[Stream] = []
    for st in streams:
        u = (st.url or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(st)
    return out

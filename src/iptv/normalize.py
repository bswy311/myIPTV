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
    r"(?<![a-z])(?:hevc|h265|h264|avc|\d{2,3}\s*fps|\d{2,3}hz)(?![a-z])|"
    r"[（(\[【]?\s*" + _RES_RE + r"\s*[)）\]】]?|"
    r"\(backup\)"
    r")",
    re.IGNORECASE,
)

# iptv-org 会在频道名后面附标注，如 [Not 24/7]、[Geo-blocked]，显示时应去掉
_ANNOTATION_RE = re.compile(
    r"\s*[（(\[【]\s*(?:not\s*24/7|geo-?blocked|not\s*working|offline|"
    r"discontinued|replaced|behind\s*a\s*vpn)\s*[)）\]】]",
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

# ---------------------------------------------------------------
# 央视频道规范名
# ---------------------------------------------------------------
CCTV_NAMES = {
    "cctv1": "CCTV-1 综合", "cctv2": "CCTV-2 财经", "cctv3": "CCTV-3 综艺",
    "cctv4": "CCTV-4 中文国际", "cctv5": "CCTV-5 体育", "cctv5+": "CCTV-5+ 体育赛事",
    "cctv6": "CCTV-6 电影", "cctv7": "CCTV-7 国防军事", "cctv8": "CCTV-8 电视剧",
    "cctv9": "CCTV-9 纪录", "cctv10": "CCTV-10 科教", "cctv11": "CCTV-11 戏曲",
    "cctv12": "CCTV-12 社会与法", "cctv13": "CCTV-13 新闻",
    "cctv14": "CCTV-14 少儿", "cctv15": "CCTV-15 音乐",
    "cctv16": "CCTV-16 奥林匹克", "cctv17": "CCTV-17 农业农村",
    "cctv4k": "CCTV-4K 超高清", "cctv8k": "CCTV-8K 超高清",
    # 以下为央视付费频道（iptv-org 里是英文名，这里补上中文）
    "cctvbilliards": "央视台球",
    "cctvgolf&tennis": "央视高尔夫网球",
    "cctvstormfootball": "央视风云足球",
    "cctvstormmusic": "央视风云音乐",
    "cctvstormtheater": "央视风云剧场",
    "cctvthefirsttheater": "央视第一剧场",
    "cctvnostalgiatheater": "央视怀旧剧场",
    "cctvwomensfashion": "央视女性时尚",
    "cctvworldgeography": "央视世界地理",
    "cctvhealth": "央视卫生健康",
    "cctvcultureofquality": "央视文化精品",
    "cctvweapon&technology": "央视兵器科技",
    # CGTN 多语种台。每个语种必须有自己的键，否则会全被并成同一个频道，
    # 电视上显示「CGTN法语」但点开听到的是英语/西语/阿语。
    "cgtn": "CGTN 英语",
    "cgtnfrench": "CGTN 法语",
    "cgtnspanish": "CGTN 西语",
    "cgtnarabic": "CGTN 阿语",
    "cgtnrussian": "CGTN 俄语",
    "cgtndocumentary": "CGTN 纪录",
    "cgtnglobalbiz": "CGTN 财经",
}

# CGTN 后缀归一化：中英文写法都映射到同一个键，
# 这样 “CGTN法语” 和 “CGTN French” 能归并成同一频道的备用线路。
_CGTN_LANG = {
    "": "",
    "英": "", "英语": "", "english": "",
    "法": "french", "法语": "french", "french": "french",
    "francais": "french", "français": "french", "fran": "french",
    "西": "spanish", "西语": "spanish", "西班牙语": "spanish",
    "spanish": "spanish", "espanol": "spanish", "español": "spanish",
    "阿": "arabic", "阿语": "arabic", "阿拉伯语": "arabic", "arabic": "arabic",
    "俄": "russian", "俄语": "russian", "russian": "russian",
    "纪录": "documentary", "纪录片": "documentary", "记录": "documentary",
    "documentary": "documentary",
}

# 央视付费频道的中文名 → 规范键。
# vbskycn 等源直接给中文名（兵器科技 / 风云剧场 / CCTV怀旧剧场），
# 不做这层映射的话 canonical_key 会退化成裸键，channel_sort 认不出它是央视频道，
# 排序权重变 0.0——于是这两个频道跑到 CCTV-1 前面去了。
# 顺带把“央视怀旧剧场”和“CCTV怀旧剧场”这种同台异名归并成一个频道。
_CCTV_PAID_ZH = {
    "兵器科技": "cctvweapon&technology",
    "风云剧场": "cctvstormtheater",
    "风云音乐": "cctvstormmusic",
    "风云足球": "cctvstormfootball",
    "怀旧剧场": "cctvnostalgiatheater",
    "第一剧场": "cctvthefirsttheater",
    "文化精品": "cctvcultureofquality",
    "台球": "cctvbilliards",
    "高尔夫网球": "cctvgolf&tennis",
    "世界地理": "cctvworldgeography",
    "女性时尚": "cctvwomensfashion",
    "卫生健康": "cctvhealth",
}

# 卫视排序参考中国行政区划顺序；未列出的排到中间。
# 吉林紧跟在黑龙江之后，方便你一眼找到。
_PROVINCE_ORDER = [
    "北京", "天津", "河北", "山西", "内蒙古",
    "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东",
    "河南", "湖北", "湖南",
    "广东", "广西", "海南",
    "重庆", "四川", "贵州", "云南", "西藏",
    "陕西", "甘肃", "青海", "宁夏", "新疆",
    "深圳", "厦门", "延边", "三沙", "兵团", "东南", "东方",
    "南方", "海峡", "澳亚", "星空", "凤凰", "香港",
]
_PROVINCE_RANK = {name: i for i, name in enumerate(_PROVINCE_ORDER)}


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
    # 上游标注（[Not 24/7] / [Geo-blocked]）必须先去掉，
    # 否则它们会进到归一化键里——例如 “CNA (Singapore) [Geo-blocked]”
    # 会变成键 cnasingaporegeoblocked，跟“CNA”变成两个不同频道。
    s = _ANNOTATION_RE.sub("", s)
    s = _NOISE_RE.sub("", s)
    s = _PUNCT_RE.sub("", s)
    return s.strip()


def canonical_key(name: str, aliases: dict[str, str] | None = None) -> str:
    """生成频道归一化键。同一频道的不同写法应得到相同结果。"""
    raw = name or ""

    # 这两个必须在噪声清洗之前判，否则 CCTV-4K 会被削成 CCTV
    m = re.search(r"cctv\s*[-_]?\s*(4k|8k)", raw, re.IGNORECASE)
    if m:
        return f"cctv{m.group(1).lower()}"
    m = re.search(r"cctv\s*\+\s*(\d{1,2})", raw, re.IGNORECASE)
    if m:
        return f"cctvplus{m.group(1)}"

    s = clean_name(raw)
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

    # CGTN 系列（英语主台 / 法语 / 西语 / 阿语 / 俄语 / 纪录）
    # 后缀可能是中文或带重音的拉丁字母，不能只用 [a-z]*——否则 “CGTN法语”
    # “CGTN Français” 会退化成不同的键（前者变 cgtn、后者变 cgtnfran），
    # 同一个语种台会在列表里出现两次。
    m = re.search(r"cgtn\s*([a-z\u00c0-\u00ff\u4e00-\u9fa5]*)", low)
    if m:
        suffix = m.group(1) or ""
        return "cgtn" + _CGTN_LANG.get(suffix, suffix)

    # 央视付费频道的中文名（兵器科技 / 风云剧场 / 央视台球 / CCTV怀旧剧场…）
    bare = re.sub(r"^(?:cctv|央视)", "", low)
    if bare in _CCTV_PAID_ZH:
        return _CCTV_PAID_ZH[bare]

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
    r"\s*(?:超高清|高清|超清|标清|蓝光|备用|主源|uhd|fhd|hd|sd|hevc|h265|h264|avc|"
    r"\d{2,3}\s*fps|\d{2,3}\s*hz)\s*$",
    re.IGNORECASE,
)


def display_name(raw: str) -> str:
    """生成适合电视界面显示的频道名。

    比 canonical_key 温和得多：只剔除括号内/结尾的画质标记，
    避免把 “CCTV-4K” 这种把画质写进名字的频道削成 “CCTV”。
    """
    s = _ANNOTATION_RE.sub("", unicodedata.normalize("NFKC", raw or "").strip())
    if not s:
        return (raw or "").strip()
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


# ---------------------------------------------------------------
# tvg-id / 台标 / 排序
# ---------------------------------------------------------------
def epg_id(key: str) -> str:
    """把频道键转成 EPG 用的 tvg-id。

    目标是和 fanmingming 的 e.xml 对齐，它的 id 就两种形式：
      CCTV1 / CCTV5+ / CCTV4K   和   北京卫视、吉林卫视
    对不上 EPG 的频道返回空字符串。
    """
    m = re.fullmatch(r"cctv(\d{1,2})(\+)?", key or "")
    if m:
        return f"CCTV{m.group(1)}{'+' if m.group(2) else ''}"
    if re.fullmatch(r"cctv(?:4k|8k)", key or ""):
        return key.upper()
    if (key or "").endswith("卫视"):
        return key
    return ""


def resolve_logo(stream: Stream, cfg) -> str:
    """决定用哪个台标。

    源自带的台标优先，但如果是已知失效的图床（如 tv.haoqu99.com）
    就换成模板拼出来的。
    """
    template = cfg.output.get("logo_template") or ""
    skip = [str(d).lower() for d in (cfg.output.get("logo_skip_domains") or [])]
    logo = (stream.tvg_logo or "").strip()
    tid = stream.tvg_id or ""
    can_template = bool(template) and (tid.startswith("CCTV") or tid.endswith("卫视"))

    # 统一台标：同一频道混用 gitee / imgur / fanmingming 几套图源看着很乱，
    # 开启 logo_prefer_template 后，央视和卫视一律用同一个模板。
    if can_template and cfg.output.get("logo_prefer_template"):
        return template.replace("{id}", tid)

    is_bad = (not logo) or any(d in logo.lower() for d in skip)
    if is_bad and can_template:
        return template.replace("{id}", tid)
    return logo


def channel_sort(stream: Stream) -> tuple[float, str]:
    """分组内部的排序权重。

    否则会按字典序排成 CCTV-1, CCTV-10, CCTV-11 ... CCTV-2 这种很观的顺序。
    """
    key = stream.key or ""
    m = re.fullmatch(r"cctv(\d{1,2})(\+)?", key)
    if m:
        return (int(m.group(1)) * 10 + (4 if m.group(2) else 0), "")
    m = re.fullmatch(r"cctv(\d)k", key)
    if m:
        return (180 + int(m.group(1)), "")
    if key.startswith("cctvplus"):
        return (950, key)
    if key.startswith("cgtn"):
        return (960, key)
    # 无编号的央视频道（付费频道）：排到 CCTV-17 之后，但别排到 CCTV-1 前面
    if key.startswith("cctv"):
        return (500, key)
    if key.endswith("卫视"):
        return (float(_PROVINCE_RANK.get(key[:-2], 500)), key)
    # 形如「河北4K」的频道：4K 被当噪声去掉了，键剩个裸省名“河北”，
    # 上面所有分支都不命中，会掉到兜底。把它排到对应省卫视的紧后面。
    if key in _PROVINCE_RANK:
        return (float(_PROVINCE_RANK[key]) + 0.5, key)
    # 兜底：未知频道排在已知之后。以前这里是 0.0，结果「兵器科技」「河北4K」
    # 这种认不出键的频道反而排到了 CCTV-1 / 北京卫视前面。
    return (900.0, stream.display or key)


def _exact_norm(name: str) -> str:
    """「精确名单」比对用的规范化名。

    本地化 → 去掉画质标注 → 只留字母数字与汉字 → 小写。
    这样 "CNA (Singapore)" 与 "cna singapore" 能对上，
    而 "BBC News Africa" 不会因为包含 "BBC News" 就被误判成同一台。
    """
    s = display_name(name or "").lower()
    s = re.sub(r"[^a-z0-9\u4e00-\u9fa5]+", " ", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def exact_index(cfg) -> set[str]:
    """收集所有分类 `exact:` 精确名单里的频道名（规范化后）。"""
    out: set[str] = set()
    for cat in (cfg.categories or []):
        for item in (cat.get("exact") or []):
            k = _exact_norm(str(item))
            if k:
                out.add(k)
    return out


def _exact_hit(stream: Stream, names: set[str]) -> bool:
    """流的名字是否命中精确名单。"""
    if not names:
        return False
    for cand in (stream.name, stream.tvg_name, stream.display):
        if cand and _exact_norm(cand) in names:
            return True
    return False


def categorize(stream: Stream, categories: list) -> str:
    """按配置的 categories 顺序归类。

    判定分两轮：
      1. 先看各分类的 `exact:` 精确名单。这种需求（「只要这几个台」）
         靠通配关键词是做不干净的——比如用 "bbc" 会把 BBC Earth / BBC 戏剧
         一并捞进来。精确名单用规范化后的完整名比对，可控得多。
      2. 再按 `keywords:` 模糊匹配，命中第一条即返回。

    haystack 里加了 display（本地化名），这样 "Phoenix Hong Kong" 能被
    「凤凰」命中，不必再写宽泛的 "phoenix"（那个会把美国凤凰城的地方台也捞进来）。
    """
    for cat in categories or []:
        exact = {_exact_norm(str(x)) for x in (cat.get("exact") or []) if str(x).strip()}
        if exact and _exact_hit(stream, exact):
            return cat.get("name") or ""

    haystack = (
        f"{stream.name} {stream.tvg_name} {stream.group} "
        f"{stream.key} {stream.display}"
    ).lower()
    for cat in categories or []:
        name = cat.get("name") or ""
        for kw in cat.get("keywords") or []:
            if kw and str(kw).lower() in haystack:
                return name
    return categories[-1].get("name", "其他") if categories else "其他"


def source_modes(cfg) -> dict[str, str]:
    """收集每个采集源自己的筛选模式（sources[].filter）。

    备注：iptv-org 的 countries/cn.m3u 用的是英文名（Beijing Satellite TV），
    按中文关键词去卡会把它们全部误杀。这一点现在靠 matches_filter 里
    「先本地化再匹配」解决（Beijing Satellite TV → 北京卫视 → 命中「卫视」），
    所以不再需要把它设成 filter: all。
    """
    modes: dict[str, str] = {}
    for src in cfg.sources or []:
        name = src.get("name") or ""
        mode = (src.get("filter") or "").strip().lower()
        if name and mode in ("all", "include"):
            modes[name] = mode
    return modes


def _is_noise_local(stream: Stream, cfg) -> bool:
    """判断是否为需要丢弃的外省地方台。

    有些源用 group-title="浙江台"/"吉林台" 这种形式组织地方台，里面混了
    大量县级台。对吉林用户来说「浙江上虞新闻综合频道」只是噪声。
    返回 True 表示应当丢弃。
    """
    flt = cfg.filter
    if not flt.get("local_filter_enabled", False):
        return False

    suffix = str(flt.get("local_group_suffix") or "台")
    group = (stream.group or "").strip()
    if not group or not group.endswith(suffix):
        return False

    exempt = [str(x) for x in (flt.get("local_group_exempt") or [])]
    if any(e and e in group for e in exempt):
        return False

    keep = [str(x) for x in (flt.get("local_keep") or [])]
    return not any(k and k in group for k in keep)


def matches_filter(stream: Stream, cfg, modes: dict[str, str] | None = None) -> bool:
    """按 filter 配置判断是否保留该频道。

    匹配前会先把频道的**本地化名**一并放进候选文本。这一步很关键：
    iptv-org 之类源里卫视的叫法是英文（Beijing Satellite TV / Hunan TV /
    Dragon TV / Jiangsu Satellite TV），而 include_keywords 写的是中文「卫视」。
    不做本地化的话，只要这些源声明 filter: include，
    **北京/湖南/东方/江苏/浙江/深圳卫视会被整个筛掉**——实测 122 条里只剩 17 条。
    本地化后 "Beijing Satellite TV" → "北京卫视"，命中「卫视」，行为才符合直觉。
    """
    flt = cfg.filter
    mode = (flt.get("mode") or "include").lower()
    if modes:
        override = modes.get(stream.source or "")
        if override:
            mode = override

    parts = [stream.name or "", stream.tvg_name or "", stream.group or ""]
    localized = display_name(stream.name or "")
    if localized and localized != stream.name:
        parts.append(localized)
    haystack = " ".join(parts).lower()
    url_low = (stream.url or "").lower()

    for kw in flt.get("exclude_url_keywords") or []:
        if kw and str(kw).lower() in url_low:
            return False

    for kw in flt.get("exclude_keywords") or []:
        if kw and str(kw).lower() in haystack:
            return False

    if _is_noise_local(stream, cfg):
        return False

    if mode == "all":
        return True

    # 分类里 `exact:` 精确名单上的频道一律保留。
    # 这些通常是「只想要这几个台」的重点频道，不该因为通配关键词没覆盖到而被筛掉。
    if _exact_hit(stream, exact_index(cfg)):
        return True

    keywords = flt.get("include_keywords") or []
    if not keywords:
        return True
    return any(kw and str(kw).lower() in haystack for kw in keywords)


def _pick_display(names: Counter[str], key: str, overrides: dict[str, str]) -> str:
    """从同一频道的多个原始名里挑一个最规范的，再清洗成显示名。"""
    if key in overrides:
        return overrides[key]
    if key in CCTV_NAMES:
        return CCTV_NAMES[key]
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
        # tvg-id 统一由自己生成，保证和 EPG 对得上；对不上的回退到显示名
        st.tvg_id = epg_id(st.key) or st.display
        st.tvg_logo = resolve_logo(st, cfg)

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

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any


@dataclass
class Stream:
    """一条直播流（一个频道可能有多条流作为备用线路）。"""

    url: str = ""
    name: str = ""              # 原始频道名（来自 #EXTINF 逗号后的部分）
    source: str = ""            # 来源列表标识
    tvg_id: str = ""
    tvg_name: str = ""
    tvg_logo: str = ""
    group: str = ""             # 原始 group-title
    referrer: str = ""          # #EXTVLCOPT:http-referrer
    user_agent: str = ""        # #EXTVLCOPT:http-user-agent

    # ---- 归一化结果 ----
    key: str = ""               # 频道归一化键，用于聚合同一频道的多条流
    display: str = ""           # 最终显示名
    category: str = ""          # 归类后的分组（央视/卫视/体育/...）

    # ---- 探测结果 ----
    ok: bool = False
    kind: str = ""              # hls / ts / mp4 / flv / dash / audio / other
    status: int = 0
    latency_ms: float = 0.0
    resolution: str = ""
    height: int = 0             # 分辨率高度，用于评分
    bandwidth: int = 0          # 清单里声明的码率（bps）
    error: str = ""
    checked_at: str = ""

    # ---- 带宽实测（决定会不会卡）----
    bitrate_kbps: float = 0.0   # 视频实际码率
    speed_kbps: float = 0.0     # 实测下载速度
    stability: float = 0.0      # 0~100，分片拉取成功率
    headroom: float = 0.0       # speed / bitrate，越大越不容易卡

    # ---- 音轨体检（TS 流才有；没有数据时为 0）----
    audio_kbps: float = 0.0     # 估算的音轨码率，正常 64~256，残缺的只有二十几
    audio_codec: str = ""       # aac / mp2 / ac3 ...
    audio_share: float = 0.0    # 音轨包占比（0~1）
    audio_bad: bool = False     # 音轨残缺（听着是噪音），发布时排到最后

    # ---- 评分 ----
    score: float = 0.0
    fail_streak: int = 0        # 历史连续失败次数
    ok_count: int = 0
    skipped: bool = False       # 因拉黑而跳过探测

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Stream":
        allowed = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in allowed})


@dataclass
class ProbeResult:
    ok: bool = False
    kind: str = "other"
    status: int = 0
    latency_ms: float = 0.0
    resolution: str = ""
    bandwidth: int = 0
    error: str = ""
    bitrate_kbps: float = 0.0
    speed_kbps: float = 0.0
    stability: float = 0.0
    audio_kbps: float = 0.0
    audio_codec: str = ""
    audio_share: float = 0.0
    audio_bad: bool = False

    @property
    def height(self) -> int:
        if not self.resolution or "x" not in self.resolution:
            return 0
        try:
            return int(self.resolution.split("x", 1)[1])
        except (ValueError, IndexError):
            return 0

    @property
    def headroom(self) -> float:
        if self.bitrate_kbps <= 0:
            return 0.0
        return self.speed_kbps / self.bitrate_kbps


@dataclass
class SourceStat:
    name: str = ""
    url: str = ""
    fetched: int = 0
    parsed: int = 0
    error: str = ""


@dataclass
class RunStats:
    started_at: str = ""
    finished_at: str = ""
    elapsed_sec: float = 0.0
    sources: list[SourceStat] = field(default_factory=list)
    total_parsed: int = 0
    after_filter: int = 0
    after_dedup: int = 0
    probed: int = 0
    skipped_blacklist: int = 0
    alive: int = 0
    dead: int = 0
    channels: int = 0
    published_channels: int = 0
    published_streams: int = 0
    kind_breakdown: dict[str, int] = field(default_factory=dict)

    @property
    def alive_rate(self) -> float:
        return (self.alive / self.probed * 100) if self.probed else 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["alive_rate"] = round(self.alive_rate, 2)
        return d

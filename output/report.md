# IPTV 直播源检测报告

- 运行时间：2026-10-15T17:06:38+00:00 → 2026-10-15T17:11:54+00:00（316.3 秒）
- 解析到流：**14929** 条
- 筛选后：6148 条，去重后：3737 条
- 实际探测：3708 条（拉黑跳过 832 条）
- 可用：**1151** 条（31.0%），失效：1725 条
- 频道数：185，发布：185 个频道 / 359 条线路

## 流类型分布

- `hls`：1106
- `mp4`：27
- `flv`：8
- `ts`：8
- `dash`：2

## 带宽实测概览

- 平均下载速度：**15.2 Mbps**（最低 0.8，最高 173.8）
- 平均视频码率：**2.5 Mbps**
- 带宽余量 ≥2x（基本不会卡）：**241/303** 条（占 80%）

> 余量 = 实测速度 ÷ 视频码率。余量 <1 必定卡；1~2 勉强；>2 流畅。

## 分组统计

| 分组 | 可用线路 | 频道数 |
|---|---|---|
| 央视 | 738 | 55 |
| 卫视 | 243 | 27 |
| 吉林 | 7 | 6 |
| 长春 | 1 | 1 |
| 港澳台 | 98 | 50 |
| 国际新闻 | 35 | 20 |
| 其他 | 29 | 26 |

## 采集源

| 源 | 条数 | 状态 |
|---|---|---|
| local-extra | 1 | 正常 |
| bestfan-cctv | 73 | 正常 |
| bestfan-province | 104 | 正常 |
| bestfan-all | 186 | 正常 |
| bestfan-all-direct | 186 | 正常 |
| vbskycn-ipv4 | 537 | 正常 |
| vbskycn-ipv4-gh | 537 | 正常 |
| chinaiptv-cntv | 405 | 正常 |
| iptv-org-sports | 465 | 正常 |
| iptv-org-cn | 147 | 正常 |
| iptv-org-hk | 18 | 正常 |
| iptv-org-tw | 28 | 正常 |
| iptv-org-zho | 216 | 正常 |
| iptv-org-news | 1017 | 正常 |
| suxuang-iptv | 1225 | 正常 |
| suxuang-iptv-gh | 1225 | 正常 |
| gh:myIPTV | 1052 | 正常 |
| gh:myIPTV | 350 | 正常 |
| gh:iptv | 676 | 正常 |
| gh:iptv | 676 | 正常 |
| gh:iptv | 0 | 失败：HTTPStatusError: Client error '404 Not Found' for url 'https://raw.githubusercontent.com/app-bot-server/iptv/main/lista.m3u8'
For more information check: https://developer.mozilla.org/en-US/docs/Web/H |
| gh:iptv-bridge | 637 | 正常 |
| gh:m3u-autoupdate | 2748 | 正常 |
| gh:iptv | 221 | 正常 |
| gh:m3u-autoupdate | 5 | 正常 |
| gh:IPTV-M3U-TOOL | 75 | 正常 |
| gh:iptv | 1942 | 正常 |
| gh:Xixi-iptv | 38 | 正常 |
| gh:Xixi-iptv | 20 | 正常 |
| gh:iptv | 109 | 正常 |
| gh:Xixi-iptv | 10 | 正常 |

## 带宽实测（决定会不会卡）

| 频道 | 分辨率 | 音轨 | 码率 | 实测速度 | 余量 | 稳定性 | 评分 |
|---|---|---|---|---|---|---|---|
| Bloomberg tv+ 🇺🇸 | 3840x2160 | aac 344k | 10.0M | 98.3M | 9.8x | 100% | 2413 |
| CNN International | 1920x1080 | aac | 8.9M | 120.5M | 13.5x | 100% | 2372 |
| CNA | 1920x1080 | aac | 8.0M | 128.4M | 16.1x | 100% | 2368 |
| NHK World-Japan | 1920x1080 | - | 7.0M | 133.5M | 19.1x | 100% | 2356 |
| Al Jazeera English | 1920x1080 | aac | 6.1M | 109.2M | 17.8x | 100% | 2332 |
| NBC News Now | 1920x1080 | aac | 5.3M | 152.0M | 28.9x | 100% | 2321 |
| NBC News Now | 1920x1080 | aac | 5.3M | 39.7M | 7.5x | 100% | 2319 |
| NBC News Now 🇺🇸 | 1920x1080 | aac | 5.3M | 37.8M | 7.2x | 100% | 2318 |
| 无线新闻 | 1920x1080 | aac | 5.0M | 61.0M | 12.2x | 100% | 2318 |
| 凤凰卫视台 | 1920x1080 | aac | 5.0M | 44.7M | 8.9x | 100% | 2318 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 43.9M | 8.8x | 100% | 2318 |
| 凤凰资讯台 | 1920x1080 | aac | 5.0M | 55.3M | 11.1x | 100% | 2317 |
| 翡翠台 | 1920x1080 | - | 5.0M | 30.9M | 6.2x | 100% | 2317 |
| 明珠台 | 1920x1080 | - | 5.0M | 35.3M | 7.1x | 100% | 2316 |
| [MLB] Milwaukee Brewers at Los Angeles Dodgers (SPRTSPASS) | 1920x1080 | aac | 8.6M | 77.3M | 9.0x | 100% | 2311 |
| CNN 🇺🇸 | 1920x1080 | aac | 4.7M | 37.5M | 8.0x | 100% | 2308 |
| Reuters TV | 1920x1080 | aac | 4.7M | 42.4M | 9.0x | 100% | 2307 |
| CNBC UK | 1920x1080 | aac | 4.7M | 150.4M | 31.9x | 100% | 2306 |
| CGTN 财经 | 1920x1080 | aac | 4.7M | 42.2M | 9.0x | 100% | 2303 |
| CGTN News 🇬🇧 | 1920x1080 | aac | 4.5M | 137.7M | 30.3x | 100% | 2298 |
| CGTN 西语 | 1920x1080 | aac 54k | 4.0M | 150.0M | 37.5x | 100% | 2296 |
| DW English | 1920x1080 | aac | 5.1M | 29.1M | 5.8x | 100% | 2292 |
| 华丽翡翠台 | 1920x1080 | aac 113k | 3.6M | 65.5M | 18.3x | 100% | 2289 |
| 明珠台 | 1920x1080 | - | 5.0M | 32.3M | 6.5x | 100% | 2288 |
| NBC News Now | 1920x1080 | aac | 5.3M | 48.0M | 9.1x | 100% | 2281 |
| ViuTV | 1920x1080 | - | 4.6M | 33.4M | 7.3x | 100% | 2280 |
| 明珠台 | 1920x1080 | aac 806k | 4.3M | 44.9M | 10.6x | 100% | 2275 |
| Arirang TV | 1920x1080 | aac 350k | 3.3M | 74.8M | 23.0x | 100% | 2273 |
| 澳视澳门 | 1920x1080 | aac 387k | 3.0M | 48.5M | 16.2x | 100% | 2268 |
| CNN International | 1920x1080 | aac | 8.9M | 42.8M | 4.8x | 100% | 2264 |

> 音轨码率低于音轨阈值会标 ⚠ 并被降权：这种源视频很好但声音是噪音。

> 由 iptv-pipeline 自动生成 2026-10-15T17:11:54+00:00

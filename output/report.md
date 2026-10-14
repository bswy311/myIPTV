# IPTV 直播源检测报告

- 运行时间：2026-10-14T17:17:51+00:00 → 2026-10-14T17:21:44+00:00（233.5 秒）
- 解析到流：**11902** 条
- 筛选后：3804 条，去重后：1996 条
- 实际探测：1967 条（拉黑跳过 1208 条）
- 可用：**658** 条（33.5%），失效：101 条
- 频道数：188，发布：188 个频道 / 352 条线路

## 流类型分布

- `hls`：622
- `mp4`：25
- `ts`：6
- `flv`：3
- `dash`：2

## 带宽实测概览

- 平均下载速度：**29.4 Mbps**（最低 0.8，最高 374.1）
- 平均视频码率：**3.4 Mbps**
- 带宽余量 ≥2x（基本不会卡）：**107/143** 条（占 75%）

> 余量 = 实测速度 ÷ 视频码率。余量 <1 必定卡；1~2 勉强；>2 流畅。

## 分组统计

| 分组 | 可用线路 | 频道数 |
|---|---|---|
| 央视 | 224 | 39 |
| 卫视 | 285 | 43 |
| 吉林 | 7 | 6 |
| 长春 | 1 | 1 |
| 港澳台 | 75 | 48 |
| 国际新闻 | 33 | 20 |
| 其他 | 33 | 31 |

## 采集源

| 源 | 条数 | 状态 |
|---|---|---|
| local-extra | 1 | 正常 |
| bestfan-cctv | 73 | 正常 |
| bestfan-province | 128 | 正常 |
| bestfan-all | 212 | 正常 |
| bestfan-all-direct | 212 | 正常 |
| vbskycn-ipv4 | 494 | 正常 |
| vbskycn-ipv4-gh | 0 | 失败：HTTPStatusError: Client error '403 Forbidden' for url 'https://gh-proxy.com/raw.githubusercontent.com/vbskycn/iptv/refs/heads/master/tv/iptv4.m3u'
For more information check: https://developer.mozilla |
| chinaiptv-cntv | 405 | 正常 |
| iptv-org-sports | 459 | 正常 |
| iptv-org-cn | 147 | 正常 |
| iptv-org-hk | 18 | 正常 |
| iptv-org-tw | 27 | 正常 |
| iptv-org-zho | 216 | 正常 |
| iptv-org-news | 1015 | 正常 |
| suxuang-iptv | 1225 | 正常 |
| suxuang-iptv-gh | 1225 | 正常 |
| gh:myIPTV | 605 | 正常 |
| gh:myIPTV | 347 | 正常 |
| gh:iptv | 619 | 正常 |
| gh:iptv | 619 | 正常 |
| gh:iptv | 0 | 失败：HTTPStatusError: Client error '404 Not Found' for url 'https://raw.githubusercontent.com/app-bot-server/iptv/main/lista.m3u8'
For more information check: https://developer.mozilla.org/en-US/docs/Web/H |
| gh:iptv-bridge | 636 | 正常 |
| gh:m3u-autoupdate | 2748 | 正常 |
| gh:iptv | 221 | 正常 |
| gh:m3u-autoupdate | 5 | 正常 |
| gh:IPTV-M3U-TOOL | 72 | 正常 |
| gh:Xixi-iptv | 36 | 正常 |
| gh:Xixi-iptv | 20 | 正常 |
| gh:iptv | 109 | 正常 |
| gh:Xixi-iptv | 8 | 正常 |

## 带宽实测（决定会不会卡）

| 频道 | 分辨率 | 音轨 | 码率 | 实测速度 | 余量 | 稳定性 | 评分 |
|---|---|---|---|---|---|---|---|
| Bloomberg tv+ 🇺🇸 | 3840x2160 | aac 287k | 10.0M | 74.2M | 7.4x | 100% | 2408 |
| 翡翠台 | 1920x1080 | mp2 212k | 8.0M | 47.6M | 6.0x | 100% | 2371 |
| CNN International | 1920x1080 | aac | 8.9M | 147.6M | 16.6x | 100% | 2360 |
| CNN International | 1920x1080 | aac | 8.9M | 168.9M | 18.9x | 100% | 2348 |
| NHK World-Japan | 1920x1080 | - | 7.0M | 351.2M | 50.2x | 100% | 2346 |
| Al Jazeera English | 1920x1080 | aac | 6.1M | 81.7M | 13.3x | 100% | 2330 |
| NBC News Now | 1920x1080 | aac | 5.3M | 374.1M | 71.2x | 100% | 2321 |
| NBC News Now 🇺🇸 | 1920x1080 | aac | 5.3M | 69.7M | 13.3x | 100% | 2320 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 126.3M | 25.2x | 100% | 2319 |
| 无线新闻 | 1920x1080 | aac 312k | 5.0M | 106.5M | 21.3x | 100% | 2319 |
| 凤凰资讯台 | 1920x1080 | aac 57k | 5.0M | 36.7M | 7.3x | 100% | 2319 |
| 翡翠台北美版 | 1920x1080 | aac 115k | 5.0M | 33.6M | 6.7x | 100% | 2318 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 43.8M | 8.8x | 100% | 2318 |
| NBC News Now | 1920x1080 | aac | 5.3M | 79.2M | 15.1x | 100% | 2318 |
| 明珠台 | 1920x1080 | - | 5.0M | 31.2M | 6.2x | 100% | 2317 |
| NBC News Now | 1920x1080 | aac | 5.3M | 60.7M | 11.6x | 100% | 2316 |
| 翡翠 | 1920x1080 | - | 5.0M | 81.6M | 16.3x | 100% | 2316 |
| ViuTV | 1920x1080 | - | 4.6M | 50.8M | 11.0x | 100% | 2311 |
| ViuTV | 1920x1080 | - | 4.6M | 31.2M | 6.8x | 100% | 2310 |
| CNBC UK | 1920x1080 | aac | 4.7M | 173.1M | 36.7x | 100% | 2310 |
| CNN 🇺🇸 | 1920x1080 | aac 47k | 4.7M | 48.8M | 10.4x | 100% | 2308 |
| ViuTV | 1920x1080 | - | 4.6M | 37.5M | 8.2x | 100% | 2308 |
| 凤凰中文 | 1920x1080 | aac | 5.0M | 35.7M | 7.1x | 100% | 2307 |
| 华丽翡翠台 | 1920x1080 | aac | 5.0M | 36.1M | 7.2x | 100% | 2306 |
| 翡翠台 | 1920x1080 | - | 5.0M | 90.8M | 18.2x | 100% | 2304 |
| 翡翠台 | 1920x1080 | aac 134k | 4.3M | 47.4M | 11.2x | 100% | 2304 |
| 翡翠 | 1920x1080 | aac 134k | 4.3M | 41.7M | 9.8x | 100% | 2302 |
| CGTN 财经 | 1920x1080 | aac | 4.7M | 40.1M | 8.6x | 100% | 2300 |
| CGTN News 🇬🇧 | 1920x1080 | aac 49k | 4.5M | 59.9M | 13.2x | 100% | 2300 |
| TVB翡翠台 | 1920x1080 | - | 5.0M | 31.0M | 6.2x | 100% | 2299 |

> 音轨码率低于音轨阈值会标 ⚠ 并被降权：这种源视频很好但声音是噪音。

> 由 iptv-pipeline 自动生成 2026-10-14T17:21:44+00:00

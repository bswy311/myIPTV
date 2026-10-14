# IPTV 直播源检测报告

- 运行时间：2026-10-14T21:45:51+00:00 → 2026-10-14T21:48:26+00:00（154.5 秒）
- 解析到流：**12190** 条
- 筛选后：3917 条，去重后：2186 条
- 实际探测：2157 条（拉黑跳过 1238 条）
- 可用：**727** 条（33.7%），失效：192 条
- 频道数：178，发布：178 个频道 / 345 条线路

## 流类型分布

- `hls`：689
- `mp4`：26
- `ts`：7
- `flv`：3
- `dash`：2

## 带宽实测概览

- 平均下载速度：**20.7 Mbps**（最低 0.8，最高 321.6）
- 平均视频码率：**3.0 Mbps**
- 带宽余量 ≥2x（基本不会卡）：**133/168** 条（占 79%）

> 余量 = 实测速度 ÷ 视频码率。余量 <1 必定卡；1~2 勉强；>2 流畅。

## 分组统计

| 分组 | 可用线路 | 频道数 |
|---|---|---|
| 央视 | 268 | 39 |
| 卫视 | 318 | 42 |
| 吉林 | 7 | 6 |
| 长春 | 1 | 1 |
| 港澳台 | 76 | 49 |
| 国际新闻 | 32 | 19 |
| 其他 | 25 | 22 |

## 采集源

| 源 | 条数 | 状态 |
|---|---|---|
| local-extra | 1 | 正常 |
| bestfan-cctv | 73 | 正常 |
| bestfan-province | 104 | 正常 |
| bestfan-all | 186 | 正常 |
| bestfan-all-direct | 186 | 正常 |
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
| gh:myIPTV | 658 | 正常 |
| gh:myIPTV | 352 | 正常 |
| gh:iptv | 649 | 正常 |
| gh:iptv | 649 | 正常 |
| gh:iptv | 0 | 失败：HTTPStatusError: Client error '404 Not Found' for url 'https://raw.githubusercontent.com/app-bot-server/iptv/main/lista.m3u8'
For more information check: https://developer.mozilla.org/en-US/docs/Web/H |
| gh:iptv-bridge | 636 | 正常 |
| gh:m3u-autoupdate | 2748 | 正常 |
| gh:iptv | 221 | 正常 |
| gh:m3u-autoupdate | 5 | 正常 |
| gh:IPTV-M3U-TOOL | 75 | 正常 |
| gh:Xixi-iptv | 38 | 正常 |
| gh:Xixi-iptv | 20 | 正常 |
| gh:iptv | 109 | 正常 |
| gh:Xixi-iptv | 9 | 正常 |

## 带宽实测（决定会不会卡）

| 频道 | 分辨率 | 音轨 | 码率 | 实测速度 | 余量 | 稳定性 | 评分 |
|---|---|---|---|---|---|---|---|
| 翡翠台 | 3840x2160 | aac | 15.3M | 99.0M | 6.5x | 100% | 2419 |
| Bloomberg tv+ 🇺🇸 | 3840x2160 | aac 344k | 10.0M | 203.4M | 20.3x | 100% | 2418 |
| 翡翠台 | 1920x1080 | mp2 230k | 8.0M | 66.5M | 8.3x | 100% | 2379 |
| 翡翠台 | 1920x1080 | mp2 230k | 8.0M | 93.8M | 11.7x | 100% | 2379 |
| CNA | 1920x1080 | aac | 8.0M | 255.1M | 31.9x | 100% | 2374 |
| CNN International | 1920x1080 | aac | 8.9M | 196.2M | 22.0x | 100% | 2370 |
| NHK World-Japan | 1920x1080 | - | 7.0M | 314.0M | 44.8x | 100% | 2355 |
| CNN International | 1920x1080 | aac | 8.9M | 171.8M | 19.3x | 100% | 2354 |
| [MLB] Cleveland Guardians at Tampa Bay Rays (SPRTSPASS) | 1920x1080 | aac | 8.6M | 60.5M | 7.1x | 100% | 2344 |
| Al Jazeera English | 1920x1080 | aac | 6.1M | 218.4M | 35.6x | 100% | 2336 |
| NBC News Now | 1920x1080 | aac | 5.3M | 233.9M | 44.5x | 100% | 2322 |
| NBC News Now 🇺🇸 | 1920x1080 | aac | 5.3M | 157.0M | 29.9x | 100% | 2322 |
| NBC News Now | 1920x1080 | aac | 5.3M | 146.3M | 27.8x | 100% | 2321 |
| NBC News Now | 1920x1080 | aac | 5.3M | 51.2M | 9.7x | 100% | 2320 |
| 无线新闻 | 1920x1080 | aac 646k | 5.0M | 40.2M | 8.1x | 100% | 2320 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 144.1M | 28.8x | 100% | 2319 |
| 华丽翡翠台 | 1920x1080 | aac | 5.0M | 74.8M | 15.0x | 100% | 2319 |
| TVB翡翠台 | 1920x1080 | - | 5.0M | 65.8M | 13.2x | 100% | 2319 |
| 翡翠台北美版 | 1920x1080 | aac 54k | 5.0M | 55.9M | 11.2x | 100% | 2319 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 57.3M | 11.5x | 100% | 2319 |
| 无线新闻台 | 1920x1080 | aac 646k | 5.0M | 131.8M | 26.4x | 100% | 2319 |
| 凤凰卫视台 | 1920x1080 | aac | 5.0M | 132.7M | 26.5x | 100% | 2318 |
| 翡翠 | 1920x1080 | - | 5.0M | 52.6M | 10.5x | 100% | 2318 |
| 凤凰中文 | 1920x1080 | aac | 5.0M | 71.6M | 14.3x | 100% | 2318 |
| [NHL] Toronto Maple Leafs at Utah Mammoth (SPRTSPASS) | 1920x1080 | aac | 8.6M | 52.8M | 6.2x | 100% | 2318 |
| 凤凰资讯台 | 1920x1080 | aac | 5.0M | 57.4M | 11.5x | 100% | 2318 |
| 凤凰香港台 | 1920x1080 | aac 54k | 5.0M | 81.4M | 16.3x | 100% | 2318 |
| ViuTV | 1920x1080 | - | 4.6M | 54.8M | 11.9x | 100% | 2311 |
| ViuTV | 1920x1080 | - | 4.6M | 46.3M | 10.1x | 100% | 2311 |
| ViuTV | 1920x1080 | - | 4.6M | 128.6M | 28.0x | 100% | 2310 |

> 音轨码率低于音轨阈值会标 ⚠ 并被降权：这种源视频很好但声音是噪音。

> 由 iptv-pipeline 自动生成 2026-10-14T21:48:26+00:00

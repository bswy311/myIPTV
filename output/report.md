# IPTV 直播源检测报告

- 运行时间：2026-10-19T13:28:57+00:00 → 2026-10-19T13:33:48+00:00（291.0 秒）
- 解析到流：**11932** 条
- 筛选后：4416 条，去重后：3016 条
- 实际探测：2987 条（拉黑跳过 1638 条）
- 可用：**999** 条（33.4%），失效：350 条
- 频道数：178，发布：178 个频道 / 341 条线路

## 流类型分布

- `hls`：958
- `mp4`：27
- `ts`：7
- `flv`：5
- `dash`：2

## 带宽实测概览

- 平均下载速度：**16.4 Mbps**（最低 0.8，最高 88.1）
- 平均视频码率：**2.5 Mbps**
- 带宽余量 ≥2x（基本不会卡）：**276/307** 条（占 90%）

> 余量 = 实测速度 ÷ 视频码率。余量 <1 必定卡；1~2 勉强；>2 流畅。

## 分组统计

| 分组 | 可用线路 | 频道数 |
|---|---|---|
| 央视 | 687 | 66 |
| 卫视 | 150 | 15 |
| 吉林 | 7 | 6 |
| 长春 | 1 | 1 |
| 港澳台 | 93 | 51 |
| 国际新闻 | 40 | 20 |
| 其他 | 21 | 19 |

## 采集源

| 源 | 条数 | 状态 |
|---|---|---|
| local-extra | 1 | 正常 |
| bestfan-cctv | 0 | 失败：HTTPStatusError: Server error '502 Bad Gateway' for url 'https://ghproxy.net/https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_cctv.m3u8'
For more information check: https://developer.mo |
| bestfan-province | 0 | 失败：HTTPStatusError: Server error '502 Bad Gateway' for url 'https://ghproxy.net/https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_province.m3u8'
For more information check: https://develope |
| bestfan-all | 0 | 失败：HTTPStatusError: Server error '502 Bad Gateway' for url 'https://ghproxy.net/https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_all.m3u8'
For more information check: https://developer.moz |
| bestfan-all-direct | 120 | 正常 |
| vbskycn-ipv4 | 524 | 正常 |
| vbskycn-ipv4-gh | 524 | 正常 |
| chinaiptv-cntv | 0 | 失败：HTTPStatusError: Server error '502 Bad Gateway' for url 'https://ghproxy.net/https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV1_ALL.m3u8'
For more information check: https://developer. |
| iptv-org-sports | 481 | 正常 |
| iptv-org-cn | 147 | 正常 |
| iptv-org-hk | 17 | 正常 |
| iptv-org-tw | 28 | 正常 |
| iptv-org-zho | 215 | 正常 |
| iptv-org-news | 1018 | 正常 |
| suxuang-iptv | 1225 | 正常 |
| suxuang-iptv-gh | 0 | 失败：HTTPStatusError: Server error '502 Bad Gateway' for url 'https://ghproxy.net/https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv4.m3u'
For more information check: https://developer.mozilla.org/e |
| gh:iptv-m3u-bot | 209 | 正常 |
| gh:Xixi-iptv | 55 | 正常 |
| gh:Xixi-iptv | 23 | 正常 |
| gh:m3u-autoupdate | 2748 | 正常 |
| gh:m3u-autoupdate | 5 | 正常 |
| gh:iptv | 221 | 正常 |
| gh:iptv-bridge | 636 | 正常 |
| gh:Xixi-iptv | 20 | 正常 |
| gh:iptv-curated | 45 | 正常 |
| gh:iptv | 1284 | 正常 |
| gh:iptv | 401 | 正常 |
| gh:iptv | 401 | 正常 |
| gh:IPTV-M3U-TOOL | 76 | 正常 |
| gh:iptv | 109 | 正常 |
| gh:myIPTV | 914 | 正常 |
| gh:myIPTV | 345 | 正常 |
| gh:iptv | 0 | 失败：HTTPStatusError: Client error '404 Not Found' for url 'https://raw.githubusercontent.com/app-bot-server/iptv/main/lista.m3u8'
For more information check: https://developer.mozilla.org/en-US/docs/Web/H |

## 带宽实测（决定会不会卡）

| 频道 | 分辨率 | 音轨 | 码率 | 实测速度 | 余量 | 稳定性 | 评分 |
|---|---|---|---|---|---|---|---|
| Bloomberg TV + | 3840x2160 | aac 344k | 10.0M | 84.1M | 8.4x | 100% | 2415 |
| Bloomberg tv+ 🇺🇸 | 3840x2160 | aac 344k | 10.0M | 65.7M | 6.6x | 100% | 2413 |
| CNN International | 1920x1080 | aac | 8.9M | 54.0M | 6.0x | 100% | 2370 |
| CNN International | 1920x1080 | aac | 8.9M | 65.1M | 7.3x | 100% | 2368 |
| NHK World-Japan | 1920x1080 | - | 7.0M | 77.0M | 11.0x | 100% | 2340 |
| Al Jazeera English | 1920x1080 | aac | 6.1M | 43.3M | 7.1x | 100% | 2333 |
| CGTN 英语 | 1920x1080 | aac | 5.9M | 65.5M | 11.2x | 100% | 2322 |
| NBC News Now 🇺🇸 | 1920x1080 | aac | 5.3M | 33.8M | 6.4x | 100% | 2319 |
| 无线新闻台 | 1920x1080 | aac 161k | 5.0M | 40.9M | 8.2x | 100% | 2319 |
| 无线新闻 | 1920x1080 | aac 1908k | 5.0M | 34.9M | 7.0x | 100% | 2318 |
| 凤凰香港台 | 1920x1080 | aac 54k | 5.0M | 34.0M | 6.8x | 100% | 2318 |
| 明珠台 | 1920x1080 | - | 5.0M | 34.1M | 6.8x | 100% | 2317 |
| NBC News Now | 1920x1080 | aac | 5.3M | 32.1M | 6.1x | 100% | 2317 |
| 明珠台 | 1920x1080 | - | 5.0M | 31.7M | 6.3x | 100% | 2317 |
| 无线新闻台 | 1920x1080 | aac 50k | 5.0M | 32.3M | 6.5x | 100% | 2317 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 39.8M | 8.0x | 100% | 2317 |
| 凤凰资讯台 | 1920x1080 | aac | 5.0M | 33.3M | 6.7x | 100% | 2317 |
| 凤凰中文 | 1920x1080 | aac | 5.0M | 30.2M | 6.0x | 100% | 2317 |
| TVB翡翠台 | 1920x1080 | - | 5.0M | 36.6M | 7.3x | 100% | 2317 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 29.9M | 6.0x | 100% | 2316 |
| 明珠台 | 1920x1080 | - | 5.0M | 39.2M | 7.8x | 100% | 2316 |
| NBC News Now | 1920x1080 | aac | 5.3M | 70.0M | 13.3x | 100% | 2313 |
| 华丽翡翠台 | 1920x1080 | aac | 5.0M | 29.7M | 5.9x | 100% | 2312 |
| ViuTV | 1920x1080 | - | 4.6M | 37.4M | 8.1x | 100% | 2311 |
| ViuTV | 1920x1080 | - | 4.6M | 38.1M | 8.3x | 100% | 2310 |
| CNBC UK | 1920x1080 | aac | 4.7M | 76.4M | 16.2x | 100% | 2309 |
| Reuters TV | 1920x1080 | aac | 4.7M | 45.8M | 9.7x | 100% | 2306 |
| 明珠台 | 1920x1080 | aac 705k | 4.3M | 31.7M | 7.4x | 100% | 2303 |
| CGTN 财经 | 1920x1080 | aac | 4.7M | 35.2M | 7.5x | 100% | 2303 |
| 明珠台 | 1920x1080 | aac 421k | 4.3M | 39.7M | 9.3x | 100% | 2303 |

> 音轨码率低于音轨阈值会标 ⚠ 并被降权：这种源视频很好但声音是噪音。

> 由 iptv-pipeline 自动生成 2026-10-19T13:33:48+00:00

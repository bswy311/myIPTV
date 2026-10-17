# IPTV 直播源检测报告

- 运行时间：2026-10-17T15:40:55+00:00 → 2026-10-17T15:45:14+00:00（259.5 秒）
- 解析到流：**14229** 条
- 筛选后：5591 条，去重后：3862 条
- 实际探测：3833 条（拉黑跳过 1839 条）
- 可用：**1138** 条（29.7%），失效：856 条
- 频道数：175，发布：175 个频道 / 344 条线路

## 流类型分布

- `hls`：1099
- `mp4`：25
- `ts`：8
- `flv`：4
- `dash`：2

## 带宽实测概览

- 平均下载速度：**15.2 Mbps**（最低 0.8，最高 482.8）
- 平均视频码率：**2.4 Mbps**
- 带宽余量 ≥2x（基本不会卡）：**276/314** 条（占 88%）

> 余量 = 实测速度 ÷ 视频码率。余量 <1 必定卡；1~2 勉强；>2 流畅。

## 分组统计

| 分组 | 可用线路 | 频道数 |
|---|---|---|
| 央视 | 793 | 68 |
| 卫视 | 186 | 14 |
| 吉林 | 7 | 6 |
| 长春 | 1 | 1 |
| 港澳台 | 94 | 48 |
| 国际新闻 | 36 | 19 |
| 其他 | 21 | 19 |

## 采集源

| 源 | 条数 | 状态 |
|---|---|---|
| local-extra | 1 | 正常 |
| bestfan-cctv | 0 | 失败：HTTPStatusError: Client error '429 TOO MANY REQUESTS' for url 'https://ghproxy.net/https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_cctv.m3u8'
For more information check: https://develo |
| bestfan-province | 0 | 失败：HTTPStatusError: Client error '429 TOO MANY REQUESTS' for url 'https://ghproxy.net/https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_province.m3u8'
For more information check: https://de |
| bestfan-all | 163 | 正常 |
| bestfan-all-direct | 163 | 正常 |
| vbskycn-ipv4 | 533 | 正常 |
| vbskycn-ipv4-gh | 533 | 正常 |
| chinaiptv-cntv | 0 | 失败：HTTPStatusError: Client error '429 TOO MANY REQUESTS' for url 'https://ghproxy.net/https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV1_ALL.m3u8'
For more information check: https://deve |
| iptv-org-sports | 476 | 正常 |
| iptv-org-cn | 147 | 正常 |
| iptv-org-hk | 18 | 正常 |
| iptv-org-tw | 28 | 正常 |
| iptv-org-zho | 216 | 正常 |
| iptv-org-news | 1019 | 正常 |
| suxuang-iptv | 1225 | 正常 |
| suxuang-iptv-gh | 0 | 失败：HTTPStatusError: Client error '429 TOO MANY REQUESTS' for url 'https://ghproxy.net/https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv4.m3u'
For more information check: https://developer.mozilla |
| gh:Xixi-iptv | 20 | 正常 |
| gh:Xixi-iptv | 0 | 正常 |
| gh:Xixi-iptv | 20 | 正常 |
| gh:m3u-autoupdate | 2748 | 正常 |
| gh:m3u-autoupdate | 5 | 正常 |
| gh:iptv-curated | 45 | 正常 |
| gh:iptv-bridge | 637 | 正常 |
| gh:iptv | 2094 | 正常 |
| gh:iptv | 1081 | 正常 |
| gh:iptv | 1081 | 正常 |
| gh:IPTV-M3U-TOOL | 74 | 正常 |
| gh:iptv | 221 | 正常 |
| gh:iptv | 109 | 正常 |
| gh:myIPTV | 1082 | 正常 |
| gh:myIPTV | 363 | 正常 |
| gh:iptv | 0 | 失败：HTTPStatusError: Client error '404 Not Found' for url 'https://raw.githubusercontent.com/app-bot-server/iptv/main/lista.m3u8'
For more information check: https://developer.mozilla.org/en-US/docs/Web/H |

## 带宽实测（决定会不会卡）

| 频道 | 分辨率 | 音轨 | 码率 | 实测速度 | 余量 | 稳定性 | 评分 |
|---|---|---|---|---|---|---|---|
| 翡翠台 | 3840x2160 | aac 153k | 15.3M | 88.6M | 5.8x | 100% | 2400 |
| 翡翠台 | 3840x2160 | aac 98k | 15.3M | 86.9M | 5.7x | 100% | 2393 |
| 翡翠台 | 1920x1080 | mp2 144k | 8.0M | 97.2M | 12.1x | 100% | 2378 |
| 翡翠台 | 1920x1080 | mp2 287k | 8.0M | 85.0M | 10.6x | 100% | 2377 |
| 翡翠台 | 1920x1080 | mp2 287k | 8.0M | 47.3M | 5.9x | 100% | 2366 |
| CNN International | 1920x1080 | aac | 8.9M | 57.7M | 6.5x | 100% | 2358 |
| NHK World-Japan | 1920x1080 | - | 7.0M | 482.8M | 68.9x | 100% | 2353 |
| 翡翠台 | 3840x2160 | aac 153k | 15.3M | 76.5M | 5.0x | 100% | 2340 |
| NBC News Now | 1920x1080 | aac | 5.3M | 467.1M | 88.9x | 100% | 2321 |
| NBC News Now | 1920x1080 | aac | 5.3M | 140.2M | 26.7x | 100% | 2321 |
| 无线新闻台 | 1920x1080 | aac 1359k | 5.0M | 59.9M | 12.0x | 100% | 2320 |
| NBC News Now 🇺🇸 | 1920x1080 | aac | 5.3M | 70.2M | 13.4x | 100% | 2319 |
| 华丽翡翠台 | 1920x1080 | aac | 5.0M | 43.4M | 8.7x | 100% | 2319 |
| 凤凰香港台 | 1920x1080 | aac 54k | 5.0M | 80.9M | 16.2x | 100% | 2319 |
| NBC News Now | 1920x1080 | aac | 5.3M | 61.8M | 11.8x | 100% | 2319 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 89.8M | 17.9x | 100% | 2319 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 78.2M | 15.7x | 100% | 2319 |
| 凤凰资讯台 | 1920x1080 | aac | 5.0M | 61.2M | 12.2x | 100% | 2318 |
| 翡翠台北美版 | 1920x1080 | aac 57k | 5.0M | 41.9M | 8.4x | 100% | 2318 |
| 凤凰中文 | 1920x1080 | aac | 5.0M | 91.0M | 18.2x | 100% | 2318 |
| 无线新闻台 | 1920x1080 | aac 151k | 5.0M | 89.7M | 17.9x | 100% | 2318 |
| 凤凰资讯 | 1920x1080 | aac | 5.0M | 75.8M | 15.2x | 100% | 2318 |
| TVB翡翠台 | 1920x1080 | - | 5.0M | 92.0M | 18.4x | 100% | 2318 |
| 翡翠台 | 1920x1080 | - | 5.0M | 80.0M | 16.0x | 100% | 2318 |
| 明珠台 | 1920x1080 | - | 5.0M | 103.7M | 20.7x | 100% | 2318 |
| 凤凰卫视台 | 1920x1080 | aac | 5.0M | 69.1M | 13.8x | 100% | 2317 |
| 翡翠 | 1920x1080 | - | 5.0M | 90.8M | 18.1x | 100% | 2317 |
| 无线新闻 | 1920x1080 | aac 151k | 5.0M | 91.1M | 18.2x | 100% | 2316 |
| 翡翠台 | 1920x1080 | - | 5.0M | 97.4M | 19.5x | 100% | 2315 |
| TVB Plus | 1920x1080 | - | 5.0M | 98.3M | 19.7x | 100% | 2315 |

> 音轨码率低于音轨阈值会标 ⚠ 并被降权：这种源视频很好但声音是噪音。

> 由 iptv-pipeline 自动生成 2026-10-17T15:45:14+00:00

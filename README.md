# IPTV 直播源自动采集 · 检测 · 剔除 · 发布

自动聚合公开直播源 → **真实拉流验证** → 剔除失效源 → 生成标准 M3U，供安卓 TV / PotPlayer 订阅。
本机可跑，也能交给 GitHub Actions 每 6 小时自动更新并发布到 Pages，电视端订阅一个固定网址即可。

---

## 一、它解决了什么问题

网上公开的 IPTV 列表最大的痛点是：**80% 的源是死的**。只做「域名能不能连通」的检测毫无意义，
因为大量失效源会返回 `HTTP 200` + 一个门户网页。

本项目的核心是**分层深检**：

```mermaid
flowchart LR
    A[公开源列表<br/>M3U / TXT] --> B[解析 EXTINF<br/>tvg-id/名称/分组]
    B --> C[关键词筛选<br/>中文 · 体育优先]
    C --> D[频道名归一化<br/>CCTV-1 = cctv1 = 央视一套]
    D --> E{分层探测}
    E -->|HLS| F[清单 → 子清单 → 拉首个分片]
    E -->|TS| G[校验 0x47 同步字节]
    E -->|MP4/FLV| H[校验文件头魔数]
    F --> I[评分排序]
    G --> I
    H --> I
    I --> J[历史库累计成败<br/>连续失败 N 次 → 拉黑]
    J --> K[live.m3u<br/>每频道保留 Top-N 备用线路]
```

**关键判定规则**：

| 情况 | 判定 |
|---|---|
| HLS 清单拿到了，但第一个分片拉不下来 | ❌ 失效 |
| 返回 `200` 但 `Content-Type: text/html` | ❌ 失效 |
| TS 流前 64KB 里找不到 `0x47` 同步字节 | ❌ 失效 |
| MP4 缺少 `ftyp` 头 / FLV 缺少 `FLV` 头 | ❌ 失效 |
| 分片能正常下载且 > 1KB | ✅ 可用 |

---

## 二、快速开始

### 1. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

> 只依赖 `httpx` 和 `PyYAML`。HLS 解析是项目自带实现的，不依赖第三方 m3u8 库，
> 因此在 Python 3.10 ~ 3.14 上都能直接装好。

### 2. 跑一次完整流程

```powershell
python main.py run
```

或者直接双击 `run.bat`。

跑完会在 `output/` 下生成：

| 文件 | 用途 |
|---|---|
| **`live.m3u`** | ★ 主文件，每个频道保留评分最高的 3 条线路，**给电视订阅这个** |
| `live_full.m3u` | 全部验证可用的源（不裁剪） |
| `live.txt` | 纯 URL 列表，方便手工挑单个链接测试 |
| `index.html` | 网页版总览面板（含一键直连测试） |
| `report.md` | 本次检测报告：存活率、分组统计、优质线路排行 |
| `stats.json` | 运行快照，便于排查 |

### 3. 用 PotPlayer 验证（本机）

两种方式，任选：

**方式 A — 直接打开文件**

双击 `output/live.m3u`，或在 PotPlayer 里 `F3` → 打开播放列表 → 选择该文件。
左侧会按「央视 / 卫视 / 港澳台 / 体育 …」分组，双击某个频道即可播放。

**方式 B — 通过局域网地址打开（更接近电视的真实使用场景）**

```powershell
python main.py serve        # 或双击 serve.bat
```

输出示例：

```
PotPlayer / 本机测试：
  订阅地址 : http://127.0.0.1:8899/live.m3u
安卓 TV / 手机（同一局域网）：
  订阅地址 : http://192.168.1.23:8899/live.m3u
```

在 PotPlayer 里 `Ctrl+U` 粘贴 `http://127.0.0.1:8899/live.m3u` 即可。
服务已强制 `Cache-Control: no-store`，重新检测后电视端刷新就能看到最新列表，不会被缓存坑到。

---

## 三、安卓 TV 使用

支持订阅 M3U 的播放器都可以直接用：

| 播放器 | 添加方式 |
|---|---|
| **TiviMate** | 添加播放列表 → M3U 播放列表 → 输入下方订阅地址 |
| **OTT Navigator** | 播放列表 → 添加 → M3U URL |
| **Kodi** | PVR IPTV Simple Client 插件 → M3U Play List URL |
| 电视家 / 火星直播等 | 自定义源 → 填订阅地址 |

**方式一：局域网订阅（最省事）**

电脑上跑 `python main.py serve`，电视上填 `http://电脑IP:8899/live.m3u`。
记得把电脑 IP 设为静态（或在路由器做 DHCP 绑定），并且电脑要开机。

**方式二：GitHub Pages 订阅（推荐长期使用）**

见下一节。电脑不用开机，电视随时能拉到最新列表。

---

## 四、GitHub Actions 全自动更新

推送到 GitHub 后，`.github/workflows/update.yml` 会：

1. 每 6 小时（UTC `17 */6 * * *`）自动跑一次，也支持手动触发
2. 把 `data/history.json`（历史战绩）和 `output/`（结果）提交回仓库
3. 部署到 GitHub Pages

**关键点：一定要用 Pages 的地址，不要用 `raw.githubusercontent.com`。**
实测后者在部分网络下会间歇性连不上，而 `*.github.io` 稳定得多。

订阅地址格式：

```
https://<你的用户名>.github.io/<仓库名>/live.m3u
```

> **首次使用必须手动做两件事，缺一不可：**
>
> 1. **仓库必须是 Public**。GitHub Pages 在私有仓库上需要付费账号（Pro / Team / Enterprise），
>    Free 账号的私有仓库无法启用 Pages。改法：
>    `Settings → General → 拉到底部 Danger Zone → Change visibility → Public`
> 2. **启用 Pages**：`Settings → Pages → Build and deployment → Source` 选择 **GitHub Actions**
>
> 第 2 步**没法用 workflow 自动完成**。虽然 `actions/configure-pages` 有个 `enablement: true`
> 参数，但创建 Pages 站点需要管理员权限，Actions 自带的 `GITHUB_TOKEN` 会直接报
> `Resource not accessible by integration`。所以这次点击是省不掉的。
>
> workflow 里加了一步前置检查，如果 Pages 没开，它会直接告诉你该点哪里，不会让你对着
> `HttpError: Not Found` 猜。
>
> 顺带一提，仓库设为 Public 后 Actions 分钟数不计费（私有仓库才吃 2000 分钟/月的免费额度）。

因为 `data/history.json` 会一起提交，**每次运行都在上一次的战绩基础上做判断**，
失效源会持续累积失败次数直至被拉黑，稳定源则越用越靠前。

### 关于「推送撞车」

流水线跑完会自动把结果 commit 回仓库。如果你**同时**在本机手动 `git push`，
两者会撞车（`! [rejected] main -> main (fetch first)`）。

workflow 里已经做了处理：推送被拒时会自动 `git fetch` + `git rebase -X theirs` 后重试，
最多 3 次。所以正常情况下你不需要管它，只管在本机正常 `git push` 即可。

另外 workflow 只会提交 `output/`、`data/history.json`、`data/last_run.json`。
`data/raw.json` 和 `data/probed.json` 是中间产物，不进仓库。

---

## 五、带宽筛选 · 自动剔除 · 自动复活

### 带宽测速：解决「能打开但一直转圈」

「源可用」和「源能流畉看」是两件事。一个返回 `200`、分片也能拉到 64KB 的源，
完全可能只有 200kbps —— 打开有画面，然后一直转圈。

所以探测分两个阶段：

```mermaid
flowchart LR
    A["阶段一 · 可达性<br/>并发 200，每条只读 64KB"] -->|"活下来"| B["阶段二 · 带宽测速<br/>并发 16，实测下载速度"]
    B --> C{"速度 ≥ min_speed_kbps?"}
    C -->|"是"| D["记下 speed / bitrate / 稳定性"]
    C -->|"否"| E["剔除"]
    D --> F["按 speed ÷ bitrate 余量排序"]
```

阶段一求「快、广」，阶段二求「准」，所以**并发必须低**。
用 200 并发去测速等于同时从 200 个服务器下载，把自己家带宽占满，
测出来每个源都只有几百 kbps —— 结论全是错的。

| 指标 | 含义 | 怎么看 |
|---|---|---|
| `speed_kbps` | 实测下载速度 | 越大越好 |
| `bitrate_kbps` | 视频本身码率 | 分片完整下完时按 `#EXTINF` 时长算，否则用清单里声明的 `BANDWIDTH` |
| `headroom` | `speed ÷ bitrate` | **<1 必卡；1~2 勉强；>2 流畉** |
| `stability` | 分片拉取成功率 | <100% 说明源不稳定 |

排序完全按 `headroom` 优先，所以「同一频道留 3 条备用线路」时，
排第一的一定是速度最宽裕的那条。`output/report.md` 和 `index.html` 里都有这一列。

#### 墙钟预算：一个踩过的坑

单条流的测速有个全局时间上限 `bw_total_timeout`。这个值**必须 ≥「拉清单 + 下完 `bw_sample_bytes`」**，
否则会出大问题：

```
内层：每个分片软超时 8s，要连测 2 个分片        -> 最坏 16s
外层：bw_total_timeout = 12s
结果：外层 asyncio.wait_for 一到点就 cancel 掉整个协程
      -> 已经下载到的字节也一起丢掉
      -> 一个完全能看的源被记成「整体超时」
```

这个 bug 实测吃掉了 **122 条流**，其中央视 26 条、卫视 26 条，
央视/卫视频道数直接腰斩。

现在的做法是**让内层自己看着 deadline 提前收工**（`validate._limit()`）：
每个 HTTP 请求的墙钟上限都被压到「剩余预算」以内，
于是外层那道 `asyncio.wait_for` 只是个永远不该触发的保险。
`tests/test_bandwidth.py` 里有针对它的回归测试。

#### 先量一下自己家的宽带

`bw_concurrency` 该填多少，取决于你这条线有多宽：

```powershell
python tools/speedtest.py        # 多源测单流速度
python tools/speedtest.py -p 6   # 6 路并发，看聚合上限
```

按「单条流平均 3 Mbps、留 4 倍余量」估：

| 宽带 | 建议 `bw_concurrency` |
|---|---|
| 50M | 8 |
| 100M | 16 |
| 200M | 24 |
| 500M+ | 32 |

> **检测所在网络会直接决定结果。** 在 GitHub Actions（美国机房）测出来的速度，
> 和你家电视实际能跑的速度不是一回事。如果在意播放质量，
> 建议在本机跑检测（见第八节），或者至少把 `min_speed_kbps` 调保守些。

### 历史战绩：自动剔除与复活

`data/history.json` 记录了每条 URL 的成功/失败次数：

```json
{
  "http://example.com/cctv1.m3u8": {
    "ok_count": 37,
    "fail_count": 0,
    "fail_streak": 0,
    "last_ok": "2026-10-01T12:00:00+00:00",
    "latency_ms": 218.4,
    "blacklist_until": ""
  }
}
```

- **连续失败 `blacklist_after`（默认 4）次** → 打上 `blacklist_until`，之后不再浪费时间去探测
- **冷却 `blacklist_hours`（默认 72）小时** → 自动解除黑名单重新探测，源修好了会自动复活
- 连续失败会被扣分，即使没到拉黑线，排位也会掉到备用线路后面
- 超过 `keep_days`（默认 60 天）没出现的记录会被清理

想手动重置：`python main.py reset -y`

### 断崖保护

网络抽风时可用源会骤降。如果某次检测出的频道数不到上次的 `min_keep_ratio`
（默认 50%），程序会**拒绝覆盖** `output/` 里的文件并打印提示：

```
[保留旧文件] 本次仅 6 个频道，不到上次 263 个的 50%
        为免把电视上的好列表冲掉，本次不覆盖输出。
```

这样即使某次跑失败，电视上的订阅列表也不会被清空。确认要写入就加 `--force`：

```powershell
python main.py run --force
```

---

## 六、配置说明（`config/config.yaml`）

改完配置直接重跑，不需要动代码。

### 采集源

```yaml
sources:
  - name: bestfan-cctv
    url: https://ghproxy.net/https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_cctv.m3u8
    enabled: true
    filter: include      # include=按关键词筛（默认）；all=这个源的频道全都要
```

默认启用的源：

| 源 | 内容 |
|---|---|
| `best-fan/iptv-sources` (`cn_cctv` / `cn_province` / `cn_all`) | 央视 1~17 全套 + 省卫视 |
| `vbskycn/iptv` (`iptv4`) | 国内直连大源，央视/卫视/地方/影视，每日更新 |
| `hujingguang/ChinaIPTV` (`cnTV1_ALL`) | 地方台合集 |
| `iptv-org` (sports / news / cn / hk / tw / zho) | 体育、国际新闻、港澳台补充 |

> **关于 ghproxy.net**：本机访问 `raw.githubusercontent.com` 会间歇性失败，
> 所以 GitHub 上的源统一走 ghproxy 镜像，同时保留直连版本作备份，
> 哪条通用哪条，重复 URL 自动去重。单个源失败不影响整体。

`url` 也支持**本地文件路径**，可以填自己整理的清单。想全量收录（一万多频道），
把 `iptv-org-index` 的 `enabled` 改成 `true` 即可。

> **筛选会先做本地化，这点很重要**。像 `iptv-org` 的 `countries/cn.m3u` 用的是
> 英文名（`Beijing Satellite TV` / `Hunan TV` / `Dragon TV`），而
> `include_keywords` 里写的是中文「卫视」。如果直接拿英文名去比，这些源一旦声明
> `filter: include`，**北京/湖南/东方/江苏/浙江/深圳卫视会被整个筛掉**
> （实测 122 条里只剩 17 条）。
>
> 所以 `normalize.matches_filter()` 会先把频道名本地化再匹配：
> `Beijing Satellite TV` → `北京卫视` → 命中「卫视」。
> 于是**所有源都可以统一用 `filter: include`**，不必再靠 `filter: all` 绕开。
> 白名单的初衷（把杂台滤掉）不受影响。

### 节目单 EPG

程序不下载 EPG，只把地址写进 m3u 头部的 `x-tvg-url`，**播放器自己去拉**：

```
#EXTM3U x-tvg-url="https://live.fanmingming.cn/e.xml"
```

这个 `e.xml` 恰好覆盖**央视全套 + 39 个省卫视**，而且它的 channel id 就是
`CCTV1` / `CCTV5+` / `北京卫视` 这种格式——程序生成的 `tvg-id` 就是按这个规则
对齐的（见 `normalize.epg_id()`），所以 央视和卫视两组能直接看到节目单。

吉林地方台、长春台等上游 EPG 里没有的频道，自然不显示节目单。
想换 EPG 改 `output.epg_url` 即可；注意换成别的 EPG 往往需要同步改 `epg_id()`
的 id 规则，否则匹配不上。

### 台标

```yaml
output:
  logo_template: "https://live.fanmingming.com/tv/{id}.png"
  logo_prefer_template: true    # 央视和卫视一律用模板，避免同频道混用几套图源
```

`{id}` 就是 `tvg-id`（如 `CCTV1`）。开启 `logo_prefer_template` 后央视和卫视
统一用同一套台标，否则优先用源里自带的，只在缺失或碰到已失效图床
（`tv.haoqu99.com` 等）时才回退到模板。

### 命名与排序

- **央视**：显示为规范中文名 `CCTV-1 综合` / `CCTV-5+ 体育赛事`，
  而不是 `CCTV-1`。央视付费频道也做了中文化（`CCTV-Storm Music` → `央视风云音乐`）。
- **英文名本地化**：`Beijing Satellite TV` → `北京卫视`，`Hunan TV` → `湖南卫视`，
  `Dragon TV` → `东方卫视`，`TVB Jade` → `翡翠台`。
  好处是同一频道的英文写法和中文写法会合并成**同一频道的多条备用线路**。
- **去噪**：`[Not 24/7]`、`[Geo-blocked]` 这类上游标注不会出现在电视上；
  `HEVC`、`50 FPS` 这些变体会归并到同一频道。
- **排序**：央视按 **数字** 排（1,2,3…17，`CCTV-5+` 紧跟 `CCTV-5`），
  而不是字符串排序（否则会变成 1,10,11,12…2,3）。
  卫视按中国行政区划顺序（北京→天津→河北→…→黑龙江→上海→…）。
- **分组顺序**：央视 → 卫视 → 吉林 → 港澳台 → 体育 → 影视 → 少儿 → 纪录 → 新闻 → 音乐 → 其他。

### 地方台过滤

```yaml
filter:
  local_filter_enabled: true
  local_keep: [吉林, 长春, 吉视]     # 地方台白名单
```

有些源的 `group-title` 是 `浙江台` / `黑龙江台` / `吉林台` 这种形式，里面混了
大量县级台（「浙江上虞新闻综合频道」之类）。开了这个开关后，
**只有白名单命中的地方台会保留**，其它一律丢弃。
不想过滤就把它改成 `false`。

### 筛选范围

```yaml
filter:
  mode: include          # include=只留命中关键词的；all=全都要
  include_keywords: [cctv, 卫视, 体育, 翡翠, 凤凰, ...]
  exclude_keywords: [测试, test, 广告]
```

默认是「中文频道 + 体育频道优先」。想换成全量：`python main.py run --mode all`

### 调节速度与吞吐

```yaml
network:
  concurrency: 200       # 并发数，本机 200 稳；网络差就降到 50
  timeout: 8.0           # 单请求超时
  retries: 1             # 失败重试（只重试超时/连接错误，4xx 直接判死）
  max_probe: 4000        # 单次最多探测多少条，0=不限
```

命令行也能临时覆盖：

```powershell
python main.py run --concurrency 400 --max-probe 1000
```

### 带宽测速参数

```yaml
validate:
  bw_enabled: true         # 总开关；关掉后退回「只验证能出流」（快很多，但会卡）
  bw_segments: 2           # 每个流连续拉几个分片（用来算稳定性和码率）
  bw_sample_bytes: 700000  # 每个流总共最多下载多少字节（约 0.68MB）
  min_speed_kbps: 800      # 实测速度低于此值直接剔除；嫌频道少就降到 400
  bw_concurrency: 16       # 测速并发，必须低；太大等于自己把带宽占满
  bw_total_timeout: 18     # 单条流测速的墙钟上限，见第五节
```

四个值的相互关系（改一个就得跟着改另一个）：

- `bw_total_timeout` ≥ 「拉清单 + 下完 `bw_sample_bytes`」
  （800kbps 下 700KB 约需 7s，加上拉清单给到 18s 已经很宽裕）
- `min_speed_kbps` × `bw_concurrency` 要明显小于你家宽带上限，
  否则测出来的速度会普遍偏低
- `bw_sample_bytes` 太小会把突发速度当成真实速度，太大则拖慢整轮

### 输出

```yaml
output:
  max_per_channel: 3     # 每个频道保留几条备用线路
  epg_url: ""            # 有 EPG 就填，会写进 #EXTM3U x-tvg-url
```

---

## 七、命令一览

```powershell
python main.py run                      # 完整流程（最常用）
python main.py run --serve              # 跑完顺手起局域网服务
python main.py run --mode all           # 不限关键词，全量检测
python main.py run --max-probe 500      # 只探测前 500 条（调试用）
python main.py run --concurrency 400    # 提高并发
python main.py run --force              # 跳过断崖保护，强制覆盖输出
python main.py collect                  # 只采集，存成 data/raw.json
python main.py publish                  # 用上次探测结果重新生成输出（不联网）
python main.py serve                    # 只起局域网服务
python main.py stats                    # 查看历史库统计
python main.py reset -y                 # 清空历史库
```

---

## 八、Windows 定时自动更新（不用 GitHub 的话）

1. 打开「任务计划程序」→ 创建基本任务
2. 触发器：每天 / 每 6 小时
3. 操作：启动程序 → 选择 `d:\code\iptv\run.bat`
4. 若要电视随时能拉取，再配一个开机自启的 `serve.bat` 任务

---

## 九、项目结构

```
iptv/
├── main.py                     # 入口
├── config/config.yaml          # 全部可调参数
├── requirements.txt
├── run.bat / serve.bat         # Windows 一键脚本
├── src/iptv/
│   ├── collect.py              # 采集 + M3U/TXT 解析
│   ├── normalize.py            # 频道名归一化、分类、筛选
│   ├── hls.py                  # 自研极简 m3u8 解析器（零依赖）
│   ├── validate.py             # ★ 分层探测 + 带宽测速（核心）
│   ├── history.py              # 历史战绩：剔除与复活
│   ├── publish.py              # 生成 M3U / 报告 / 网页
│   ├── server.py               # 局域网订阅服务
│   ├── pipeline.py             # 流程编排
│   └── cli.py                  # 命令行
├── tools/speedtest.py          # 量本机宽带，用来定 bw_concurrency
├── data/                       # history.json / raw.json / probed.json
├── output/                     # 生成结果
└── tests/
    ├── test_normalize.py       # 频道名归一化回归测试
    └── test_bandwidth.py       # 带宽测速与评分回归测试
```

---

## 十、常见问题

**Q：电视上列表是空的 / 一直转圈？**
先确认电脑和服务端在同一局域网，用手机浏览器打开 `http://电脑IP:8899/live.m3u` 看能不能下载。
Windows 防火墙首次会弹窗，记得勾选「专用网络」允许。

**Q：可用率只有 50% 左右？**
正常。公开源本来就大半是死的，能稳定留下 200+ 条可用线路已经是很好的结果。
连续跑几天后，因为历史库会持续剔除不稳定源，列表质量会明显变好。

**Q：某个频道没有？**
说明该频道所有源都没通过深检。可以在 `filter.mode` 改成 `all`、调大 `network.timeout`，
或者把自己的源加到 `sources` 里再跑一次。

**Q：体育频道在比赛日才播，平时检测不到怎么办？**
调大 `history.blacklist_hours`（比如 168 小时）可以延长拉黑冷却，避免冷门时段被误杀。

**Q：GitHub Actions 跑失败了？**
Actions 的出口网络和本机不同，部分源在那边可能不通。这是正常的，
把 `--concurrency` 降到 120（workflow 里已设置）并适当调大 `timeout` 一般就好了。

**Q：会不会下完整部电影把流量跑光？**
不会。所有请求都是**流式读取前 64KB 就主动断开**，正常一次全量检测的流量在几十 MB 级别。

---

## 免责声明

本项目仅提供**技术工具**，用于聚合网络上公开可访问的直播流地址并检测其可用性。
不存储、不转播任何内容，不提供任何破解或绕过授权的手段。
使用者应自行确认所聚合内容的合法性与适用性，并遵守当地法律法规。

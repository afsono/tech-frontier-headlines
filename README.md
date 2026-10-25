# 全球科技前沿头条 · Global Tech Frontier Headlines

[中文](#中文说明) | [English](#english)

> 不是把新闻堆给你，而是回答：**这个领域今天发生了什么、哪几条真正值得你花时间、为什么。**
>
> Not another headline dump — it answers: **what actually happened in this field today, which few items deserve your time, and why.**

An AI-agent skill that turns a curated global tech-news feed (`news.tekoai.net`) into layered briefings:
quick scan / standard briefing / deep dive / incremental diff / shareable HTML daily / WeChat push.

一个把「全球科技要闻数据源 news.tekoai.net」加工成分层简报的 Agent Skill：
速览 / 标准简报 / 单条深挖 / 增量对比 / 可分享 HTML 日报 / 微信推送。

- 数据源 / Data source：<https://news.tekoai.net>（每 30 分钟刷新，国内可直连，无需代理 / refreshed every 30 min, direct access from mainland China）
- 零依赖 / Zero dependencies：核心流程纯提示词可用；脚本**只用 Python 标准库**，无需 `pip install`，Python 3.7+
- 许可 / License：**MIT**
- SkillHub 页面 / Marketplace page：<https://skillhub.cn/skills/user_84b3ceb3/teko-tech-news-sum>

---

## 中文说明

### 它和市面上的新闻 skill 有什么不同

| 常见做法 | 这个技能 |
|---|---|
| 抓标题堆给你，相关性 40–60% | **十大硬科技领域 + 大模型评分筛选**，只给过线的 |
| 全网热搜 / 大众舆情视角 | **前沿科技与产业情报视角**（防务、能源、科技战略、先进制造…） |
| 只覆盖 AI 或财经单一领域 | **十大硬科技领域**，可任意组合订阅 |
| 给你一份列表，不告诉你为什么选它 | 每条带 **0–100 评分**、**分类大类/细类**、**关键词**、**原始信源链接**，可核验 |
| 每次从零开始 | **兴趣记忆 + 增量模式**，回答「跟上次比新增了什么」 |
| 一次输出一种形态 | 对话简报 / 可分享 HTML 日报 / 微信推送，按需选 |

### 数据来源与可信度

数据来自 **news.tekoai.net**：

- 持续扫描全球**数千个**可信站点——通讯社、专业垂直媒体、机构官网、权威行业媒体
- 每条新闻经**前沿大模型**处理：生成中文摘要、判定所属科技领域、给出 0–100 价值评分、抽取关键词
- **服务端已完成去重**：只输出 `duplicate_checked = 1` 且 `score_class != 'DUP'` 的条目
- 覆盖十个硬科技领域 × 数十个细分方向，分类形如「能源—先进核裂变/第四代核电」
- **每 30 分钟自动更新**，国内可直连，无需代理
- 每个频道提供 **JSON（智能体）/ RSS（阅读器）/ HTML（搜索引擎收录）** 三种格式

> 所以这里和「抓一堆标题」的工具不同：每一条都带着**评分为何入选**的信号，
> 以及可以点开核验的**原文链接**。

### 覆盖领域

| 领域 | 包括什么 |
|---|---|
| **防务** | 军机平台、导弹与高超声速、无人自主系统、军贸、军事战略、太空军事、C4ISR |
| **能源** | 先进核裂变、核聚变、新型储能、可再生能源、氢能、油气技术、智能电网、CCUS |
| **信息** | 大模型与生成式AI、AI芯片与算力、半导体、量子、网络安全、6G、光通信 |
| **科技战略** | 出口管制、投资审查、制裁反制、国家科技战略、科技外交、颠覆性技术预见 |
| **海洋** | 绿色航运、无人船艇、深海探测、海上风电、海洋通信、极地装备、海底观测 |
| **生物** | 创新药与疫苗、基因编辑与细胞治疗、脑科学、生物安全、精准医疗、合成生物学 |
| **先进制造** | 工业机器人、人形机器人、数字孪生工厂、高端装备、精密加工、工业母机 |
| **航天** | 商业航天、卫星星座、深空探测、载人航天、可重复火箭、太空资源利用 |
| **航空** | 无人机与城市空中交通、低空经济、航电与飞控、绿色航空燃料、临近空间 |
| **新材料** | 高性能复合材料、能源材料、半导体材料、纳米与超导、碳材料、生物医用材料 |

### 话题模式（不止于领域）

除了按领域订阅，还支持**按话题跨领域检索**。例如问「无人机有什么新闻」，
它会扫遍全部十个领域——因为无人机在防务、航空、海洋、能源、先进制造里都有。

实测「无人机」一天的分布：**防务 26 条 · 能源 5 · 海洋 4 · 航空 3 ·
科技战略 3 · 先进制造 2 · 信息 1 · 航天 1**。
只查「航空」会漏掉 42 条——这是多数同类工具会犯的错。

检索后还会区分**核心条目**（无人机是主角）与**旁及条目**（无人机只是事件要素），分组呈现。

### 安装

**方式一：从 SkillHub 安装（上架名「全球科技要闻简报」）**
<https://skillhub.cn/skills/user_84b3ceb3/teko-tech-news-sum>

**方式二：从 GitHub 手动安装** —— 把本仓库放到你的 skill 目录即可：

```bash
# WorkBuddy / 兼容 agentskills.io 的客户端
git clone https://github.com/<你的账号>/tech-frontier-headlines.git \
  ~/.workbuddy/skills/tech-frontier-headlines
```

也可以直接下载 ZIP 解压后重命名目录。**零依赖**，不需要 `pip install` 任何东西。

> **命令里的 `python` 按平台调整**：Windows 用 `python` 或 `py`；
> **macOS / Linux 用 `python3`**（很多系统没有 `python` 这个命令）。
> 先跑 `python3 --version || python --version || py --version` 探测一下。

### 首次配置

```bash
python3 scripts/feed.py --init     # 生成配置文件（Windows 上把 python3 换成 python）
python3 scripts/feed.py --check    # 环境自检：数据源、feed 条数、记忆状态
```

### 常用命令

```bash
# 取两个领域的头条
python scripts/feed.py --domains 防务,能源 --limit 10

# 支持自然语言别名，「军工,核能」会自动映射到「防务,能源」
python scripts/feed.py --domains 军工,核能

# 话题模式：跨全部十个领域检索某个话题（如「无人机」「可控核聚变」）
python scripts/feed.py --keyword 无人机,无人系统,UAV,drone,eVTOL

# 增量：只取没推过的
python scripts/feed.py --domains 信息 --since-last

# 生成可分享 HTML 日报
python scripts/feed.py --domains 防务,能源 --limit 12 --format json --out data.json
python scripts/render.py --input data.json --out brief.html --top 5

# 推送到微信（先填 memory/preferences.json 里的 token）
python scripts/push.py --input data.json --brief-url https://你的日报链接
python scripts/push.py --test                        # 测通道
python scripts/push.py --input data.json --dry-run   # 只看要发什么
```

**也可以完全不用脚本**——直接让智能体读 `https://news.tekoai.net/index.json` 即可，
技能里的流程说明本身就是完整的（脚本只是让增量比对和记忆更稳）。

### 意图路由（一句话记住）

- **「今天有什么大事」** → `global-top.json`（按评分倒序，什么最重要）
- **「最新的」** → `latest-24h.json`（按时间倒序，什么最新）
- **某领域** → `category/{slug}.json`；**某话题/人物** → 跨全部 feed 用 `--keyword`

### 五种输出形态

1. **速览** —— 5 条，每条一句话，碎片时间看
2. **标准简报** —— 15 条，按领域分组，含摘要与「值得关注的点」
3. **单条深挖** —— 摘要 / 关键信息 / 背景上下文 / 潜在影响 / 后续可关注，五段结构化
4. **增量模式** —— 只讲相比上次新增了什么
5. **可分享 HTML 日报** —— 自包含单文件，无外部依赖，可直接转发或存档

**微信推送**是精简卡片（Top 3–5 条标题 + 评分 + 完整日报链接）——
微信适合「扫一眼」，完整内容放 HTML，不塞长文本。

### 推送通道

支持 PushPlus / Server酱 / 企业微信群机器人 / 飞书 / 邮件，
**主通道 + 备用链自动切换**，全部失败会暂存到待重试队列不丢消息。
配置方法与免费额度见 `references/push-channels.md`。

> 推荐组合：**PushPlus 为主**（直达个人微信，200 条/天免费）+ **Server酱 备用**（10 条/天）。

### 记忆机制

技能会在 `memory/` 下维护：

- `preferences.json` —— 关注领域、输出偏好、推送配置
- `pushed.jsonl` —— 已推条目流水，用于增量
- `feedback.jsonl` —— 你对条目的反馈（「这条好」「别给我这类」）

**只存本地、不上传**。分发时该目录内容为空白（仓库里只保留 `.gitkeep`）。

### 质量约束（内置的「不偷懒」机制）

| 借口 | 正确做法 |
|---|---|
| 网络不通，凭记忆写几条 | **绝不编造新闻**，明确告知失败 |
| 用户没说关注什么，默认给 AI | 读记忆 → 读宿主画像 → 才问一次 |
| 摘要太长，自己重写一遍 | **摘要原样引用**，要浓缩就标注 |
| 只找到 9 条，凑到 15 条 | 给 9 条并说明，**精选的价值在于少而准** |
| 数据源没这个领域，随便搜两条 | 可以补，但**必须标注非本数据源** |
| 重复项先放着 | 服务端已过滤；客户端再兜底，`DUP` 一律剔除 |
| 用 boring / falcon 这种泛词做关键词 | 泛词会捞进大量无关新闻，只用专属组合词 |

### 目录结构

```
├── SKILL.md                      # 技能主流程（智能体读这个）
├── README.md                     # 本文件
├── LICENSE                       # MIT
├── references/
│   ├── data-source.md            # 数据源接口与字段详解、评分口径、意图路由表
│   ├── domains.md                # 十大领域定义与关键词映射
│   ├── templates.md              # 各输出形态的完整模板
│   └── push-channels.md          # 推送通道配置与故障切换
├── scripts/
│   ├── feed.py                   # 抓取 + 筛选 + 增量 + 记忆（纯标准库）
│   ├── render.py                 # 生成可分享 HTML 日报（纯标准库）
│   └── push.py                   # 多通道推送（纯标准库）
├── assets/
│   └── preferences.template.json # 配置模板，--init 时复制到 memory/
└── memory/                       # 运行时生成：偏好、已推流水、反馈
    └── .gitkeep
```

### 边界与降级

| 情况 | 处理 |
|---|---|
| 数据源不可达 | 明确告知失败原因，询问是否改用联网搜索模式（结果标注非本数据源） |
| 某领域当天 0 条 | 如实说明，**不用其他领域凑数** |
| 领域不在这十个里 | 映射到最接近的领域并说明映射关系，缺口部分联网补充 |
| 没有 Python 环境 | 纯提示词模式，直接读 JSON 接口，流程不变 |

### 隐私说明

本技能**不含任何密钥或个人信息**，仓库内所有凭据字段均为空值模板。

### 许可与致谢

- 许可：**MIT**，可自由使用、修改、再分发
- 数据来源：[news.tekoai.net](https://news.tekoai.net)
- 输出结构设计参考了 Kagi News 的分段式展开（Summary / Context / Impact）
  与 addyosmani/agent-skills 的反理性化表方法

---

## English

### What makes it different

| Typical news skill | This skill |
|---|---|
| Dumps headlines, 40–60% relevant | **10 hard-tech domains + LLM scoring**, only items above the bar |
| Consumer trends / viral angle | **Frontier tech & industrial intelligence** (defense, energy, tech policy, advanced manufacturing…) |
| Single domain (AI or finance only) | **Ten hard-tech domains**, combinable |
| Gives a list, never says why | Every item carries a **0–100 score**, **major/minor category**, **keywords** and the **original source link** |
| Starts from scratch each time | **Interest memory + incremental mode** ("what's new since last time") |
| One output shape | Chat briefing / shareable HTML daily / WeChat push |

### Data source

All items come from **news.tekoai.net**, which continuously scans **thousands of trusted sites**
(newswires, trade media, institutional sites, authoritative industry outlets). Every item is processed
by a frontier LLM: Chinese summary, domain classification, 0–100 value score, keyword extraction.

- **De-duplicated server-side**: only `duplicate_checked = 1` and `score_class != 'DUP'` items are published
- **Ten domains × dozens of sub-fields**, e.g. `能源—先进核裂变/第四代核电`
- **Refreshed every 30 minutes**; direct access from mainland China, no proxy needed
- **Three formats per channel**: `.json` (agents), `.xml` (RSS readers), `.html` (search indexing)

> Every item ships with the signal for *why it was selected* and a clickable **source link** you can verify.

### Domains

| Domain | Covers |
|---|---|
| **Defense** | Combat aircraft, missiles & hypersonics, autonomous systems, arms trade, military strategy, space military, C4ISR |
| **Energy** | Advanced fission, fusion, storage, renewables, hydrogen, oil & gas tech, smart grid, CCUS |
| **Information** | LLMs & generative AI, AI chips & compute, semiconductors, quantum, cybersecurity, 6G, optical comms |
| **Tech Strategy** | Export controls, investment screening, sanctions, national S&T strategy, tech diplomacy |
| **Marine** | Green shipping, unmanned vessels, deep-sea exploration, offshore wind, polar equipment |
| **Biology** | Innovative drugs & vaccines, gene editing, brain science, biosafety, synthetic biology |
| **Advanced Manufacturing** | Industrial & humanoid robots, digital-twin factories, precision machining, machine tools |
| **Aerospace** | Commercial space, satellite constellations, deep space, human spaceflight, reusable rockets |
| **Aviation** | UAV & urban air mobility, low-altitude economy, avionics, SAF, near-space |
| **New Materials** | Composites, energy materials, semiconductor materials, nano & superconductors, carbon materials |

### Install

**Option 1 — SkillHub** (listed as 「全球科技要闻简报」):
<https://skillhub.cn/skills/user_84b3ceb3/teko-tech-news-sum>

**Option 2 — from GitHub**: drop this repo into your skills directory.

```bash
# WorkBuddy / agentskills.io-compatible clients
git clone https://github.com/<your-account>/tech-frontier-headlines.git \
  ~/.workbuddy/skills/tech-frontier-headlines
```

Zero dependencies — no `pip install` required. Python 3.7+ only if you use the scripts.

> Use `python3` on macOS/Linux (many systems have no `python` alias); `python` or `py` on Windows.

### Setup

```bash
python3 scripts/feed.py --init     # create config
python3 scripts/feed.py --check    # self-test: source reachability, feed counts, memory state
```

### Common commands

```bash
python scripts/feed.py --domains 防务,能源 --limit 10     # by domain
python scripts/feed.py --keyword 无人机,UAV,drone          # by topic (cross-domain)
python scripts/feed.py --domains 信息 --since-last         # incremental
python scripts/feed.py --domains 防务 --limit 12 --format json --out data.json
python scripts/render.py --input data.json --out brief.html --top 5
python scripts/push.py --input data.json --brief-url https://your-brief-url
```

You can also skip the scripts entirely — just let the agent read
`https://news.tekoai.net/index.json`; the workflow in `SKILL.md` is self-contained.

### Intent routing (the one thing to remember)

- **"What's big today?"** → `global-top.json` (score desc — what matters most)
- **"What's newest?"** → `latest-24h.json` (time desc — what's newest)
- **A domain** → `category/{slug}.json`; **a topic or entity** → scan all feeds with `--keyword`

### Output shapes

1. **Quick scan** — 5 items, one line each
2. **Standard briefing** — 15 items grouped by domain, with summary + "why it matters"
3. **Deep dive** — summary / key facts / background / impact / what to watch next
4. **Incremental** — only what's new since last run
5. **Shareable HTML daily** — single self-contained file, no external assets

### Memory

`memory/preferences.json`, `memory/pushed.jsonl`, `memory/feedback.jsonl` — **local only, never uploaded**.
Shipped empty (`.gitkeep` only).

### Anti-rationalization guardrails

| Excuse | Correct behavior |
|---|---|
| "Network is down, I'll write a few from memory" | **Never fabricate news** — report the failure |
| "User didn't say a domain, default to AI" | Memory → host profile → then ask once |
| "Summary is too long, I'll rewrite it" | **Quote it verbatim**, or label it as condensed |
| "Only 9 items, pad to 15" | Ship 9 and say so — **curation means fewer but better** |
| "Source has no such domain, I'll grab some" | Allowed, but **must be labeled as off-source** |
| "Keep the duplicate, it's still news" | Drop `DUP` items |
| "Use generic words like boring / falcon as keywords" | Generic words pull in noise — use entity-specific terms (SpaceX / Starlink) |

### Privacy

Contains **no secrets or personal data**; every credential field is an empty placeholder.

### License & credits

- License: **MIT**
- Data source: [news.tekoai.net](https://news.tekoai.net)
- Output structure inspired by Kagi News (Summary / Context / Impact)
  and the anti-rationalization table method from addyosmani/agent-skills

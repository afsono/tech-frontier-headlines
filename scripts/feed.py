#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tech-frontier-headlines / feed.py

从 news.tekoai.net 拉取科技前沿头条，按领域筛选、去重、做增量比对，并维护记忆文件。

设计约束：**只用 Python 标准库**，不需要 pip install 任何东西。
这样在 Claude Code / Codex / Cursor / WorkBuddy 等任何支持 skill 的环境里都能直接跑。

用法:
    python feed.py --check                                  # 环境自检
    python feed.py --domains 防务,能源 --limit 10            # 取两个领域
    python feed.py --domains 信息 --limit 5 --format text
    python feed.py --since-last --domains 防务               # 增量：只取新增
    python feed.py --domains 能源 --limit 10 --mark-sent     # 取出并记入已推流水
    python feed.py --no-proxy --domains 能源                 # 强制直连（绕过系统代理）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
MEM_DIR = SKILL_DIR / "memory"
PREFS_FILE = MEM_DIR / "preferences.json"
PUSHED_FILE = MEM_DIR / "pushed.jsonl"
FEEDBACK_FILE = MEM_DIR / "feedback.jsonl"

# 数据源根地址，可用环境变量覆盖
BASE_URL = os.environ.get("TECH_FRONTIER_BASE", "https://news.tekoai.net").rstrip("/")

# 标准领域名 -> feed slug
DOMAIN_SLUG = {
    "防务": "defense",
    "能源": "energy",
    "信息": "information",
    "科技战略": "tech-strategy",
    "海洋": "marine",
    "生物": "biology",
    "先进制造": "advanced-manufacturing",
    "航天": "aerospace",
    "航空": "aviation",
    "新材料": "new-materials",
}
SLUG_DOMAIN = {v: k for k, v in DOMAIN_SLUG.items()}

# 通用 feed（不分领域）。键是 --feed 取值。
GENERIC_FEEDS = {
    "top": ("global-top", "全球科技头条：近 24h、score>40、按评分倒序（最重要的在前）"),
    "latest": ("latest-24h", "最新科技新闻：近 24h、score>40、按发布时间倒序（最新的在前）"),
}

# 意图 → 该读哪个文件。这张表是给模型快速定位用的，见 SKILL.md 同名小节。
ROUTING = [
    ("不知道有什么 / 先摸底", "index.json", "总索引：全部 feed 清单 + 字段说明"),
    ("通用科技新闻、今天有什么大事", "global-top.json", "按评分倒序，最重要的在前 → --feed top"),
    ("最新动态、持续更新、刚发生了什么", "latest-24h.json", "按时间倒序，最新的在前 → --feed latest"),
    ("某个领域（防务/能源/…）", "category/{slug}.json", "该领域专用 → --domains 领域名"),
    ("某个话题（无人机/可控核聚变/某公司）", "跨全部 feed 扫", "话题横跨多领域 → --keyword"),
]

# 常见别名 -> 标准领域名（对应 references/domains.md 的关键词映射）
ALIASES = {
    "军工": "防务", "国防": "防务", "武器装备": "防务", "军事": "防务", "安全防务": "防务",
    "电力": "能源", "核能": "能源", "核电": "能源", "新能源": "能源", "储能": "能源", "石油": "能源",
    "ai": "信息", "人工智能": "信息", "大模型": "信息", "芯片": "信息", "半导体": "信息",
    "量子": "信息", "网络安全": "信息", "算力": "信息", "计算": "信息", "通信": "信息",
    "战略": "科技战略", "科技政策": "科技战略", "出口管制": "科技战略", "科技竞争": "科技战略",
    "船舶": "海洋", "航运": "海洋", "深海": "海洋", "极地": "海洋",
    "生物技术": "生物", "医药": "生物", "生命科学": "生物", "医疗": "生物", "新药": "生物",
    "制造": "先进制造", "机器人": "先进制造", "智能制造": "先进制造", "工业": "先进制造",
    "太空": "航天", "卫星": "航天", "火箭": "航天", "商业航天": "航天",
    "飞机": "航空", "民航": "航空", "无人机": "航空", "低空": "航空", "低空经济": "航空",
    "材料": "新材料", "石墨烯": "新材料", "复合材料": "新材料",
}

# score_class 中表示"重复项"的等级，必须剔除
DUP_CLASSES = {"DUP", "dup"}


# --------------------------------------------------------------------------- #
# 输出编码（Windows 控制台默认 GBK，中文会乱码）
# --------------------------------------------------------------------------- #
def _fix_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def log(*a) -> None:
    print(*a, file=sys.stderr)


# --------------------------------------------------------------------------- #
# HTTP：先直连，失败再走系统代理（很多环境的本地代理转发不了大响应体）
# --------------------------------------------------------------------------- #
def http_get(url: str, timeout: int = 25, force_direct: bool = False,
             retries: int = 3) -> bytes:
    """取一个 URL。返回 bytes。

    双层容错：
      1. 先直连、失败再走系统代理（很多本地代理会重置连接，反过来也常见）
      2. 整体重试若干轮（网络抖动、代理重启导致的 DNS/502 是真实会发生的）

    两条通路、多轮重试都失败才抛异常 —— 这样在代理环境和直连环境下都能用。
    """
    attempts = [("直连", None)] if force_direct else [("直连", None), ("系统代理", {})]
    last_err: Exception | None = None

    for rnd in range(1, retries + 1):
        for label, proxies in attempts:
            try:
                if proxies is None:
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                else:
                    opener = urllib.request.build_opener()  # 默认读取环境变量
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "tech-frontier-headlines/1.0 (+skill)",
                        "Accept": "application/json, application/xml, text/html, */*",
                        "Cache-Control": "no-cache",
                    },
                )
                with opener.open(req, timeout=timeout) as resp:
                    data = resp.read()
                log(f"  [ok] 第{rnd}轮 {label} 取回 {len(data)} 字节")
                return data
            except Exception as e:  # noqa: BLE001
                last_err = e
                log(f"  [!!] 第{rnd}轮 {label} 失败: {type(e).__name__}: {str(e)[:110]}")
        if rnd < retries:
            time.sleep(1.5 * rnd)   # 1.5s / 3s 退避，给代理重启留时间

    raise RuntimeError(f"无法访问 {url}（直连与代理、共 {retries} 轮重试均失败）：{last_err}")


def get_json(url: str, timeout: int = 25, force_direct: bool = False) -> dict:
    return json.loads(http_get(url, timeout, force_direct).decode("utf-8"))


def bust(url: str) -> str:
    """加时间戳绕过 CDN 缓存（站点设了 max-age=300）。"""
    ts = int(datetime.now(timezone.utc).timestamp())
    return f"{url}{'&' if '?' in url else '?'}t={ts}"


# --------------------------------------------------------------------------- #
# 记忆
# --------------------------------------------------------------------------- #
def ensure_mem() -> None:
    MEM_DIR.mkdir(parents=True, exist_ok=True)


def load_prefs() -> dict:
    if PREFS_FILE.exists():
        try:
            return json.loads(PREFS_FILE.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            log(f"  [!!] preferences.json 解析失败，按空配置处理: {e}")
    return {}


def save_prefs(prefs: dict) -> None:
    ensure_mem()
    PREFS_FILE.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")


TEMPLATE_FILE = SKILL_DIR / "assets" / "preferences.template.json"


def init_prefs(force: bool = False) -> int:
    """从模板创建 memory/preferences.json。首次使用跑一次即可。"""
    ensure_mem()
    if PREFS_FILE.exists() and not force:
        print(f"配置已存在，未覆盖: {PREFS_FILE}")
        print("（要强制重置用 --init --force，注意会清掉已填的 token）")
        return 0
    if not TEMPLATE_FILE.exists():
        print(f"模板文件缺失: {TEMPLATE_FILE}", file=sys.stderr)
        return 2
    PREFS_FILE.write_text(TEMPLATE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"已创建配置: {PREFS_FILE}")
    print("下一步：")
    print("  1. 填 domains（你关注的领域），或直接跑 feed.py 时用 --save-domains 自动写入")
    print("  2. 想用微信推送就填 push.channels.pushplus.token，"
          "接入方法见 references/push-channels.md")
    print("  3. python scripts/feed.py --check 验证环境")
    return 0


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:  # noqa: BLE001
                continue
    return out


def append_jsonl(path: Path, rows: list[dict]) -> None:
    ensure_mem()
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def pushed_urls() -> set[str]:
    return {r.get("url", "") for r in read_jsonl(PUSHED_FILE) if r.get("url")}


# --------------------------------------------------------------------------- #
# 领域解析
# --------------------------------------------------------------------------- #
def resolve_domains(raw: str | None, prefs: dict) -> list[str]:
    """把用户输入（或记忆里的偏好）解析成标准领域名列表。"""
    if not raw:
        saved = prefs.get("domains") or []
        if saved:
            log(f"  使用记忆里的关注领域: {saved}")
            return [d for d in saved if d in DOMAIN_SLUG]
        return list(DOMAIN_SLUG)  # 无偏好 → 全部领域

    out: list[str] = []
    for token in raw.replace("，", ",").replace("、", ",").split(","):
        t = token.strip()
        if not t:
            continue
        if t in DOMAIN_SLUG:
            name = t
        elif t.lower() in ALIASES:
            name = ALIASES[t.lower()]
        else:
            name = None
            for alias, std in ALIASES.items():
                if alias in t.lower() or t in alias:
                    name = std
                    break
        if name and name not in out:
            out.append(name)
        elif not name:
            log(f"  [!!] 无法识别领域「{t}」，已跳过。可用: {' / '.join(DOMAIN_SLUG)}")
    return out or list(DOMAIN_SLUG)


# --------------------------------------------------------------------------- #
# 抓取
# --------------------------------------------------------------------------- #
def match_keywords(item: dict, keywords: list[str]) -> bool:
    """话题关键词过滤：命中 title / summary / category / keywords 任一即算命中。

    用于「某个话题」类查询（如"无人机""可控核聚变"）——
    话题常常横跨多个领域，且可能是歧义词，所以按关键词跨领域检索最稳。
    """
    if not keywords:
        return True
    haystack = " ".join([
        str(item.get("title") or ""),
        str(item.get("summary") or ""),
        str(item.get("category") or ""),
        str(item.get("category_minor") or ""),
        " ".join(item.get("keywords") or []),
    ]).lower()
    return any(k.lower() in haystack for k in keywords if k)


def normalize(item: dict, domain: str) -> dict:
    return {
        "id": item.get("id"),
        "title": (item.get("title") or "").strip(),
        "summary": (item.get("summary") or "").strip(),
        "category": item.get("category") or "",
        "category_major": item.get("category_major") or domain,
        "category_minor": item.get("category_minor") or "",
        "url": item.get("url") or "",
        "source": item.get("source") or "",
        "publish_time": item.get("publish_time") or "",
        "score": item.get("score") if isinstance(item.get("score"), int) else 0,
        "score_class": (item.get("score_class") or "").strip(),
        "lang": item.get("lang") or "",
        "keywords": item.get("keywords") or [],
        "domain": domain,
    }


def _filter_items(items: list[dict], min_score: int, keywords: list[str] | None,
                  default_domain: str, label: str) -> list[dict]:
    """共用的筛选管线：剔 DUP、卡评分、话题匹配、去缺字段、按分排序。"""
    rows: list[dict] = []
    dropped_dup = dropped_score = dropped_empty = dropped_kw = 0

    for it in items:
        cls = (it.get("score_class") or "").strip()
        if cls in DUP_CLASSES:                       # DUP = 重复项，必须剔除
            dropped_dup += 1
            continue
        sc = it.get("score") if isinstance(it.get("score"), int) else 0
        if sc <= min_score:                           # 评分不达标，不凑数
            dropped_score += 1
            continue
        if keywords and not match_keywords(it, keywords):   # 话题不匹配
            dropped_kw += 1
            continue
        # 通用 feed 里每条自带 category_major，用它当领域更准
        dom = it.get("category_major") or default_domain
        n = normalize(it, dom)
        if not n["title"] or not n["url"]:            # 无标题/无链接的不可用
            dropped_empty += 1
            continue
        rows.append(n)

    rows.sort(key=lambda r: (r["score"], r["publish_time"]), reverse=True)
    log(f"[{label}] 原始 {len(items)} 条 → 可用 {len(rows)} 条"
        f"（剔除 DUP {dropped_dup} / 低分 {dropped_score} / 缺字段 {dropped_empty}"
        + (f" / 话题不匹配 {dropped_kw}" if keywords else "") + "）")
    return rows


def fetch_domain(domain: str, min_score: int, limit: int, force_direct: bool,
                 timeout: int, keywords: list[str] | None = None) -> list[dict]:
    """取某个领域的分类 feed。"""
    slug = DOMAIN_SLUG[domain]
    url = bust(f"{BASE_URL}/category/{slug}.json")
    log(f"[{domain}] GET {url}")
    data = get_json(url, timeout=timeout, force_direct=force_direct)
    rows = _filter_items(data.get("items") or [], min_score, keywords, domain, domain)
    return rows[:limit] if limit > 0 else rows


def fetch_generic(feed_key: str, min_score: int, limit: int, force_direct: bool,
                  timeout: int, keywords: list[str] | None = None,
                  sort_by_time: bool = False) -> list[dict]:
    """取通用 feed（不分领域）。

    · top    -> /global-top.json   全球科技头条，**按评分倒序**，最重要的在前
    · latest -> /latest-24h.json   最新科技新闻，**按发布时间倒序**，最新的在前

    这是「通用科技新闻需求」和「看最新动态」两条最快路径。
    """
    slug, desc = GENERIC_FEEDS[feed_key]
    url = bust(f"{BASE_URL}/{slug}.json")
    log(f"[{feed_key}] GET {url}")
    log(f"[{feed_key}] {desc}")
    data = get_json(url, timeout=timeout, force_direct=force_direct)
    rows = _filter_items(data.get("items") or [], min_score, keywords, "", feed_key)
    if sort_by_time:   # "看最新"要按时间倒序，不是按评分
        rows.sort(key=lambda r: r["publish_time"], reverse=True)
    return rows[:limit] if limit > 0 else rows


# --------------------------------------------------------------------------- #
# 自检
# --------------------------------------------------------------------------- #
def do_check(force_direct: bool, timeout: int) -> int:
    print("=" * 72)
    print("tech-frontier-headlines 环境自检")
    print("=" * 72)
    ok = True

    print(f"\n[1] 数据源: {BASE_URL}")
    try:
        idx = get_json(bust(f"{BASE_URL}/index.json"), timeout=timeout, force_direct=force_direct)
        print(f"    ✔ 可达｜更新于 {idx.get('generated_at')}｜"
              f"刷新间隔 {idx.get('refresh_interval_minutes')} 分钟｜"
              f"共 {idx.get('feed_count')} 个 feed")
        print("    各 feed 条数：")
        for f in idx.get("feeds", []):
            print(f"      - {f.get('name_zh', ''):<24} {f.get('count', 0):>4} 条   {f.get('feed_id')}")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"    ✘ 不可达：{type(e).__name__}: {str(e)[:200]}")
        print("      → 降级：告知用户失败原因，询问是否改用联网搜索模式（结果需标注非本数据源）")

    print(f"\n[2] 记忆目录: {MEM_DIR}")
    if MEM_DIR.exists():
        prefs = load_prefs()
        print(f"    ✔ 存在")
        print(f"      关注领域 : {prefs.get('domains') or '(未设置，将取全部领域)'}")
        print(f"      输出偏好 : {prefs.get('style') or '(未设置)'}")
        print(f"      推送通道 : {(prefs.get('push') or {}).get('channel') or '(未配置)'}")
        print(f"      已推流水 : {len(read_jsonl(PUSHED_FILE))} 条")
        print(f"      反馈记录 : {len(read_jsonl(FEEDBACK_FILE))} 条")
    else:
        print("    · 尚未创建 → 执行 python scripts/feed.py --init 初始化配置")

    print("\n[3] 意图 → 该读哪个文件（快速定位表）")
    print(f"    {'用户意图':<30} {'文件':<24} 说明")
    print("    " + "-" * 96)
    for intent, path, note in ROUTING:
        print(f"    {intent:<30} {path:<24} {note}")

    print("\n[4] 可用领域")
    for name, slug in DOMAIN_SLUG.items():
        print(f"      {name:<8} {BASE_URL}/category/{slug}.json")

    print("\n[5] 结论")
    print("    " + ("✔ 环境正常，可以开始使用" if ok else
                    "✘ 数据源不可达 —— 不要编造内容，先告知用户并给出手动访问地址"))
    print()
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main() -> int:
    _fix_stdout()
    ap = argparse.ArgumentParser(
        description="从 news.tekoai.net 拉取科技前沿头条（零依赖）")
    ap.add_argument("--domains", help="领域，逗号分隔。可用: " + " / ".join(DOMAIN_SLUG))
    ap.add_argument("--feed", choices=["top", "latest", "all"],
                    help="通用 feed：top=全球科技头条（按评分倒序，默认）；"
                         "latest=最新科技新闻（按时间倒序）；"
                         "all=扫描全部 12 个 feed 并去重（话题/主体追踪推荐，最全）")
    ap.add_argument("--keyword", help="话题关键词，逗号分隔（跨 feed 检索）。"
                                      "例：无人机,无人系统,UAV。与 --domains/--feed 可同时使用")
    ap.add_argument("--limit", type=int, default=0, help="每个领域最多几条（0=不限）")
    ap.add_argument("--min-score", type=int, default=40, help="评分下限，默认 40（严格大于）")
    ap.add_argument("--since-last", action="store_true", help="增量模式：排除已推过的条目")
    ap.add_argument("--mark-sent", action="store_true", help="把本次结果记入已推流水（供增量用）")
    ap.add_argument("--save-domains", action="store_true", help="把本次领域写入记忆，下次默认使用")
    ap.add_argument("--format", choices=["json", "text"], default="text", help="输出格式")
    ap.add_argument("--out", help="结果写入文件（UTF-8）")
    ap.add_argument("--no-proxy", action="store_true", help="强制直连，绕过系统代理")
    ap.add_argument("--timeout", type=int, default=25, help="单次请求超时秒数")
    ap.add_argument("--check", action="store_true", help="只做环境自检")
    ap.add_argument("--init", action="store_true", help="首次使用：从模板创建 memory/preferences.json")
    ap.add_argument("--force", action="store_true", help="配合 --init，强制覆盖已有配置")
    args = ap.parse_args()

    if args.init:
        return init_prefs(args.force)

    if args.check:
        return do_check(args.no_proxy, args.timeout)

    prefs = load_prefs()
    keywords = [k.strip() for k in (args.keyword or "").replace("，", ",").split(",") if k.strip()]
    if keywords:
        log(f"话题关键词: {keywords}")

    all_rows: list[dict] = []
    failures: list[str] = []
    scope_desc = ""

    # ---------- 决定读哪些 feed ----------
    # 优先级：--domains > --feed > 话题/主体追踪自动全扫 > 记忆里的关注领域 > 默认头条
    # 「通用科技新闻」应该走头条（按评分倒序），不是把十个领域全拉一遍。
    use_generic = args.feed
    if args.domains:
        domains = resolve_domains(args.domains, prefs)
        scope_desc = "领域 " + "、".join(domains)
    elif use_generic:
        domains = []
        scope_desc = {"top": "头条", "latest": "最新", "all": "全部 feed（去重）"}[use_generic]
    elif keywords:
        # 话题/主体追踪：只在 global-top 里找会漏掉仅存在于分类 feed 的条目，必须全扫
        use_generic = "all"
        domains = []
        scope_desc = "全部 feed（话题/主体追踪，自动全扫）"
    elif prefs.get("domains"):
        domains = [d for d in prefs["domains"] if d in DOMAIN_SLUG]
        scope_desc = "领域 " + "、".join(domains) + "（来自记忆）"
    else:
        use_generic = "top"          # 默认：通用科技新闻 → 头条
        domains = []
        scope_desc = "头条（默认：通用科技新闻）"

    if keywords:
        scope_desc += " · 话题 " + "/".join(keywords)
    log(f"检索范围: {scope_desc}")

    seen = pushed_urls() if args.since_last else set()
    if args.since_last:
        log(f"增量模式：已知已推 {len(seen)} 条")

    # ---------- 全部 feed 模式（话题/主体追踪） ----------
    if use_generic == "all":
        collected: dict[str, dict] = {}
        for key in ("top", "latest"):          # 先扫两个通用 feed
            try:
                for r in fetch_generic(key, args.min_score, 0, args.no_proxy,
                                       args.timeout, keywords,
                                       sort_by_time=(key == "latest")):
                    collected.setdefault(r["url"], r)
            except Exception as e:  # noqa: BLE001
                log(f"[{key}] 抓取失败: {type(e).__name__}: {str(e)[:150]}")
                failures.append(key)
        for d in DOMAIN_SLUG:                  # 再扫十个领域
            try:
                for r in fetch_domain(d, args.min_score, 0, args.no_proxy,
                                      args.timeout, keywords):
                    collected.setdefault(r["url"], r)
            except Exception as e:  # noqa: BLE001
                log(f"[{d}] 抓取失败: {type(e).__name__}: {str(e)[:150]}")
                failures.append(d)
        all_rows = list(collected.values())
        log(f"[all] 去重后共 {len(all_rows)} 条")
        if args.since_last and all_rows:
            before = len(all_rows)
            all_rows = [r for r in all_rows if r["url"] not in seen]
            if before != len(all_rows):
                log(f"[all] 增量过滤掉 {before - len(all_rows)} 条已推过的")

    # ---------- 通用 feed 路径 ----------
    elif use_generic:
        try:
            all_rows = fetch_generic(use_generic, args.min_score, args.limit, args.no_proxy,
                                     args.timeout, keywords, sort_by_time=(use_generic == "latest"))
        except Exception as e:  # noqa: BLE001
            log(f"[{use_generic}] 抓取失败: {type(e).__name__}: {str(e)[:150]}")
            failures.append(use_generic)
        if args.since_last and all_rows:
            before = len(all_rows)
            all_rows = [r for r in all_rows if r["url"] not in seen]
            if before != len(all_rows):
                log(f"[{use_generic}] 增量过滤掉 {before - len(all_rows)} 条已推过的")
    else:
        # ---------- 领域 feed 路径 ----------
        for d in domains:
            try:
                rows = fetch_domain(d, args.min_score, args.limit, args.no_proxy,
                                    args.timeout, keywords)
            except Exception as e:  # noqa: BLE001
                log(f"[{d}] 抓取失败: {type(e).__name__}: {str(e)[:150]}")
                failures.append(d)
                continue
            if args.since_last:
                before = len(rows)
                rows = [r for r in rows if r["url"] not in seen]
                if before != len(rows):
                    log(f"[{d}] 增量过滤掉 {before - len(rows)} 条已推过的")
            all_rows.extend(rows)

    # "看最新"要按时间倒序；其余按评分倒序
    if use_generic == "latest":
        all_rows.sort(key=lambda r: r["publish_time"], reverse=True)
    else:
        all_rows.sort(key=lambda r: (r["score"], r["publish_time"]), reverse=True)

    if not all_rows and not failures:
        log("提示：本次没有任何条目达到阈值。这是正常结果，不要为了有输出而降低标准。")

    payload = {
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "source": BASE_URL,
        "feed": use_generic or "category",
        "domains": domains,
        "keyword": keywords,
        "scope_desc": scope_desc,
        "failed_domains": failures,
        "min_score": args.min_score,
        "incremental": bool(args.since_last),
        "count": len(all_rows),
        "items": all_rows,
    }

    if args.format == "json":
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        lines = [
            f"# 全球科技前沿（{payload['generated_at']}）",
            f"来源 {BASE_URL}　{scope_desc}　共 {len(all_rows)} 条",
            "",
        ]
        if failures:
            lines.append(f"⚠️ 以下领域抓取失败：{'、'.join(failures)}")
            lines.append("")
        for i, r in enumerate(all_rows, 1):
            lines.append(f"{i}. [{r['score']}分 {r['score_class']}] {r['title']}")
            lines.append(f"   {r['domain']}·{r['category_minor']}　{r['source']}　{r['publish_time']}")
            if r["summary"]:
                lines.append(f"   {r['summary'][:200]}")
            lines.append(f"   {r['url']}")
            lines.append("")
        text = "\n".join(lines)

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        log(f"已写入 {args.out}")
    else:
        print(text)

    if args.mark_sent and all_rows:
        now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
        append_jsonl(PUSHED_FILE, [
            {"url": r["url"], "title": r["title"], "score": r["score"],
             "domain": r["domain"], "sent_at": now}
            for r in all_rows
        ])
        log(f"已记入已推流水 {len(all_rows)} 条")

    if args.save_domains and args.domains:
        prefs["domains"] = domains
        save_prefs(prefs)
        log(f"已把关注领域写入记忆: {domains}")

    return 1 if failures and not all_rows else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)

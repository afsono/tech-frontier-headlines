#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tech-frontier-headlines / push.py

把简报推送到微信 / 飞书 / 邮件等通道。**只用 Python 标准库**。

设计要点：
  · 通道可插拔 —— 业务逻辑不关心底层是哪家，某通道挂了换一个即可
  · 主通道 + 备用链 —— 主通道失败自动依次重试
  · 失败兜底 —— 全部失败就暂存到 memory/pending_push.jsonl，下次重试
  · 微信内容只发精简卡片（Top N 标题+评分）+ 完整日报链接，不塞全文

用法:
    python push.py --input data.json --test          # 发一条测试消息
    python push.py --input data.json                 # 推送简报
    python push.py --input data.json --dry-run       # 只打印要发的内容，不真发
    python push.py --input data.json --brief-url https://xxx/brief.html
    python push.py --input data.json --top 5 --channel serverchan
"""

from __future__ import annotations

import argparse
import json
import smtplib
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from email.header import Header
from email.mime.text import MIMEText
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
MEM_DIR = SKILL_DIR / "memory"
PREFS_FILE = MEM_DIR / "preferences.json"
PENDING_FILE = MEM_DIR / "pending_push.jsonl"

CN_TZ = timezone(timedelta(hours=8))

# 各通道的每日免费额度（仅用于提醒，不强制拦截）
QUOTA_HINT = {
    "pushplus": "200 条/天",
    "serverchan": "10 条/天（免费版）",
    "wecom_bot": "额度宽松",
    "feishu": "额度宽松",
    "email": "视邮箱服务商",
}


def log(*a) -> None:
    print(*a, file=sys.stderr)


def load_prefs() -> dict:
    if PREFS_FILE.exists():
        try:
            return json.loads(PREFS_FILE.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            log(f"[!!] preferences.json 解析失败: {e}")
    return {}


def http_post(url: str, payload: dict, timeout: int = 20) -> tuple[bool, str]:
    """POST JSON。返回 (是否成功, 响应片段)。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "tech-frontier-headlines/1.0"},
    )
    for label, use_proxy in (("直连", False), ("系统代理", True)):
        try:
            opener = (urllib.request.build_opener()
                      if use_proxy else
                      urllib.request.build_opener(urllib.request.ProxyHandler({})))
            with opener.open(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", "replace")
            log(f"    [{label}] HTTP {resp.status}: {text[:160]}")
            return True, text
        except Exception as e:  # noqa: BLE001
            log(f"    [{label}] 失败: {type(e).__name__}: {str(e)[:120]}")
    return False, ""


def http_post_form(url: str, form: dict, timeout: int = 20) -> tuple[bool, str]:
    """POST 表单（Server酱用这个）。"""
    body = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    for label, use_proxy in (("直连", False), ("系统代理", True)):
        try:
            opener = (urllib.request.build_opener()
                      if use_proxy else
                      urllib.request.build_opener(urllib.request.ProxyHandler({})))
            with opener.open(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", "replace")
            log(f"    [{label}] HTTP {resp.status}: {text[:160]}")
            return True, text
        except Exception as e:  # noqa: BLE001
            log(f"    [{label}] 失败: {type(e).__name__}: {str(e)[:120]}")
    return False, ""


# --------------------------------------------------------------------------- #
# 通道实现
# --------------------------------------------------------------------------- #
def send_pushplus(cfg: dict, title: str, content: str) -> bool:
    token = (cfg or {}).get("token")
    if not token:
        log("    pushplus 未配置 token")
        return False
    ok, txt = http_post("https://www.pushplus.plus/send", {
        "token": token, "title": title, "content": content, "template": "markdown",
    })
    # 接口返回 200 但 body 里 code!=200 也算失败
    if ok:
        try:
            if json.loads(txt).get("code") not in (200, "200"):
                log("    pushplus 返回非成功 code")
                return False
        except Exception:  # noqa: BLE001
            pass
    return ok


def send_serverchan(cfg: dict, title: str, content: str) -> bool:
    sk = (cfg or {}).get("sendkey")
    if not sk:
        log("    serverchan 未配置 sendkey")
        return False
    ok, txt = http_post_form(f"https://sctapi.ftqq.com/{sk}.send",
                             {"title": title, "desp": content})
    if ok:
        try:
            if json.loads(txt).get("code") not in (0, "0"):
                log("    serverchan 返回非成功 code")
                return False
        except Exception:  # noqa: BLE001
            pass
    return ok


def send_wecom_bot(cfg: dict, title: str, content: str) -> bool:
    hook = (cfg or {}).get("webhook")
    if not hook:
        log("    wecom_bot 未配置 webhook")
        return False
    ok, _ = http_post(hook, {
        "msgtype": "markdown",
        "markdown": {"content": f"**{title}**\n{content}"},
    })
    return ok


def send_feishu(cfg: dict, title: str, content: str) -> bool:
    hook = (cfg or {}).get("webhook")
    if not hook:
        log("    feishu 未配置 webhook")
        return False
    ok, _ = http_post(hook, {
        "msg_type": "text",
        "content": {"text": f"{title}\n\n{content}"},
    })
    return ok


def send_email(cfg: dict, title: str, content: str) -> bool:
    cfg = cfg or {}
    need = ["smtp_host", "user", "pass"]
    if any(not cfg.get(k) for k in need) or not cfg.get("to"):
        log("    email 未配置齐全（需要 smtp_host/user/pass/to）")
        return False
    port = int(cfg.get("smtp_port", 465))
    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = cfg["user"]
    msg["To"] = ", ".join(cfg["to"])
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg["smtp_host"], port, context=ctx, timeout=25) as s:
            s.login(cfg["user"], cfg["pass"])
            s.sendmail(cfg["user"], cfg["to"], msg.as_string())
        log("    [email] 已发送")
        return True
    except Exception as e:  # noqa: BLE001
        log(f"    [email] 失败: {type(e).__name__}: {str(e)[:150]}")
        return False


CHANNELS = {
    "pushplus": send_pushplus,
    "serverchan": send_serverchan,
    "wecom_bot": send_wecom_bot,
    "feishu": send_feishu,
    "email": send_email,
}


# --------------------------------------------------------------------------- #
# 内容构造
# --------------------------------------------------------------------------- #
def build_message(data: dict, top: int, brief_url: str) -> tuple[str, str]:
    """返回 (标题, 正文)。微信场景下正文是精简卡片。"""
    items = data.get("items") or []
    domains = data.get("domains") or []
    gen = data.get("generated_at", "")
    try:
        day = datetime.fromisoformat(gen).strftime("%m月%d日")
    except Exception:  # noqa: BLE001
        day = datetime.now(CN_TZ).strftime("%m月%d日")

    title = f"【全球科技前沿】{day} · {len(items)} 条"

    lines = []
    for i, it in enumerate(items[:top], 1):
        minor = it.get("category_minor") or it.get("domain") or ""
        lines.append(f"{i}. {it.get('title','')}（{it.get('score',0)}分 · {minor}）")

    if len(items) > top:
        lines.append(f"…另有 {len(items) - top} 条")

    lines.append("")
    if brief_url:
        lines.append(f"📄 完整日报（{len(items)}条）：{brief_url}")
    else:
        lines.append(f"📊 完整数据：{data.get('source','')}")

    lines.append("")
    lines.append(f"— 领域：{'、'.join(domains) if domains else '全部'}")
    lines.append("— 数据源 news.tekoai.net，全球数千站点经前沿大模型筛选")

    return title, "\n".join(lines)


def append_pending(title: str, content: str, reason: str) -> None:
    MEM_DIR.mkdir(parents=True, exist_ok=True)
    rec = {"title": title, "content": content, "reason": reason,
           "at": datetime.now(CN_TZ).isoformat(timespec="seconds")}
    with PENDING_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log(f"已暂存到待重试队列: {PENDING_FILE}")


def main() -> int:
    ap = argparse.ArgumentParser(description="推送科技前沿简报到微信等通道")
    ap.add_argument("--input", help="feed.py 输出的 JSON 文件")
    ap.add_argument("--channel", help="指定单通道（覆盖配置里的主通道）")
    ap.add_argument("--top", type=int, default=5, help="卡片里放几条标题，默认 5")
    ap.add_argument("--brief-url", default="", help="完整 HTML 日报的链接")
    ap.add_argument("--test", action="store_true", help="发一条测试消息")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不真发")
    args = ap.parse_args()

    prefs = load_prefs()
    pcfg = prefs.get("push") or {}
    if not pcfg:
        log("未配置推送通道。请先在 memory/preferences.json 里加 push 段，"
            "见 references/push-channels.md")
        return 2

    primary = args.channel or pcfg.get("channel")
    chain = [primary] + [c for c in (pcfg.get("fallback") or []) if c != primary]
    channels_cfg = pcfg.get("channels") or {}

    if args.test:
        title = "【测试】科技前沿头条"
        content = ("这是一条通道测试消息。收到即表示推送配置成功。\n\n"
                   "— 数据源 news.tekoai.net")
    else:
        if not args.input:
            log("需要 --input 指定 JSON 文件，或用 --test 测通道")
            return 2
        src = Path(args.input)
        if not src.exists():
            log(f"输入文件不存在: {src}")
            return 2
        data = json.loads(src.read_text(encoding="utf-8"))
        if not (data.get("items") or []):
            log("简报里没有条目，不推送（不为了推送而凑内容）")
            return 0
        title, content = build_message(data, max(1, args.top), args.brief_url)

    print("=" * 64)
    print(f"标题: {title}")
    print("-" * 64)
    print(content)
    print("=" * 64)

    if args.dry_run:
        print("\n[dry-run] 未实际发送。")
        return 0

    for ch in chain:
        fn = CHANNELS.get(ch)
        if not fn:
            log(f"[跳过] 未知通道: {ch}（可用: {'/'.join(CHANNELS)}）")
            continue
        log(f"[尝试通道] {ch}（额度提示：{QUOTA_HINT.get(ch, '未知')}）")
        try:
            if fn(channels_cfg.get(ch) or {}, title, content):
                log(f"[成功] 已通过 {ch} 推送")
                return 0
        except Exception as e:  # noqa: BLE001
            log(f"[异常] {ch}: {type(e).__name__}: {str(e)[:150]}")

    log("[失败] 所有通道都没发出去。")
    append_pending(title, content, "all_channels_failed")
    log("→ 请检查通道配置与网络，或参照 references/push-channels.md 排查")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tech-frontier-headlines / render.py

把 feed.py 输出的 JSON 渲染成**自包含、可分享**的 HTML 日报。
只用 Python 标准库，无外部资源依赖（不引用 CDN，离线可看，可直接发群里）。

用法:
    python feed.py --domains 防务,能源 --limit 10 --format json --out data.json
    python render.py --input data.json --out brief.html
    python render.py --input data.json --out brief.html --top 5 --title "我的科技日报"
    python render.py --input data.json --out brief.html --tag "能源观察"
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

CN_TZ = timezone(timedelta(hours=8))

# 评分等级 -> 展示色（只用于数字本身，做很轻的区分）
CLASS_COLOR = {
    "S": "#b5493f",
    "A": "#b5652f",
    "B": "#7f8c8d",
    "C": "#a5a5a5",
}


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def fmt_time(s: str) -> str:
    if not s:
        return ""
    try:
        return datetime.fromisoformat(s).strftime("%m-%d %H:%M")
    except Exception:  # noqa: BLE001
        return s


def score_badge(item: dict) -> str:
    sc = item.get("score", 0)
    cls = item.get("score_class", "")
    color = CLASS_COLOR.get(cls, "#7f8c8d")
    return (f'<span class="score" style="color:{color}">'
            f'{sc}<small>{esc(cls)}</small></span>')


def render(data: dict, top: int, title: str, tag: str) -> str:
    items = data.get("items") or []
    head, rest = items[:top], items[top:]
    domains = data.get("domains") or []
    gen = data.get("generated_at", "")
    try:
        gen_disp = datetime.fromisoformat(gen).strftime("%Y年%m月%d日 %H:%M")
    except Exception:  # noqa: BLE001
        gen_disp = gen

    # ---- 头条卡片 ----
    cards = []
    for i, it in enumerate(head, 1):
        minor = it.get("category_minor") or it.get("category") or ""
        cards.append(f"""
    <article class="card">
      <div class="card-head">
        <span class="rank">{i:02d}</span>
        {score_badge(it)}
        <div class="tags">
          <span class="tag tag-domain">{esc(it.get('domain', ''))}</span>
          {f'<span class="tag">{esc(minor)}</span>' if minor else ''}
        </div>
      </div>
      <h2><a href="{esc(it.get('url'))}" target="_blank" rel="noopener">{esc(it.get('title'))}</a></h2>
      <p class="summary">{esc(it.get('summary'))}</p>
      <div class="meta">
        <span>{esc(it.get('source'))}</span>
        <span>{esc(fmt_time(it.get('publish_time')))}</span>
        <a href="{esc(it.get('url'))}" target="_blank" rel="noopener">原文 →</a>
      </div>
    </article>""")
    # ---- 次级列表 ----
    rows = []
    for it in rest:
        minor = it.get("category_minor") or it.get("category") or ""
        rows.append(f"""
      <tr>
        <td class="c-score">{it.get('score', 0)}<small>{esc(it.get('score_class',''))}</small></td>
        <td><a href="{esc(it.get('url'))}" target="_blank" rel="noopener">{esc(it.get('title'))}</a></td>
        <td class="c-cat">{esc(it.get('domain',''))}·{esc(minor)}</td>
        <td class="c-src">{esc(it.get('source'))}</td>
        <td class="c-time">{esc(fmt_time(it.get('publish_time')))}</td>
      </tr>""")

    rest_block = ""
    if rest:
        rest_block = f"""
  <section class="rest">
    <h3>值得留意（{len(rest)} 条）</h3>
    <table>
      <thead><tr><th>评分</th><th>标题</th><th>领域</th><th>信源</th><th>时间</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </section>"""

    failed = data.get("failed_domains") or []
    fail_block = (f'<div class="warn">⚠️ 以下领域本次抓取失败：{esc("、".join(failed))}'
                  f'　（不编造内容，如实标注）</div>') if failed else ""

    tag_html = f'<div class="tagline">{esc(tag)}</div>' if tag else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {esc(gen_disp)}</title>
<style>
  :root {{ color-scheme: light dark; --fg:#1d1d1b; --fg2:#6b6b68; --fg3:#8a8a86;
           --bg:#fbfbf9; --card:#ffffff; --line:#e8e6df; --line2:#d3d1c7; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --fg:#e8e6e3; --fg2:#a8a6a0; --fg3:#8a8a86;
             --bg:#1a1a18; --card:#242422; --line:#33332f; --line2:#44443f; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:40px 20px 60px; background:var(--bg); color:var(--fg);
          font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
          line-height:1.65; -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:860px; margin:0 auto; }}
  header {{ border-bottom:2px solid var(--fg); padding-bottom:18px; margin-bottom:8px; }}
  h1 {{ font-size:26px; font-weight:600; margin:0 0 8px; letter-spacing:-.01em; }}
  .tagline {{ font-size:13px; color:var(--fg2); margin-bottom:4px; }}
  .sub {{ font-size:13px; color:var(--fg2); }}
  .src-note {{ font-size:12px; color:var(--fg3); margin-top:10px; line-height:1.7;
               padding:12px 15px; background:var(--card); border-radius:8px;
               border:1px solid var(--line); }}
  .warn {{ font-size:13px; color:#d35400; margin-top:14px; padding:10px 14px;
           border:1px solid #d35400; border-radius:8px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
           padding:20px 22px; margin-top:18px; }}
  .card-head {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
  .rank {{ font-size:12px; font-weight:500; color:var(--line2); font-variant-numeric:tabular-nums; }}
  .score {{ font-size:12.5px; font-weight:500; color:var(--fg2); font-variant-numeric:tabular-nums; }}
  .score small {{ font-size:9.5px; font-weight:400; opacity:.7; margin-left:1px; }}
  .tags {{ display:flex; gap:6px; flex-wrap:wrap; }}
  .tag {{ font-size:10.5px; padding:1px 7px; border-radius:20px;
          background:transparent; border:1px solid var(--line); color:var(--fg3); font-weight:400; }}
  .tag-domain {{ color:var(--fg2); }}
  .card h2 {{ font-size:17.5px; font-weight:600; margin:12px 0 9px; line-height:1.45; }}
  .card h2 a {{ color:var(--fg); text-decoration:none; }}
  .card h2 a:hover {{ text-decoration:underline; text-underline-offset:3px; }}
  .summary {{ font-size:13.5px; color:var(--fg2); margin:0 0 13px; text-align:justify; }}
  .meta {{ display:flex; gap:16px; flex-wrap:wrap; font-size:11.5px; color:var(--fg3);
           border-top:1px solid var(--line); padding-top:10px; }}
  .meta a {{ color:#185fa5; text-decoration:none; }}
  .rest {{ margin-top:34px; }}
  .rest h3 {{ font-size:15px; font-weight:600; margin:0 0 14px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th {{ text-align:left; font-weight:500; color:var(--fg3); font-size:11.5px;
        padding:8px 10px; border-bottom:1px solid var(--line2); white-space:nowrap; }}
  td {{ padding:10px; border-bottom:1px solid var(--line); vertical-align:top; }}
  td a {{ color:var(--fg); text-decoration:none; }}
  td a:hover {{ text-decoration:underline; }}
  .c-score {{ white-space:nowrap; color:var(--fg3); font-size:11.5px; font-variant-numeric:tabular-nums; }}
  .c-score small {{ font-size:9.5px; margin-left:2px; opacity:.7; }}
  .c-cat, .c-src, .c-time {{ color:var(--fg3); white-space:nowrap; font-size:11.5px; }}
  footer {{ margin-top:44px; padding-top:20px; border-top:1px solid var(--line);
            font-size:12px; color:var(--fg3); line-height:1.8; }}
  footer a {{ color:#185fa5; }}
  @media (max-width:640px) {{
    body {{ padding:24px 14px 40px; }}
    h1 {{ font-size:21px; }}
    .card {{ padding:16px; }}
    .c-cat, .c-src {{ display:none; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    {tag_html}
    <h1>{esc(title)}</h1>
    <div class="sub">数据更新于 {esc(gen_disp)}</div>
  </header>

  <div class="src-note">
    <strong>数据来源</strong>：<a href="{esc(data.get('source',''))}">{esc(data.get('source',''))}</a>
    —— 扫描全球数千个可信站点，每条新闻均经前沿大模型处理与评分。
  </div>

  {fail_block}
  {''.join(cards)}
  {rest_block}

  <footer>
    由 <strong>tech-frontier-headlines</strong> 技能生成　·　数据源每 30 分钟自动更新<br>
    评级口径：score 为前沿大模型给出的 0–100 价值评分；S/A/B/C 为对应分级（重复项已剔除）<br>
    生成时间 {esc(datetime.now(CN_TZ).strftime('%Y-%m-%d %H:%M:%S'))}
  </footer>
</div>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="把 feed.py 的 JSON 渲染成可分享 HTML 日报")
    ap.add_argument("--input", required=True, help="feed.py --format json 输出的文件")
    ap.add_argument("--out", required=True, help="输出 HTML 路径")
    ap.add_argument("--top", type=int, default=5, help="头部卡片数量，默认 5")
    ap.add_argument("--title", default="全球科技前沿日报", help="报告标题")
    ap.add_argument("--tag", default="", help="标题上方的小标签，如「能源观察」")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"输入文件不存在: {src}", file=sys.stderr)
        return 2
    data = json.loads(src.read_text(encoding="utf-8"))

    html_doc = render(data, max(1, args.top), args.title, args.tag)
    Path(args.out).write_text(html_doc, encoding="utf-8")
    n = len(data.get("items") or [])
    print(f"已生成 {args.out}（{n} 条，头部卡片 {min(args.top, n)} 张，"
          f"{len(html_doc)/1024:.1f} KB，自包含无外链）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

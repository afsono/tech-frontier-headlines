# 推送通道配置

## 设计原则：通道可插拔

推送能力做成**独立通道层**，业务逻辑只调用 `push.py`，不关心底层是哪家。
某个通道挂了或被政策调整，换一个通道**不需要改业务逻辑**。

`scripts/push.py` 支持 5 类通道，配置存在 `memory/preferences.json` 的 `push` 段：

```json
{
  "push": {
    "channel": "pushplus",
    "channels": {
      "pushplus": { "token": "你的token" },
      "serverchan": { "sendkey": "你的SendKey" },
      "wecom_bot": { "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx" },
      "feishu": { "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx" },
      "email": { "smtp_host": "", "smtp_port": 465, "user": "", "pass": "", "to": [] }
    },
    "daily_limit": 200,
    "fallback": ["serverchan", "wecom_bot"]
  }
}
```

`channel` 是主通道，`fallback` 是备用链——主通道失败自动依次尝试。
**实测建议**：配置主通道 + 至少一个备用通道，这是最可靠的组合。

---

## 通道对比（2026-09 调研）

| 通道 | 直达个人微信 | 接入成本 | 免费额度 | 消息格式 | 适用 |
|---|---|---|---|---|---|
| **PushPlus** | ✔ 是 | 低（一个 token） | 200 条/天 | Markdown / HTML | **默认推荐**，配额最宽 |
| **Server酱** | ✔ 是 | 极低（SendKey） | Turbo 免费版 10 条/天 | Markdown | 备用通道首选 |
| **WxPusher** | ✔ 是 | 低（关注应用二维码） | 免费，开源可自建 | 文本 / HTML | 想完全自控时 |
| **企业微信群机器人** | ✘（发到群） | 低（Webhook） | 免费，额度宽松 | 文本 / Markdown | 团队/多人场景 |
| **企业微信应用** | ✔ 是 | 高（corpid/secret/agentid/可信IP） | 免费 | 文本 / Markdown | 企业内部 |
| **飞书群机器人** | ✘（需装客户端） | 低（Webhook） | 免费 | 文本 / Markdown | 公司场景 |
| **邮件** | ✘（不即时） | 低 | 免费 | HTML | 归档，不适合提醒 |
| Bark | ✘（仅 iOS） | 低 | 免费 | 通知 | 纯苹果设备 |

**结论**：给自己推 → **PushPlus 为主 + Server酱 备用**；推给团队 → 企业微信群机器人。

---

## 各通道接入步骤

### PushPlus（推荐主通道）

1. 访问 pushplus 官网，**微信扫码登录**
2. 在「一对一推送」页面拿到 `token`
3. 写进 `memory/preferences.json`
4. 验证：`python scripts/push.py --test`

接口：`POST https://www.pushplus.plus/send`，参数 `token` / `title` / `content` / `template=markdown`

### Server酱（推荐备用）

1. 访问 Server酱官网，微信扫码关注其服务号
2. 在「Key&API」页面拿 `SendKey`
3. 接口：`POST https://sctapi.ftqq.com/{SendKey}.send`，参数 `title` / `desp`

⚠️ 免费版每天 10 条，**只做备用**。标题里避免"报警""故障"等敏感词可能被过滤。

### 企业微信群机器人

1. 在企业微信里建一个群（可以只有自己）
2. 群设置 → 群机器人 → 添加 → 复制 Webhook
3. 接口：`POST {webhook}`，body `{"msgtype":"markdown","markdown":{"content":"..."}}`

额度宽松、稳定，缺点是发到群里而不是私聊。**本平台有官方「企业微信」连接器**，
装了之后可以直接用它的机器人主动通知能力，无需自己管 Webhook。

---

## 推送内容设计

**微信里不要推全文**。按 `templates.md` 的「形态五：微信推送」：

- Top 3–5 条标题 + 评分 + 细分领域
- 一行数据源说明
- 一个完整日报链接

**推送时机**：由用户决定。**不要主动替用户开定时任务**——
在用户明确说"每天 8 点推给我"时，才用宿主的定时/自动化能力配置，
并把配置写进 `memory/preferences.json`。

---

## 故障排查

| 现象 | 排查 |
|---|---|
| 返回成功但没收到 | 检查微信是否屏蔽了该服务号（微信 → 设置 → 通用 → 辅助功能）；检查内容是否触发敏感词过滤 |
| `token invalid` | 重新扫码获取 token |
| 超配额 | 查 `daily_limit`，切换到备用通道 |
| 企业微信机器人无响应 | Webhook 是否失效（群被解散/机器人被移除） |
| 内容被截断 | 微信类通道有长度限制，**推送时只用精简卡片**，超长内容走链接 |

**通用兜底**：所有通道都失败时，把消息写到 `memory/pending_push.jsonl`，
下次运行时重试，并告知用户"推送失败，已暂存"。

# Audit Guide — 证明 Claude 到底往服务器发了什么

回应反馈:"Can we start from Audit logs, I want us to be able clearly see what
Claude app sends to servers to validate the tool."

审计分两层,回答两个不同的问题。**两层都要看,缺一不可。**

| 层 | 问题 | 机制 | 谁能做 | 可靠性 |
|---|---|---|---|---|
| **Q1 边界审计日志** | 我们的工具交给 Claude 的是什么? | 本地 append-only JSONL,记录每次工具调用返回给 Claude 的**完整内容** | 已内置,自动 | 确定性,不受 TLS/证书 pinning 影响 |
| **Q2 网络抓包** | Claude app 实际往服务器发的是什么? | mitmproxy 解密 HTTPS,扫描请求体里的哨兵名 | 需你装根证书 | 依赖证书信任;可能被 pinning 阻挡 |

---

## Q1:边界审计日志(随时可查,零配置)

每次 `mask_document` / `restore_text` / `restore_document` 调用后,工具会在
`%APPDATA%\ContentMaskingTool\audit\audit-YYYYMMDD.jsonl` 追加一行,内容是
**返回给 Claude 的确切 payload**。

- `mask_document` 的记录里 `returned_to_claude.masked_text` 就是进入对话的全部内容
  —— 里面只有 `⟦PERSON_001⟧` 这类 token,可肉眼确认无真名。
- `restore_text` 的记录会显式标注 `returns_originals_to_conversation: true`
  —— 提醒你这个调用会把真名带回对话(所以敏感场景要用 `restore_document`)。
- `restore_document` 的记录只含输出文件路径,payload 里无真名。

查看:用记事本打开当天的 jsonl,或跑
`maskingtool-server.exe`(命令行)后直接看文件。这是**权威记录**:它就在原文
离开本地信任域的那个点上,任何网络层的东西都改变不了它。

---

## Q2:网络抓包(证明 Claude app 的实际出站流量)

### 前提:哨兵文档

用 `demo\audit-sentinel-doc.md` —— 里面的名字(Zorbix / Kwframe / Vantalio /
Brixworth / Quenndale)是独一无二的编造词,只要它出现在流量里就是铁证级泄漏。

### 步骤

**步骤 1 — 启动抓包**
双击 `packaging\audit\1-start-capture.bat`,保持窗口开着。每条发往 Anthropic 的
请求会实时打印 `clean` 或 `LEAK!`。

**步骤 2 — 信任 mitmproxy 根证书(⚠️ 需要你自己操作,这是修改系统安全设置)**
证书在 `%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.cer`。
1. 双击该 .cer 文件 → 安装证书 → 存储位置选"当前用户" → "将所有证书放入下列存储" →
   浏览 → 选"受信任的根证书颁发机构" → 完成。
2. 完成审计后**务必删除**这张证书(certmgr.msc → 受信任的根证书颁发机构 →
   证书 → 删除 mitmproxy)。装着它期间,这台机器的 HTTPS 可被该证书持有者解密。

> 我(Claude Code)不会替你装/删根证书 —— 这是系统安全设置,按规矩必须你亲自做。

**步骤 3 — 让 Claude 走代理**
先完全退出 Claude Desktop(托盘 → Quit),再双击
`packaging\audit\2-launch-claude-through-proxy.bat`。它只给 Claude 这一个进程设
代理环境变量 + 让 Electron 信任 mitmproxy 证书,**不改你的系统全局代理**。

**步骤 4 — 三种操作各跑一遍,分别截图**

| # | 模式 | 操作 | 抓包窗口应显示 |
|---|---|---|---|
| A | 聊天窗 + 脱敏工具(推荐路径) | 对 Claude 说:用 mask_document 处理 `demo\audit-sentinel-doc.md` 再总结 | 全部 `clean`;哨兵名不出现 |
| B | 聊天窗 + 直接上传附件(反例!) | 用回形针把 `audit-sentinel-doc.md` 当附件上传 | **LEAK!** —— 证明附件绕过工具,这正是 USAGE.md 警告的洞 |
| C | 兜底目录 | 文件放在 Claude 原生够不到的目录,只给路径让它脱敏 | 全部 `clean` |

对每种模式:截图抓包窗口(能看到 clean/LEAK 判定)+ 截图 Claude 对话。

**步骤 5 — 汇总**
Ctrl+C 停止抓包,跑 `packaging\audit\3-analyze.ps1`,得到判定表和
`network-audit-verdict.txt`。截这张表。

### 已知风险:证书 pinning

如果 Claude 对某些端点做了证书锁定,那些请求在抓包里会显示 TLS 握手失败/无法解密
——不是我们工具的问题,而是抓不到明文。此时后备证据是:
- Q1 边界日志(已经证明我们只交给 Claude token);
- 抓包仍能看到**连接的目标主机和请求大小**,配合边界日志足以佐证。

---

## 结论应如何向审阅者陈述

1. Q1 证明:**我们的工具**只把脱敏后文本交给 Claude(边界日志,确定性)。
2. Q2 证明:**Claude app** 在"走工具"的 A/C 模式下,出站流量里无哨兵名;而在
   B 模式(直接传附件)下有 —— 精确印证了"强制/纪律/兜底"三档的边界:
   - 走工具(A/C)= 干净;
   - 传附件(B)= 泄漏,工具无法拦(上传发生在工具系统之前),只能靠纪律避免。

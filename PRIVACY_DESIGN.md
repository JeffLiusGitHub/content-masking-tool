# 隐私边界设计 — Claude 永远接触不到原文

> 本文描述当前打包版本(v1.2.0,含强制人工审核)经代码核实的实际行为。
> 相关文档:[USAGE.md](USAGE.md) · [AUDIT_GUIDE.md](AUDIT_GUIDE.md) · 实现状态见 [PROGRESS.md](PROGRESS.md)

## 核心流程:敏感信息如何被隔离

```
用户给 Claude 一个本地文件路径(只是字符串,不是文件内容)
        │
        ▼
mask_document(file_path)          ← 本机 MCP 进程读文件,Claude 读不到
        │  立即返回 review_id,弹出本地审核窗口
        ▼
用户在审核窗口里检查红/绿 diff、补漏、点"确认并生成脱敏文件"
        │  确认之前:不写任何文件、不返回任何内容
        │  (Claude 同时在用 get_review_status 长轮询等待,
        │   点击确认的瞬间自动解除等待,无需用户回聊天窗口报告)
        ▼
get_review_result(review_id)      ← Claude 此时才拿到"脱敏后"的文本
        │  内容里只有 ⟦PERSON_001⟧ / ⟦ORG_001⟧ 这类令牌
        ▼
Claude 基于脱敏文本做后续工作(摘要、改写、翻译……)
        │
        ▼
restore_document(vault_id, 文件)  ← 还原发生在本机,写成本地文件
           Claude 只收到输出文件的路径,把路径告诉用户即可
```

**整个链路中,原始姓名/公司名只存在于:① 源文件 ② 本机 Vault ③ 还原输出文件。三者都只在本机磁盘上,永远不进入与 Claude 的对话。**

## 各类文件存放位置(当前实际行为)

| 内容 | 位置 | 说明 |
|---|---|---|
| 脱敏输出文件 | **`Documents\Masked Files\`**,命名 `<原名>.masked.md` | 集中存放(2026-07-20 起);绝不覆盖已有文件,重名时自动加数字后缀;可用 settings.json 的 `masked_output_dir` 或环境变量 `MASKINGTOOL_MASKED_DIR` 改位置 |
| 还原输出文件 | 脱敏文件所在目录,命名 `<原名>.restored.<扩展名>` | 同样绝不覆盖 |
| Vault(令牌↔原名映射,**敏感**) | `%APPDATA%\ContentMaskingTool\vaults\vault_<id>.json` | 每次脱敏生成一个 `vault_id`;还原必须用同一个 id |
| 历史索引 | `%APPDATA%\ContentMaskingTool\`(history) | 记录输入/输出路径、vault_id、时间戳、令牌统计;**不含原名** |
| 审核任务状态 | `%APPDATA%\ContentMaskingTool\reviews\review_<id>.json` | 原子写入,状态单向:waiting → completed/cancelled/failed |
| 名单 CSV | `%APPDATA%\ContentMaskingTool\`(companies/people) | 热加载,改完立即生效 |
| 审计日志 | `%APPDATA%\ContentMaskingTool\audit\`(JSONL) | 记录每次 MCP 调用实际返回给 Claude 的完整 payload,可事后核查 |

## 四个关键问题的核实结论

1. **是否在 Documents 里建 "masked file" 文件夹集中存放?**
   ✅ 是(2026-07-20 起)。GUI/审核确认生成的脱敏文件统一写入 `Documents\Masked Files\`,所有经 MCP 或拖拽产生的脱敏输出都在这一个地方。

2. **vault_id 是否存在电脑某处?**
   ✅ 是。`%APPDATA%\ContentMaskingTool\vaults\vault_<id>.json`,本机保存,永不打包进安装包或脱敏输出。它是唯一能把令牌换回原名的钥匙——**分享脱敏文件时不要附带 Vault**,除非对方确需还原且走安全通道。

3. **确认后 Claude 是否自动用脱敏版本做后续工作?**
   ✅ 是。审核确认后 `get_review_result` 返回的就是脱敏文本(只有令牌),Claude 之后所有的分析、改写、生成都基于这份文本。Claude 从头到尾没有渠道读到原文——Claude Code 侧还有 hook 硬性拦截对 .pdf/.docx/.md 的直接读取。

4. **还原时 Claude 是否只告诉用户文件位置(不读敏感内容)?**
   ✅ 是——**前提是用 `restore_document`**。它在本机把令牌换回原名、写出 `.restored` 文件,返回给 Claude 的只有输出路径和未解析令牌列表,Claude 把路径(可点击链接)告诉用户即可。
   ⚠️ 注意另有一个 `restore_text` 工具,它**会**把原名直接返回到对话里(设计如此,便于在聊天里就地还原小段文本)。敏感场景应要求 Claude 使用 `restore_document`;审计日志会明确标记 `restore_text` 的每次使用。

## 保证边界(诚实声明)

- **确定性保证**只覆盖名单(deny-list)里的名字:精确匹配,优先级 1.0,永远命中。
- 名单之外的随机姓名靠 NER 模型识别:**高召回,但非 100% 保证**;审核窗口里的人工检查 + "遮蔽所选文字"补漏就是为此设计的最后一道闸。
- 中文姓名/公司名是当前英文 NER 模型的已知盲区——重要中文名请加入名单 CSV。
- **无法防住的洞**:把文件直接拖成聊天附件、或把原文粘贴进对话——内容在工具介入之前就已上传。纪律:**只给路径,不给内容**。
- 每次跨边界的实际 payload 都记录在审计日志里,随时可以核查"Claude 到底收到了什么"。

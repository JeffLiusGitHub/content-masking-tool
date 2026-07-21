# Content Masking Tool — 使用说明（给团队）

本工具在你的电脑本地把文档里的人名/公司名替换成 `⟦PERSON_001⟧` 这类代号后再交给
Claude，事后可精确还原。真名和还原映射表（vault）永远只在你本机。

## 安装（Windows）

1. 从内网共享获取 `content-masking-tool-win.mcpb`
2. Claude Desktop → Settings → Extensions → Advanced settings → Install Extension… 选择该文件
3. 弹出"未经 Anthropic 验证"提示属预期（内部工具未上架官方目录），确认安装
4. 独立命令行版（无需 Claude 也能脱敏/还原）：解压 `maskingtool-windows-standalone.zip` 到任意位置

## 日常用法

```
（聊天窗）用 content masking tool 脱敏 C:\docs\report.docx 然后总结要点
（继续对话，全程只有代号，没有真名）
（结束时）用 restore_document 把结果还原到本地文件
```

命令行版（同一个程序，带参数=命令行工具，不带参数=MCP server）：
```
maskingtool-server.exe mask C:\docs\report.docx
maskingtool-server.exe restore C:\docs\report.masked.md --vault-id <脱敏时返回的id>
```

## ⚠️ 哪些是"强制保证"，哪些做不到——务必读完

### 技术强制（想绕都绕不过）

| 保证 | 机制 |
|---|---|
| 脱敏/还原全程本地完成，过程零联网 | 自动化测试证明：禁用网络后功能完整（`Test result/M_local_only/`） |
| 还原映射表只存本机 | vault 是本地 JSON 文件，工具对话回复里只含无意义的 vault_id |
| **Claude Desktop 聊天窗给文件路径** → 必走脱敏 | 聊天窗没有自己的文件读取能力，拿到内容的唯一途径就是脱敏工具 |
| **Claude Code 里直接读 .pdf/.docx/.doc** → 被拦截 | PreToolUse hook 由框架执行（`.claude/settings.json`+`.claude/hooks/`），模型无法绕过；需随项目分发此配置 |
| 名单内名字 100% 被遮 | 确定性字符串匹配，有测试断言零泄漏 |

### 无法技术强制（靠使用纪律）

| 风险行为 | 后果 | 纪律 |
|---|---|---|
| **用回形针"Add files"上传附件** | 文件内容直接上云，任何工具拦不到（上传发生在工具系统之前） | **敏感文件永远给路径，永远不当附件传** |
| 把原文复制粘贴进对话 | 同上 | 不粘贴敏感原文 |
| 让 Claude 打开 vault 文件 / 还原后的文件 / 名单 CSV | 内容进对话=上云 | 带真名的文件自己用记事本/Word 打开 |
| 用 `restore_text`（对话内还原） | 还原结果显示在聊天里=真名上云 | 敏感内容一律用 `restore_document`（写本地文件） |
| 随机名字（不在名单里的）依赖 NER 识别 | NER 是高召回但**非 100%**（表格/生僻名可能漏） | 关键名字加进名单 CSV（`%APPDATA%\ContentMaskingTool\denylists\`），加一行=永久保证 |
| Claude Code 里用终端命令绕过（如 `type file.pdf`） | hook 只拦 Read 工具 | 不指示 Claude 用 shell 读敏感文档 |

### 一句话原则

> **敏感文件只给路径；带真名的文件只自己打开；重要名字进名单。**

## 常见问题

- **vault_id 忘了**：`%APPDATA%\ContentMaskingTool\vaults\` 按时间找，文件名即 id
- **名单怎么改**：记事本编辑 `%APPDATA%\ContentMaskingTool\denylists\people.csv`（一行一个全名），保存即生效
- **NER 开关**：`%APPDATA%\ContentMaskingTool\settings.json` 的 `enable_ner`（出厂开启）
# Drag-and-drop desktop interface

In the Windows standalone package, double-click `maskingtool-server.exe` to
open the local interface. Drop one supported document onto the window. Plain
documents are masked; documents containing masking tokens are restored with
the vault recorded on this machine. Outputs are written beside the source and
existing files are never overwritten.

The same executable remains available as a command-line tool when arguments
are supplied, and as the MCP server when started with a stdin pipe.

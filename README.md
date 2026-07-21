# Content Masking Tool

[![build](https://github.com/JeffLiusGitHub/content-masking-tool/actions/workflows/build.yml/badge.svg)](https://github.com/JeffLiusGitHub/content-masking-tool/actions/workflows/build.yml)
[![checks](https://github.com/JeffLiusGitHub/content-masking-tool/actions/workflows/checks.yml/badge.svg)](https://github.com/JeffLiusGitHub/content-masking-tool/actions/workflows/checks.yml)
[![CodeQL](https://github.com/JeffLiusGitHub/content-masking-tool/actions/workflows/codeql.yml/badge.svg)](https://github.com/JeffLiusGitHub/content-masking-tool/actions/workflows/codeql.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
![platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20(arm64%20%7C%20x86__64)-lightgrey)

**English** ⬇️ | [中文](#中文说明)

Local-first, reversible masking of company and people names in documents (MD/TXT/DOCX/PDF) before their content reaches an AI — shipped as a Windows and macOS desktop app, a CLI, and a Claude Desktop Extension (MCP), all in one executable.

本地优先、可逆的文档脱敏工具:在文档内容进入 AI 之前,把公司名和人名替换成令牌,事后精确还原。[跳转到中文完整说明 →](#中文说明)

**Status:** v1.2.0, Windows and macOS builds working (148 source tests passing). macOS ships native binaries for both Apple Silicon (arm64) and Intel (x86_64). Details in [PROGRESS.md](PROGRESS.md).

---

## What it does

Documents sent to Claude (or any AI) often contain confidential company and people names. This tool:

- **Masks before the conversation** — the AI only ever sees tokens like `⟦PERSON_001⟧` / `⟦ORG_001⟧`, never the real names;
- **Deterministically reversible** — token↔name mappings live in a local Vault; restore is exact, byte-for-byte;
- **Same name, same token** — a given name always maps to the same token across the whole document (and across revisions reusing the same Vault), so the AI keeps the context;
- **Mandatory human review** — no masked file is created from any entry point until you inspect a red/green diff and explicitly confirm;
- **Fully local** — no network dependency (proven by socket-disabled tests); Vaults, name lists, and history stay under `%APPDATA%\ContentMaskingTool\`.

Supported input: `.md` / `.markdown` / `.txt` / `.docx` / `.pdf` (PDF is text-extraction to masked Markdown only; scanned PDFs are rejected explicitly instead of producing garbage).

## Detection (two layers)

| Layer | Mechanism | Guarantee |
|---|---|---|
| Deny-list | Your people/companies CSVs + terms added by hand in the GUI | **Deterministic hit**, highest priority; the zero-leak guarantee covers this layer |
| NER model | Bundled spaCy `en_core_web_sm`, catches random names not on any list | High recall, not 100%; Chinese names are a known blind spot — put critical Chinese names on the list |

Missed a name? Select it in the review window and add it — once added, it applies to every future document automatically.

## How to use

### Option 1: Desktop GUI (drag & drop)

Launch `maskingtool-server.exe` (double-click opens the GUI) and drop a file into the window:

The tool analyzes the file and shows a **read-only preview** — red is the original, green is the masked result. **No file has been created yet**.

Click **Confirm and create masked file** only when the preview is right — that is the only action that writes the masked file (default: `Documents\Masked Files\`), the Vault, and the history record. Cancel leaves nothing behind.

Spotted a missed name? **Select it in the preview** → click `Mask selected text` → classify it as Person or Organization. Every exact occurrence is re-masked immediately, and the term is saved permanently for future documents.

To restore, drop the `.masked` file back into the same window. The tool asks explicitly before restoring, writes a `.restored` file, and never overwrites anything.

A step-by-step tutorial plays on first launch (reopen anytime via `Tutorial`); the UI switches between English / 中文 and remembers your choice.

### Option 2: Inside Claude (MCP extension)

With the extension installed, just tell Claude:

> Mask C:\path\to\report.docx for me (give the **path only** — never attach the file to the chat; attachments upload before any tool can intervene)

Flow: Claude calls `mask_document` → a review window opens on your machine → you inspect, fix misses, click Confirm → Claude picks up the approved masked text automatically (long-polling; it continues the instant you confirm — no need to report back in chat). For restoring, have Claude use `restore_document`: it only receives the output file path; real names never enter the conversation.

**Claude has no channel to read the original text at any point**; every payload that crosses the boundary is recorded in a local audit log. See [PRIVACY_DESIGN.md](PRIVACY_DESIGN.md) and [USAGE.md](USAGE.md).

### Option 3: Command line

```powershell
maskingtool-server.exe mask report.md              # mask (the human at the keyboard is the reviewer)
maskingtool-server.exe restore-doc report.masked.md --vault-id <id>
```

One executable, three modes, selected automatically: arguments = CLI; piped stdin = MCP server; plain double-click = GUI.

## Installation

**End users (Windows, no Python needed):**

1. Download `maskingtool-windows-standalone.zip` from this repository's GitHub Releases and **extract it completely** (the exe depends on the `_internal` folder next to it — don't copy the exe alone);
2. For use inside Claude Desktop: run `packaging\installer\install.bat` (one-click) or double-click `content-masking-tool-win.mcpb`;
3. After first run, put your team's real name lists into `people.csv` / `companies.csv` under `%APPDATA%\ContentMaskingTool\denylists\` (hot-reloaded — saving takes effect immediately).

The build is currently unsigned: IT should whitelist the exe hash in EDR.

**End users (macOS, no Python needed):**

macOS ships **native builds for both architectures** — pick the one for your Mac:

- Apple Silicon (M1/M2/M3/M4): `content-masking-tool-macos-arm64.mcpb`
- Intel: `content-masking-tool-macos-x86_64.mcpb`

(Not sure? Apple menu →  About This Mac → "Chip" says Apple = arm64, "Processor" says Intel = x86_64.)

**Connect it to Claude Desktop:**

1. Download the matching `.mcpb` from this repository's GitHub Releases;
2. Claude Desktop → **Settings → Extensions → Advanced settings → Install Extension…** → choose the `.mcpb`;
3. The "not verified by Anthropic" prompt is expected for an internal tool — confirm and install, then **restart Claude Desktop**;
4. First launch: because the build is unsigned, macOS Gatekeeper may block it. Approve once via **System Settings → Privacy & Security** (scroll to the blocked-app notice → "Open Anyway"), or clear the quarantine flag: `xattr -dr com.apple.quarantine <path-to-maskingtool-server>`;
5. After first run, put your team's real name lists into `people.csv` / `companies.csv` under `~/Library/Application Support/ContentMaskingTool/denylists/` (hot-reloaded — saving takes effect immediately).

Prefer wiring it up by hand instead of the Extensions UI? Add this to
`~/Library/Application Support/Claude/claude_desktop_config.json` (adjust the
path to where you extracted the standalone ZIP), then restart Claude Desktop:

```json
{
  "mcpServers": {
    "content-masking-tool": {
      "command": "/Users/<you>/Applications/content-masking-tool/maskingtool-server/maskingtool-server",
      "args": []
    }
  }
}
```

The standalone `maskingtool-macos-<arch>-standalone.zip` also works without Claude for CLI masking/restore — extract it completely (the binary depends on the `_internal` folder beside it).

**Developers:**

```powershell
uv sync --locked --extra dev
.venv\Scripts\python.exe -m pytest                          # full test suite
.venv\Scripts\python.exe -m maskingtool mask doc.md         # CLI
.venv\Scripts\python.exe -m maskingtool.mcp_server.server   # MCP stdio server
packaging\pyinstaller\build_windows.ps1                     # Windows: clean, test, freeze, package, checksum
```

On macOS the equivalent release build is a shell script (builds every architecture the host supports, or an explicit list):

```bash
uv sync --locked --extra dev
./packaging/pyinstaller/build_macos.sh              # both arches (Apple Silicon host)
./packaging/pyinstaller/build_macos.sh arm64        # Apple Silicon only
./packaging/pyinstaller/build_macos.sh x86_64       # Intel only
```

See [RELEASING.md](RELEASING.md) for the clean-checkout Windows/macOS release procedure.

## Where your data lives

| Content | Location |
|---|---|
| Masked output | `Documents\Masked Files\` (override via settings.json `masked_output_dir` or `MASKINGTOOL_MASKED_DIR`) |
| Restored output | Next to the masked file, named `.restored` |
| Vault (token↔real-name map, **sensitive — do not share**) | `%APPDATA%\ContentMaskingTool\vaults\` |
| Name-list CSVs / custom terms / history / review jobs / audit log | Subfolders of `%APPDATA%\ContentMaskingTool\` |

When collaborating, **share only the masked file**; send the matching Vault JSON separately over a secure channel only if the recipient genuinely needs to restore.

## Boundaries and known limitations (honest statement)

- **Cannot be prevented:** dragging the original into the chat as an attachment, or pasting its text — content uploads before any tool runs. Discipline: **paths only, never content.** Claude Code projects can ship the bundled `.claude/hooks/` to hard-block direct document reads.
- Names not on the list rely on NER: high recall, not guaranteed; Chinese entities are a blind spot of the current English model (Stage 2: zh model or GLiNER).
- A name split by Markdown inline formatting (`**Acme** Corp`) is not detected; a token split across DOCX runs by later Word edits is not reassembled on restore.
- Out of scope for Stage 1: masked PDF output/restore, OCR, fuzzy/alias matching, auto-update, multi-user shared-Vault sync.

## Roadmap / Support

- macOS packaging (M11): **done** — native arm64 + x86_64 builds, dual-arch CI. Next: code signing / notarization to drop the Gatekeeper prompt. Stage 2 candidates: Chinese NER, alias matching.
- Docs index: architecture [CLAUDE.md](CLAUDE.md) · progress [PROGRESS.md](PROGRESS.md) · team boundary guide [USAGE.md](USAGE.md) · privacy design [PRIVACY_DESIGN.md](PRIVACY_DESIGN.md) · audit [AUDIT_GUIDE.md](AUDIT_GUIDE.md) · test plan [TESTPLAN.md](TESTPLAN.md) · third-party notices [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
- Questions/issues: contact the maintainer, Jeff (internal channels).

*Open-source software licensed under [GNU AGPL-3.0](LICENSE).*

---

# 中文说明

[Back to English ↑](#content-masking-tool)

本地优先、可逆的文档脱敏工具:在文档内容进入 AI(Claude)之前,把公司名和人名替换成 `⟦PERSON_001⟧` / `⟦ORG_001⟧` 这样的令牌;工作完成后再一键还原回真实姓名。全程本地运行,原文永远不离开你的电脑。同一个可执行文件同时提供 Windows 桌面应用、命令行和 Claude 桌面扩展(MCP)三种形态。

**当前状态:** v1.2.0,Windows 与 macOS 版均可用(源码测试 148 通过)。macOS 同时提供 Apple Silicon(arm64)和 Intel(x86_64)两种原生二进制。详细进度见 [PROGRESS.md](PROGRESS.md)。

## 它解决什么问题

给 Claude(或任何 AI)发文档时,里面常有不能外传的公司名、人名。这个工具:

- **先脱敏再对话** — AI 只见到令牌,见不到真名;
- **确定可逆** — 令牌↔真名的映射存在本机 Vault 里,随时精确还原,字节级一致;
- **同名同令牌** — 同一个名字在全文(乃至复用同一 Vault 的多个版本)中永远映射到同一个令牌,AI 能正常理解上下文;
- **强制人工审核** — 无论从哪个入口发起脱敏,生成文件前都要你亲眼检查红绿对比并点确认;
- **完全本地** — 无网络依赖(有断网测试证明),Vault、名单、历史都只存在 `%APPDATA%\ContentMaskingTool\`。

支持输入:`.md` / `.markdown` / `.txt` / `.docx` / `.pdf`(PDF 仅提取文本生成脱敏 Markdown;扫描版 PDF 会被明确拒绝而不是输出乱码)。

## 识别机制(两层)

| 层 | 机制 | 保证 |
|---|---|---|
| 名单(deny-list) | 你维护的 people/companies CSV + GUI 里手工添加的词 | **确定命中**,优先级最高,零泄漏保证只覆盖这一层 |
| NER 模型 | 内置 spaCy `en_core_web_sm`,自动识别名单外的随机姓名/公司 | 高召回但非 100%;中文名是已知盲区,重要中文名请入名单 |

漏网的名字在审核窗口里划选补上即可——补过一次,以后所有文档自动生效。

## 怎么用

### 方式一:桌面 GUI(拖拽)

启动 `maskingtool-server.exe`(双击即进 GUI),把文件拖进窗口:

工具分析后先给出**只读预览**——红色是原文,绿色是脱敏结果,此时**没有生成任何文件**。

检查无误点 **Confirm and create masked file / 确认并生成脱敏文件**,才会写出脱敏文件(默认在 `Documents\Masked Files\`)、Vault 和历史记录;点取消则什么都不留。

发现漏识别?在预览里**划选那个词** → 点 `Mask selected text / 遮蔽所选文字` → 归类为人员或公司。全文所有相同内容立即重新脱敏,并永久保存到自定义名单,以后的文件自动适用。

要还原时,把 `.masked` 文件拖回同一个窗口,工具会明确询问后才还原,输出 `.restored` 文件,绝不覆盖任何已有文件。

首次启动会自动播放分步教程(也可随时点 `Tutorial / 使用教程` 重看);界面支持 English / 中文 切换并记住选择。

### 方式二:在 Claude 里用(MCP 扩展)

安装扩展后,直接在对话里说:

> 帮我脱敏 C:\path\to\报告.docx(只给路径,**不要**把文件拖成聊天附件——附件在工具介入前就已上传)

流程:Claude 调 `mask_document` → 本机弹出审核窗口 → 你检查、补漏、点确认 → Claude 自动拿到脱敏文本继续干活(长轮询,确认瞬间衔接,无需你回聊天窗口报告)。要还原时让 Claude 用 `restore_document`,它只会收到输出文件路径,真名不进对话。

**Claude 全程没有任何渠道读到原文**;每次跨边界的实际返回内容都记录在本机审计日志里可供核查。详见 [PRIVACY_DESIGN.md](PRIVACY_DESIGN.md) 和 [USAGE.md](USAGE.md)。

### 方式三:命令行

```powershell
maskingtool-server.exe mask 报告.md              # 脱敏(键盘前的人就是审核者)
maskingtool-server.exe restore-doc 报告.masked.md --vault-id <id>
```

同一个 exe 三种模式自动选择:带参数 = CLI;stdin 是管道 = MCP 服务器;直接双击 = GUI。

## 安装

**普通使用者(Windows,无需装 Python):**

1. 从本仓库的 GitHub Releases 下载 `maskingtool-windows-standalone.zip`,**完整解压**(exe 依赖同目录的 `_internal`,不能单独拷走);
2. 要在 Claude Desktop 里用:运行 `packaging\installer\install.bat` 一键安装扩展,或双击 `content-masking-tool-win.mcpb`;
3. 首次运行后,把团队的真实名单填入 `%APPDATA%\ContentMaskingTool\denylists\` 下的 `people.csv` / `companies.csv`(热加载,保存即生效)。

构建暂未签名:IT 需将 exe 哈希加入 EDR 白名单。

**普通使用者(macOS,无需装 Python):**

macOS 提供**两种架构的原生构建**,按你的 Mac 选一个:

- Apple Silicon(M1/M2/M3/M4):`content-masking-tool-macos-arm64.mcpb`
- Intel:`content-masking-tool-macos-x86_64.mcpb`

(不确定?左上角苹果菜单 →  关于本机:显示「芯片」= Apple 芯片 = arm64,显示「处理器」= Intel = x86_64。)

**连接到 Claude Desktop:**

1. 从本仓库的 GitHub Releases 下载对应架构的 `.mcpb`;
2. Claude Desktop → **设置 → Extensions → Advanced settings → Install Extension…** → 选该 `.mcpb`;
3. 弹出「未经 Anthropic 验证」提示属预期(内部工具未上架官方目录),确认安装,然后**重启 Claude Desktop**;
4. 首次启动:因未签名,macOS Gatekeeper 可能拦截。到**系统设置 → 隐私与安全性**(下滑找到被拦提示 →「仍要打开」)放行一次;或清除隔离标记:`xattr -dr com.apple.quarantine <maskingtool-server 路径>`;
5. 首次运行后,把团队真实名单填入 `~/Library/Application Support/ContentMaskingTool/denylists/` 下的 `people.csv` / `companies.csv`(热加载,保存即生效)。

不想用 Extensions 界面、想手动接?把下面这段加进
`~/Library/Application Support/Claude/claude_desktop_config.json`(路径改成你解压独立版的位置),然后重启 Claude Desktop:

```json
{
  "mcpServers": {
    "content-masking-tool": {
      "command": "/Users/<你>/Applications/content-masking-tool/maskingtool-server/maskingtool-server",
      "args": []
    }
  }
}
```

独立版 `maskingtool-macos-<架构>-standalone.zip` 也可不依赖 Claude 单独做脱敏/还原——**完整解压**(二进制依赖同目录的 `_internal`)。

**开发者:**

```powershell
uv sync --locked --extra dev
.venv\Scripts\python.exe -m pytest                          # 全量测试
.venv\Scripts\python.exe -m maskingtool mask doc.md         # CLI
.venv\Scripts\python.exe -m maskingtool.mcp_server.server   # MCP stdio 服务器
packaging\pyinstaller\build_windows.ps1                     # Windows:清理、测试、冻结、打包、校验值
```

macOS 上对应的发布构建是 shell 脚本(默认构建本机支持的所有架构,也可指定):

```bash
uv sync --locked --extra dev
./packaging/pyinstaller/build_macos.sh              # 两个架构(Apple Silicon 主机)
./packaging/pyinstaller/build_macos.sh arm64        # 仅 Apple Silicon
./packaging/pyinstaller/build_macos.sh x86_64       # 仅 Intel
```

全新克隆环境下的 Windows/macOS 发布流程见 [RELEASING.md](RELEASING.md)。

## 数据存放在哪

| 内容 | 位置 |
|---|---|
| 脱敏输出 | `Documents\Masked Files\`(可用 settings.json `masked_output_dir` 或 `MASKINGTOOL_MASKED_DIR` 改) |
| 还原输出 | 脱敏文件旁,`.restored` 命名 |
| Vault(令牌↔真名,**敏感,勿外传**) | `%APPDATA%\ContentMaskingTool\vaults\` |
| 名单 CSV / 自定义词 / 历史 / 审核任务 / 审计日志 | `%APPDATA%\ContentMaskingTool\` 各子目录 |

分享时**只发脱敏文件**;对方确需还原时才通过安全渠道单独发对应 Vault JSON。

## 边界与已知限制(诚实声明)

- **防不住的:** 把原文拖成聊天附件或直接粘贴——纪律是"只给路径,不给内容"。Claude Code 项目里可附带 `.claude/hooks/` 强制拦截直读文档。
- 名单外名字靠 NER,高召回非保证;中文实体是当前英文模型盲区(Stage 2 计划换 zh 模型或 GLiNER)。
- 被 Markdown 行内格式拆开的名字(`**Acme** Corp`)检测不到;DOCX 中被后续编辑拆散跨 run 的令牌还原时不会重组。
- Stage 1 不做:PDF 脱敏输出/还原、OCR、模糊/别名匹配、自动更新、多人共享 Vault 同步。

## 路线图 / 支持

- macOS 打包(M11):**已完成**——原生 arm64 + x86_64 构建、双架构 CI。下一步:代码签名 / 公证以免除 Gatekeeper 提示。Stage 2 备选:中文 NER、别名匹配。
- 文档索引:架构 [CLAUDE.md](CLAUDE.md) · 进度 [PROGRESS.md](PROGRESS.md) · 团队边界指南 [USAGE.md](USAGE.md) · 隐私设计 [PRIVACY_DESIGN.md](PRIVACY_DESIGN.md) · 审计 [AUDIT_GUIDE.md](AUDIT_GUIDE.md) · 测试计划 [TESTPLAN.md](TESTPLAN.md) · 第三方声明 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
- 问题反馈:联系维护者 Jeff(内部渠道)。

*本项目按 [GNU AGPL-3.0](LICENSE) 开源发布。*

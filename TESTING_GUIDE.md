# M9 测试指南 — 在 Claude Desktop 中验证脱敏工具

> 关掉 Claude Desktop 后这份文件仍位于仓库根目录：`TESTING_GUIDE.md`
> （用记事本或任何编辑器打开即可对照操作）

## 背景

MCP server 已通过冒烟测试（用 Claude Desktop 将执行的同一条命令拉起，3 个工具、
脱敏→还原全部正常）。剩下的就是把它注册进 Claude Desktop 并在真实对话里走一遍。

**重要**：Claude Desktop 运行时会回写自己的配置文件，外部改动会被覆盖。
所以必须按下面的顺序来：**先退出 → 再改配置 → 再启动**。

---

## 第 1 步：完全退出 Claude Desktop

1. 找到屏幕右下角**系统托盘**（时间旁边，可能要点 ^ 展开）里的 Claude 图标
2. **右键 → Quit / 退出**（注意：直接点窗口右上角的 X 只是最小化，不算退出）
3. 确认退出：任务管理器里搜 "Claude" 应该没有进程

⚠️ 退出后这个 Claude Code 对话也会关闭——没关系，本指南文件就在项目根目录，
测试结果之后回来告诉我即可（会话历史还能继续）。

## 第 2 步：注册 MCP server（双击一个脚本）

双击运行：

```
packaging\dev\add-mcp-entry.bat
```

- 它会把 `content-masking-tool` 条目安全地合并进
  `%APPDATA%\Claude\claude_desktop_config.json`（先自动备份原文件）
- 如果提示 "Claude Desktop is still running"，说明第 1 步没退干净，退出后重跑
- 看到绿色 "Done." 即成功

（不想用脚本的话，手动等效操作：用记事本打开
`%APPDATA%\Claude\claude_desktop_config.json`，
在最外层 `{` 后面加入：

```json
  "mcpServers": {
    "content-masking-tool": {
      "command": "C:\\Projects\\Content masking tool\\.venv\\Scripts\\python.exe",
      "args": ["-m", "maskingtool.mcp_server.server"]
    }
  },
```
保存即可。）

## 第 3 步：启动 Claude Desktop，确认工具已加载

1. 正常打开 Claude Desktop
2. 开一个**新对话**（普通聊天，不是 Claude Code）
3. 在输入框下方/旁边找**工具图标**（滑块/插头样式），点开
4. ✅ 应该能看到 **content-masking-tool**，展开有 3 个工具：
   `mask_document`、`restore_text`、`restore_document`

看不到？→ 见文末"排障"。

## 第 4 步：核心测试 — 脱敏 → AI 处理 → 还原

演示文档已备好（含 2 个同名 Sam、2 个同名 Leah、Noah D'angelo 等所有"险名"，均为虚构占位名）：
`<repo>\demo\masking-demo-report.md`

⚠️ 别把待脱敏文件放进 `%USERPROFILE%\Claude`（Claude 的原生文件目录）——
Claude 能直接读那里的文件，可能绕过脱敏工具看到原文。

**4a. 脱敏 + 总结**。在对话里输入（明确点名工具，禁止直接读文件）：

> 请调用 content-masking-tool 的 mask_document 工具处理这个文件：
> <repo>\demo\masking-demo-report.md
> 不要用其他方式直接读取该文件。然后基于返回的脱敏文本总结这份文档。

预期：
- Claude 请求调用 `mask_document`（第一次会弹权限确认，点允许）
- 返回内容里名字全部变成 `⟦PERSON_001⟧` 这样的 token
- Claude 基于脱敏后的文本给出总结
- ✅ **检查点：总结里不出现任何原名**（Cole Han、Sam Delgado……一个都不能有）
- 记下返回里的 **vault_id**（形如 `20260714-164516-xxxxxxxx`）

**4b. 还原**。接着输入：

> 把总结里的名字还原

预期：
- Claude 调用 `restore_text`（自动带上刚才的 vault_id）
- ✅ 检查点：真名回来了，且和原文档里的名字一致

**4c. 跨会话找回（关键卖点）**。完全关闭 Claude Desktop 再打开，开个**新对话**，输入
（vault_id 换成 4a 记下的那个）：

> 用 content masking tool 的 restore_text 还原这段文字，vault_id 是 XXXX：
> ⟦PERSON_001⟧ 和 ⟦PERSON_002⟧ 负责本周发布

预期：
- ✅ 检查点：即使换了会话、重启了应用，凭 vault_id 依然能还原
  （映射存在本机磁盘 `%APPDATA%\ContentMaskingTool\vaults\`，不在内存）

## 第 5 步：记录结果

回到 Claude Code（本项目会话），告诉我每步结果（通过/失败+现象），
我会把结果记入 `Test result/M9_claude_desktop/` 并勾掉核对清单，然后进入 M10 打包。

---

## 排障

| 现象 | 处理 |
|---|---|
| 工具列表里没有 content-masking-tool | 检查配置文件里 mcpServers 条目还在不在（可能又被覆盖——确认改配置时应用确实已退出）；JSON 语法是否合法（多/少逗号） |
| 工具显示了但调用报错 | 看日志：`%APPDATA%\Claude\logs\` 下的 `mcp-server-content-masking-tool.log` 和 `mcp.log`，把报错贴给我 |
| 提示找不到 python | 确认 `<repo>\.venv\Scripts\python.exe` 存在 |
| 脱敏没生效/名字没被换 | 确认 `%APPDATA%\ContentMaskingTool\denylists\people.csv` 里有名单（63 人已装好） |
| 权限弹窗没出现也没结果 | 把对话里 Claude 的原话/错误贴给我 |

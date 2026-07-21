# 最后一环操作清单 — 抓包证明(照抄即可)

目标:截图证明三种模式下 Claude 到底往服务器发了什么。
哨兵文档已备好：`<repo>\demo\audit-sentinel-doc.md`
(里面的 Zorbix / Kwframe / Vantalio / Brixworth / Quenndale 是独一无二的编造词,
一旦出现在流量里就是铁证泄漏)。

预计 15 分钟。全程只需双击 + 复制粘贴。

---

## 步骤 1 — 启动抓包(5 秒)

双击：`<repo>\packaging\audit\1-start-capture.bat`

- 出现一个黑窗口,显示 "Starting capture on 127.0.0.1:8080"。
- **这个窗口全程别关。** 每条发往 Anthropic 的请求会实时打印 clean 或 LEAK。

## 步骤 2 — 信任证书(1 分钟,只做一次)

1. 文件资源管理器地址栏粘贴:`%USERPROFILE%\.mitmproxy` 回车
2. 双击 `mitmproxy-ca-cert.cer`
3. 点"安装证书" → 选"**当前用户**" → 下一步
4. 选"**将所有的证书都放入下列存储**" → 浏览 → 选"**受信任的根证书颁发机构**" → 确定 → 下一步 → 完成
5. 弹安全警告点"是"

> ⚠️ 测试全部结束后必须删除这张证书(见步骤 6)。

## 步骤 3 — 让 Claude 走代理(30 秒)

1. 右下角托盘 → Claude 图标右键 → **Quit**(彻底退出,不是关窗口)
2. 双击：`<repo>\packaging\audit\2-launch-claude-through-proxy.bat`
3. Claude 会自动打开,此时它的流量都经过抓包窗口

先做个连通性确认:随便问 Claude 一句"你好",抓包窗口应打印出一条
`clean ... api.anthropic.com`。**如果 Claude 连不上网/报错 → 证书没装对**,回步骤 2。

---

## 步骤 4 — 三种模式,各跑各截图

### 模式 A — 走脱敏工具(预期:全部 clean)✅ 核心证据

新对话粘贴:

```
请调用 content-masking-tool 的 mask_document 工具处理这个文件：
<repo>\demo\audit-sentinel-doc.md
不要用其他任何方式直接读取该文件。然后基于返回的脱敏文本总结这份备忘录。
```

- Claude 应返回全是 ⟦PERSON_xxx⟧ 的总结,无真名。
- **截图 1**:抓包窗口(应看到若干 `clean`,无 LEAK)。
- **截图 2**:Claude 对话(总结里无真名)。

### 模式 B — 直接传附件(预期:LEAK)⚠️ 演示那个洞

新对话,点回形针 → Add files → 选同一个文件
`demo\audit-sentinel-doc.md` → 发一句"总结这个文件"。

- **截图 3**:抓包窗口(应出现红色 `LEAK! ... Zorbix` 之类)。
- 这一步是**故意**演示"附件绕过工具"——证明为什么使用纪律是"只给路径不传附件"。
- (不想演示这个洞可跳过,但它最有说服力。)

### 模式 C — 兜底目录(预期:全部 clean)✅

新对话粘贴(文件放在项目 demo 目录,Claude 原生附件够不到,只能走工具):

```
请调用 content-masking-tool 的 mask_document 工具处理这个文件：
<repo>\demo\audit-sentinel-doc.md
然后用 restore_document 把结果还原到本地文件，只告诉我输出路径，不要显示还原内容。
```

- **截图 4**:抓包窗口(全 clean)。

---

## 步骤 5 — 出汇总表(30 秒)

1. 回到抓包窗口,按 `Ctrl+C` 停止。
2. 右键 `<repo>\packaging\audit\3-analyze.ps1`
   → 用 PowerShell 运行(或在 PowerShell 里执行它)。
3. **截图 5**:出现的判定汇总表(每条请求 clean/LEAK)。

## 步骤 6 — 收尾清理(重要,30 秒)

1. 关掉抓包窗口。
2. 删除代理证书:开始菜单搜 `certmgr.msc` 打开 → 受信任的根证书颁发机构 →
   证书 → 找到 **mitmproxy** → 右键删除。
3. 正常重启 Claude Desktop(不带代理)。

---

## 步骤 7 — 交给我

把 5 张截图(或你截的那几张)发给我,我负责:
- 核对判定、合入 `Test result/M_audit/AUDIT_REPORT.md`;
- 出最终图文审计报告给审阅者。

## 预期结论(供你对照)

| 模式 | 抓包应显示 | 说明 |
|---|---|---|
| A 走工具 | clean | 技术强制路径有效 |
| B 传附件 | LEAK | 附件绕过工具,只能靠纪律 |
| C 兜底目录 | clean | 结构强制有效 |

如果 A 或 C 出现 LEAK,或者 Claude 连不上网,**别继续**,把抓包窗口截图发我排查。

# 最后一环操作手册(抓包实测)— 用记事本打开本文件照做

> ⚠️ 第 3 步会退出 Claude Desktop,届时对话不可见。本文件路径:
> `<repo>\CAPTURE_RUNBOOK.md`
> 全程约 15 分钟。截图统一存到:
> `<repo>\Test result\M_audit\screenshots\real\`（先建好这个文件夹；该目录不会提交）

---

## 第 0 步:准备(30 秒)

- [ ] 新建文件夹 `Test result\M_audit\screenshots\real`
- [ ] 用记事本打开本文件,或打印
- [ ] 确认哨兵文档存在：`<repo>\demo\audit-sentinel-doc.md`

## 第 1 步:启动抓包(5 秒)

双击：`<repo>\packaging\audit\1-start-capture.bat`

✅ 预期:黑色窗口显示 `Starting capture on 127.0.0.1:8080` 和
`[sentinel-scan] watching 5 sentinels`。**整个测试期间不要关这个窗口。**

## 第 2 步:安装证书(1 分钟,只有你能做)

1. 按 Win+R 输入 `%USERPROFILE%\.mitmproxy` 回车
2. 双击 `mitmproxy-ca-cert.cer` → 【安装证书】
3. 存储位置:【当前用户】→ 下一步
4. 选【将所

# Security Policy

Content Masking Tool exists to keep confidential names out of AI conversations,
so we take reports of anything that undermines that guarantee seriously.

## Supported versions

Security fixes target the latest released version and `main`. Older builds are
not patched — upgrade to the latest release.

## Reporting a vulnerability or a leak

**Do not open a public issue for security problems.** This especially includes
any case where the tool **leaked an original name into masked output, into the
MCP/stdio channel, or over the network** — that is the exact failure this tool
is meant to prevent.

Please report privately via one of:

- GitHub's **[Private vulnerability reporting](https://github.com/JeffLiusGitHub/content-masking-tool/security/advisories/new)**
  (Security tab → "Report a vulnerability"); or
- direct contact with the maintainer (Jeff) through your internal channel.

Include, where possible:

- affected version / OS / architecture (arm64 or x86_64);
- a minimal input that reproduces the issue (**redact real names** — use
  placeholder names that still trigger the bug);
- what you expected vs. what happened (e.g. "name X appeared unmasked in the
  masked file / in the tool's return payload");
- relevant entries from the local audit log
  (`~/Library/Application Support/ContentMaskingTool/audit/` on macOS,
  `%APPDATA%\ContentMaskingTool\audit\` on Windows) — again with real names
  removed.

## What to expect

- Acknowledgement of your report as soon as the maintainer sees it.
- An assessment of severity and scope, and a fix or mitigation for confirmed
  issues in a subsequent release.
- Credit for the report if you want it (tell us how you'd like to be named).

## Scope notes

Some limitations are documented and by-design, not vulnerabilities (see the
"Boundaries and known limitations" section of the [README](README.md) and
[PRIVACY_DESIGN.md](PRIVACY_DESIGN.md)):

- Attaching or pasting the original document into the chat uploads it before any
  tool can intervene — this cannot be prevented by the tool.
- Names not on the deny-list rely on the NER model, which is high-recall but not
  100% (Chinese entities are a known blind spot).
- Builds are currently unsigned.

A missed name that was **not** on the deny-list and was **only** expected to be
caught by NER is a model-recall limitation, not a security vulnerability. A name
that **was** on the deny-list yet leaked **is** a security issue — please report
it.

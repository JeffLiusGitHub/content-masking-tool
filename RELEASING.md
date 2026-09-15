# Release packaging and distribution

> **Status as of 2026-09-15**
>
> - **Released baseline:** v1.2.0 remains the existing unsigned PyInstaller
>   `onedir` standalone ZIP plus platform MCPB assets. It is historical and
>   must not be modified, retagged, rebuilt in place, or republished.
> - **Next release:** unsigned-test-only MSI/PKG build projects and lifecycle
>   harnesses now exist for `[Unreleased]`; clean CI lifecycle checks passed on
>   Windows x64 and macOS arm64/x86_64. The
>   production signing/notarization and atomic publication path is not yet
>   implemented. This document does not assign a version after v1.2.0.
> - Updating this contract does not mean an MSI, PKG, production signature,
>   notarization, staple, clean-machine installation, upgrade, uninstall, or
>   MDM deployment has passed.

This file is the normative managed-installation and release contract.
[README.md](README.md) contains user-facing summaries,
[TESTPLAN.md](TESTPLAN.md) owns acceptance and evidence, and
[PROGRESS.md](PROGRESS.md) records implementation status. **MUST**, **MUST
NOT**, **SHOULD**, and **MAY** describe requirements, not current claims.

## Non-negotiable release rules

- Do not modify or republish the v1.2.0 tag, GitHub Release, or its assets.
- Do not rename a ZIP to imitate a real MSI or PKG.
- Do not publish an unsigned MSI or an unsigned, unnotarized, or unstapled PKG
  as a formal release asset. A self-signed certificate is not a production
  identity.
- Do not push, create a tag, create a GitHub Release, or publish a draft without
  explicit maintainer authorization.
- Do not place certificates, passwords, private keys, Apple/GitHub credentials,
  Vaults, deny lists, history, reviews, audit data, settings, or other user data
  in source control, caches, logs, test snapshots, or build artifacts.
- Do not describe source-test success as installer, signature, notarization, or
  target-machine verification.
- Do not disable, bypass, or weaken production signing, notarization, stapling,
  Gatekeeper, downgrade protection, or fail-closed release gates merely to make
  a build or test pass.
- New installer project files, release workflow/job/step identifiers, code
  comments, and implementation/operator documentation MUST be written in
  English.

## Current v1.2.0 baseline

These are current repository facts retained for migration context:

- PyInstaller builds an `onedir` directory named `maskingtool-server`; the
  adjacent `_internal` tree and other runtime files are required.
- The frozen entry is `maskingtool-server.exe` on Windows and
  `maskingtool-server` on macOS. The current CLI has no stable `--version`
  probe.
- The MCP surface has five tools: `mask_document`, `get_review_status`,
  `get_review_result`, `restore_text`, and `restore_document`.
- Existing scripts build unsigned platform MCPBs, unsigned standalone ZIPs,
  and checksum files. macOS build code targets native `arm64` and `x86_64`.
- The existing workflow lets platform jobs attach assets independently and has
  a best-effort `gh release create ... || true` path. That behavior does not
  satisfy the future atomic release contract.
- `pyproject.toml` and production MCPB manifests report 1.2.0 while runtime
  version metadata still contains a 1.1.0 value. Version identity must be
  consolidated before the first MSI/PKG release.

Release artifacts must be reproducible from a clean checkout. Builds must not
depend on `.mcp.json`, an existing developer environment, user AppData/home
state, local Vaults, custom deny lists, or developer-specific configuration.

## Current v1.2.0 build prerequisites (implemented)

- `uv` on `PATH`
- Node.js with `npm` on `PATH`
- Windows for the Windows build; macOS for the macOS build

Python and packaging dependencies are locked by `uv.lock` and
`packaging/mcpb/package-lock.json`. The build scripts install both sets of
locked dependencies automatically. Release builds use an isolated
`.build-venv` so an existing developer `.venv` (including audit tooling) is
never modified or included accidentally.

## Historical v1.2.0 metadata-checker scope

The v1.2.0 build scripts checked version synchronization in only these three
files:

- `pyproject.toml`
- `packaging/mcpb/manifest.json`
- `packaging/mcpb/manifest.macos.json`

The historical validation invocation was:

```powershell
.venv\Scripts\python.exe packaging\check_release_metadata.py --expected-version v1.2.0
```

The checker also verifies that both platform manifests declare the same five
MCP tools. This records existing v1.2.0-era behavior only: do not edit or
rebuild v1.2.0, and do not use this limited three-file check as the next-release
procedure. The canonical version contract for later releases is defined below.

## Current Windows ZIP/MCPB build

From any directory in PowerShell:

```powershell
& "C:\path\to\Content masking tool\packaging\pyinstaller\build_windows.ps1"
```

The script installs locked dependencies, runs the full source test suite,
builds with PyInstaller, runs the frozen MCP smoke test, and produces:

- `dist/content-masking-tool-win.mcpb`
- `dist/maskingtool-windows-standalone.zip`
- `dist/SHA256SUMS-windows.txt`

Close any Claude session using `maskingtool-server.exe` before rebuilding,
because Windows will otherwise keep the old executable locked.

## Current macOS ZIP/MCPB build

On a macOS machine:

```bash
./packaging/pyinstaller/build_macos.sh              # every arch this host can build
./packaging/pyinstaller/build_macos.sh arm64        # Apple Silicon only
./packaging/pyinstaller/build_macos.sh x86_64       # Intel only
./packaging/pyinstaller/build_macos.sh arm64 x86_64 # both, explicitly
```

The script performs the same locked build and verification flow per
architecture, then writes architecture-specific MCPB, ZIP, and SHA-256 files
under `dist/` (e.g. `content-masking-tool-macos-arm64.mcpb` and
`content-masking-tool-macos-x86_64.mcpb`).

Each architecture is built with its own uv-managed standalone CPython, so no
Homebrew `python-tk` is required — those interpreters bundle Tk. PyInstaller
produces a binary for the architecture of the interpreter it runs under, so:

- With no argument, an **Apple Silicon** host builds both `arm64` and `x86_64`
  (the Intel interpreter runs under Rosetta 2); an **Intel** host builds
  `x86_64` only.
- Building `x86_64` on Apple Silicon requires Rosetta 2:
  `softwareupdate --install-rosetta --agree-to-license`.
- `arm64` cannot be built on an Intel host — run that build on Apple Silicon.

PyInstaller cannot cross-compile between operating systems: Windows and macOS
artifacts must each be produced on their matching OS.

## Current distribution limitations

Do not commit `dist/`. Current scripts still produce MCPB, standalone ZIP, and
checksum files; those outputs describe the v1.2.0-era layout only. Network
captures, Vaults, user deny lists, AppData/home state, secrets, and local
configuration must never be release inputs.

Until the next-release pipeline is implemented, current outputs are legacy or
development artifacts and must not be represented as satisfying the MSI/PKG,
signing, notarization, or atomic-publication requirements below.

## Scope for the next formal release

The first formal release after v1.2.0 MUST provide:

- one signed, per-machine Windows x64 MSI;
- separate signed, notarized, and stapled macOS arm64 and x86_64 PKGs;
- the Windows and both macOS MCPB variants, containing the matching platform
  frozen payloads;
- SHA-256 checksums, one aggregate `release-manifest.json`, and release notes
  sourced from the matching `CHANGELOG.md` version section.

MCPB is the Claude Desktop extension format and remains a separate deliverable.
MSI/PKG replace only formal standalone ZIP assets; native installers MUST NOT
silently install, remove, or absorb the MCPB distribution path. Standalone ZIPs
MAY remain clearly labelled test/debug Actions artifacts, but MUST NOT appear
on a formal GitHub Release after v1.2.0.

For each platform/architecture, the native installer and matching MCPB SHOULD
consume the same already-signed frozen payload rather than rebuilding different
payloads after verification.

This work excludes a Device Management Portal, update agent, background
auto-updater, and masking-business-function changes.

## Release identity inputs

The following values are release blockers and MUST be approved before the
first MSI/PKG implementation is finalized:

- Windows `Manufacturer`, ARP `Publisher`, permanent MSI `UpgradeCode`, and
  expected Authenticode certificate subject;
- a company-controlled macOS package identifier, Apple Team ID, and exact
  `Developer ID Application` / `Developer ID Installer` identities;
- the next formal version and protected-environment approvers.

These values MUST NOT be inferred from a username or filled with production-
looking placeholders. Permanent non-secret identifiers are committed only
after approval; credentials and private key material remain in protected
secrets. The logical release `appId` is `content-masking-tool` unless an
explicit product decision changes it.

## Version and provenance contract

A formal version MUST be exactly `MAJOR.MINOR.PATCH`, with Git tag
`vMAJOR.MINOR.PATCH`. Each component is decimal and follows SemVer's no-leading-
zero rule except for the value zero. Formal MSI/PKG releases MUST NOT use
prerelease suffixes, build metadata, non-numeric components, or a hidden fourth
field. Windows Installer compares only the first three numeric fields, so the
mapping is direct: SemVer major → MSI major, minor → MSI minor, and patch →
MSI build. In accordance with the Windows Installer
[ProductVersion limits](https://learn.microsoft.com/en-us/windows/win32/msi/productversion),
major and minor MUST each be 0–255 and patch/build MUST be 0–65535. Validation
MUST reject out-of-range or malformed values instead of truncating,
reinterpreting, or ignoring them.

One canonical version MUST agree across:

- `pyproject.toml` and runtime version metadata;
- `maskingtool-server --version`;
- both production MCPB manifests;
- MSI `ProductVersion` and ARP `DisplayVersion`;
- each PKG version and receipt;
- Git tag, versioned `CHANGELOG.md` section, asset names, and
  `release-manifest.json`.

The planned version probe MUST print exactly
`maskingtool-server MAJOR.MINOR.PATCH`, exit zero, write no additional stdout,
avoid GUI/MCP startup, avoid user-data writes, and work through the installed
Windows executable and macOS launcher.

All formal assets MUST come from the exact tagged commit. The pipeline MUST
fail on any checkout, tag, embedded version, installer metadata, changelog, or
manifest mismatch. A faulty release is superseded by a new version; assets are
never rebuilt under an existing tag.

## Formal asset contract

`<version>` is the canonical version without the leading `v`:

```text
content-masking-tool-windows-x64-<version>.msi
content-masking-tool-macos-arm64-<version>.pkg
content-masking-tool-macos-x86_64-<version>.pkg
content-masking-tool-windows-x64-<version>.mcpb
content-masking-tool-macos-arm64-<version>.mcpb
content-masking-tool-macos-x86_64-<version>.mcpb
content-masking-tool-checksums-<version>.txt
release-manifest.json
```

`release-manifest.json` is the stable well-known manifest name; its contents
carry the version. Test installers MUST include `unsigned-test-only` in their
filename and CI display name. A formal standalone ZIP is not part of this
asset set. The aggregate checksum and manifest are cross-platform metadata
exceptions to the platform/architecture filename components; both carry the
canonical release version or identity in their name/content.

## Windows x64 MSI contract

### Technology and layout

WiX Toolset 4 is the approved default. Another technology requires an explicit
record explaining why WiX 4 cannot satisfy this contract and how the
replacement preserves MSI identity, upgrade, detection, signing, and
verification behavior.

The MSI MUST:

- be a 64-bit, per-machine package suitable for silent installation by an MDM
  agent running as `SYSTEM`, with a consistent per-machine context for install,
  repair, upgrade, and uninstall;
- install the complete PyInstaller `onedir` payload, including `_internal` and
  every runtime resource, under the stable unversioned path
  `%ProgramFiles%\Content Masking Tool\maskingtool-server\`;
- preserve the required relative position of `maskingtool-server.exe` and
  `_internal`, and never place program files under user `%APPDATA%`;
- populate Installed Apps/ARP with approved `DisplayName`, exact
  `DisplayVersion`, approved `Publisher`, install location, architecture, and
  standard Windows Installer uninstall information.

The product name is `Content Masking Tool`. Manufacturer, Publisher, signer,
and permanent UpgradeCode remain approval inputs and MUST NOT be guessed.

### Product identity and lifecycle

- Generate and approve one product-wide `UpgradeCode`; check it into installer
  metadata and never change it for ordinary upgrades.
- Give every formal version a different `ProductCode`. That code MUST remain
  stable across retries of the same immutable tag build.
- Use a Major Upgrade so a superseding MSI removes the previous managed product
  and prevents old/new per-machine copies from coexisting.
- Block downgrades with a clear Windows Installer result.
- Make same-version silent installation/repair idempotent and never change the
  install context to per-user.
- Record the actual ProductCode and UpgradeCode in `release-manifest.json`.

### Managed commands and detection

Silent installation MUST support:

```powershell
msiexec /i content-masking-tool-windows-x64-<version>.msi /qn /norestart /log install.log
```

Managed uninstall MUST support:

```powershell
msiexec /x {ProductCode} /qn /norestart /log uninstall.log
```

Both commands MUST return standard Windows Installer exit codes. The operator
documentation MUST state how MDM handles exit code 3010 if it can occur; the
package SHOULD avoid requiring a restart.

The stable MDM detection contract combines Windows Installer registration by
UpgradeCode/ProductCode, the expected installed three-part version, and the
actual executable probe:

```powershell
& "$env:ProgramFiles\Content Masking Tool\maskingtool-server\maskingtool-server.exe" --version
```

Detection MUST use Windows Installer APIs or appropriate uninstall
registration, not `Win32_Product`, which can trigger repair operations.

### User-data boundary

Per-user state remains under `%APPDATA%\ContentMaskingTool\`, including Vaults,
deny lists, manual terms, settings, history, reviews, and audit data. Install,
repair, Major Upgrade, and ordinary uninstall MUST NOT enumerate, migrate,
reset, or delete this directory. An installer running as `SYSTEM` MUST NOT
redirect application state into an arbitrary user's profile.

### Signing order and release gate

Production Windows packaging MUST:

1. Build the frozen `onedir` payload.
2. Enumerate applicable PE files and sign required project EXE/DLL/PYD files,
   preserving valid third-party signatures where applicable.
3. Verify every required internal signature and expected signer.
4. Build the MSI from that verified payload.
5. Sign the MSI with the approved Authenticode identity and an RFC 3161
   timestamp.
6. Verify the MSI signature, internal binary signatures, expected Authenticode
   certificate subject, independently approved ARP Publisher,
   embedded/displayed version, and SHA-256.

PR/local builds MAY produce a clearly labelled unsigned test-only MSI for WiX
and layout tests. A formal tag MUST fail if the production certificate is
missing, signing or timestamping fails, an expected binary is unsigned, or the
observed signer differs from the approved Authenticode certificate subject.
The ARP Publisher is separate installer metadata and MUST be validated against
its own approved value rather than inferred from the signer. A self-signed
certificate MUST NOT be represented as a formal release identity.

The unsigned test build requires Windows x64, `uv`, Node.js, the .NET 9 SDK,
and an elevated shell for the lifecycle test. From the repository root:

```powershell
packaging/pyinstaller/build_windows.ps1
packaging/msi/build_windows_msi.ps1 -TestOnly
packaging/msi/test_windows_msi.ps1 `
  -MsiPath dist/content-masking-tool-windows-x64-1.2.0-unsigned-test-only.msi `
  -MetadataPath dist/content-masking-tool-windows-x64-1.2.0-unsigned-test-only.json
```

Replace `1.2.0` with the synchronized project version after it is formally
assigned. The second command refuses to run without `-TestOnly`; its temporary
Manufacturer and UpgradeCode are deliberately not production identities. A
passing WiX compile or lifecycle test is not signing evidence.

## macOS PKG contract

### Architectures and layout

Formal releases MUST retain separate native `arm64` and `x86_64` packages;
Intel support MUST NOT be silently removed. A universal2 PKG may replace them
only after every bundled Mach-O file and dependency has been proven universal2
and the two-architecture acceptance matrix has been updated and executed.

The current product is a CLI/GUI/MCP `onedir`, not a canonical `.app` bundle.
The PKG therefore MUST preserve the complete onedir tree, including `_internal`,
at the stable machine-level path:

```text
/Library/Application Support/ContentMaskingTool/maskingtool-server/
```

It MUST NOT disguise an ordinary directory as an `.app`. A root-owned launcher
at `/usr/local/bin/maskingtool-server` MUST execute the absolute installed
binary without `eval`, user-controlled path resolution, or writable
intermediate code, and MUST support the same CLI and `--version` contract.

Program files MUST be owned by `root:wheel` and not writable by ordinary users.
Directories and required executables should normally be mode `0755`, and
non-executable resources should normally be `0644`, subject to verified runtime
needs.

### Package identity, receipt, and lifecycle

The PKG MUST use an approved company-controlled package identifier. Its exact
value and architecture-suffix policy remain release inputs and MUST NOT be
invented. Each PKG MUST:

- record the exact application version in its receipt;
- install idempotently over the same version;
- upgrade the stable layout without parallel version directories;
- expose receipt/version detection through
  `pkgutil --pkg-info <approved-package-identifier>`;
- record the actual package identifier in `release-manifest.json`.

Non-interactive MDM installation MUST support:

```bash
sudo installer -pkg content-masking-tool-macos-<architecture>-<version>.pkg -target /
```

Recommended detection combines the package receipt and expected version,
`/usr/local/bin/maskingtool-server --version`, and validation that relevant
installed Mach-O files match the asset architecture.

### User-data boundary

User data remains under each user's
`~/Library/Application Support/ContentMaskingTool/`. Install, repeat install,
upgrade, and managed uninstall MUST NOT enumerate or delete Vaults, deny lists,
manual terms, settings, history, reviews, audit data, or other user state.
Root installer scripts MUST NOT copy application state into a selected user's
home directory.

### Signing, notarization, and Gatekeeper

Production packaging for each architecture MUST:

1. Build the architecture-specific PyInstaller `onedir`.
2. Enumerate every nested Mach-O executable, library, extension, and applicable
   bundle.
3. Sign from the innermost code outward with the approved
   `Developer ID Application` identity, hardened runtime where applicable, and
   a secure timestamp.
4. Verify the signed payload and each relevant nested Mach-O individually.
5. Build and sign the final PKG with the approved `Developer ID Installer`
   identity.
6. Submit the final signed PKG using current `notarytool` and wait for success.
7. Staple the ticket, then verify signatures, expected Team ID, notarization,
   staple, Gatekeeper assessment, architecture, version, and SHA-256.

Required production commands include:

```bash
xcrun notarytool submit <pkg> --wait
xcrun stapler staple <pkg>
codesign --verify --deep --strict --verbose=2 <installed-code-path>
pkgutil --check-signature <pkg>
spctl -a -vv -t install <pkg>
xcrun stapler validate <pkg>
```

Deprecated `altool` is prohibited. Removing quarantine with
`xattr -dr com.apple.quarantine` is also prohibited as a production trust
solution. A formal tag MUST fail on a missing or invalid nested signature,
hardened-runtime requirement, secure timestamp, Installer signature,
notarization result, staple, Gatekeeper assessment, Team ID, architecture,
version, or checksum.

PR/local builds MAY create a clearly labelled unsigned test-only PKG for
payload and receipt-layout checks. Formal automation MUST NOT fall back to
unsigned output when credentials are unavailable.

The unsigned test build requires a native macOS runner with `uv`, Node.js, and
the standard Apple packaging tools. Run each architecture on its matching
runner from the repository root:

```bash
bash packaging/pyinstaller/build_macos.sh arm64
bash packaging/pkg/build_macos_pkg.sh arm64 --test-only
bash packaging/pkg/test_macos_pkg.sh \
  dist/content-masking-tool-macos-arm64-1.2.0-unsigned-test-only.pkg \
  dist/content-masking-tool-macos-arm64-1.2.0-unsigned-test-only.json

bash packaging/pyinstaller/build_macos.sh x86_64
bash packaging/pkg/build_macos_pkg.sh x86_64 --test-only
bash packaging/pkg/test_macos_pkg.sh \
  dist/content-masking-tool-macos-x86_64-1.2.0-unsigned-test-only.pkg \
  dist/content-masking-tool-macos-x86_64-1.2.0-unsigned-test-only.json
```

Replace `1.2.0` after the next version is assigned. The build script refuses
to run without `--test-only`; its temporary package identifiers are not
production identifiers, and these packages are not signed or notarized.

### Managed uninstall

Because PKG has no MSI-style uninstall, each PKG MUST install a managed-
uninstall helper at the stable machine-level path:

```text
/Library/Application Support/ContentMaskingTool/uninstall.sh
```

The helper MUST be package-owned, `root:wheel`, mode `0755`, and use only a
compiled-in allow-list plus the approved package identifier. The
`managedUninstall` value in `release-manifest.json` MUST be a literal, fully
expanded, idempotent guarded command rather than a placeholder. It invokes the
helper when present; when the helper is already absent, it returns success only
if the launcher, package-owned onedir, other allow-listed paths, and receipt are
also absent. Any inconsistent partial state is an error. The helper/command
MUST:

- use an explicit allow-list of package-owned absolute paths;
- remove only the launcher, package-owned machine-level onedir, helper, and
  other explicitly allow-listed files installed by the package;
- stop and retain both the receipt and retryable helper if launcher/program-file
  removal fails; forget the matching receipt only after that handling succeeds;
- treat already-absent owned files as success;
- reject empty, root, home, wildcard, parent, or unexpected targets;
- leave all per-user Application Support data untouched;
- avoid scanning home directories or arbitrary paths for legacy copies.

The command and its idempotence MUST be verified on both architectures before
release.

## `release-manifest.json` contract

The final job produces one aggregate UTF-8 JSON document. Its top level MUST
contain:

| Field | Contract |
|---|---|
| `schemaVersion` | integer schema revision |
| `appId` | stable logical ID, currently `content-masking-tool` |
| `version` | canonical `MAJOR.MINOR.PATCH` |
| `tag` | exact `vMAJOR.MINOR.PATCH` Git tag |
| `commitSha` | full tagged commit SHA |
| `publishedAt` | canonical RFC 3339 UTC publication timestamp selected once by the final job immediately before manifest serialization |
| `releaseNotes` | matching version section extracted from `CHANGELOG.md` |
| `assets` | one entry for every published MSI, PKG, and MCPB |

Each asset entry MUST contain:

- `platform`, `architecture`, `packageType`, `assetName`, and `assetSize` in
  bytes;
- lowercase `sha256`;
- `signingIdentity`, containing the verified Authenticode certificate subject
  for a Windows asset, the verified Developer ID identity for a macOS asset, or
  the identity of the signed payload contained by an MCPB; use `null` only when
  the format has no applicable production-signature contract;
- Windows `windowsManufacturer` and `windowsPublisher` for the independently
  approved MSI Manufacturer and ARP Publisher, or macOS `appleTeamId`, with
  genuinely non-applicable fields set to `null` rather than invented;
- Windows `productCode` and `upgradeCode`, or macOS `packageIdentifier`, again
  using `null` for non-applicable fields;
- exact `silentInstall`, `managedUninstall`, and `versionProbe` values, or
  explicit `null` for an MCPB field that has no native-installer meaning.

`publishedAt` is the pipeline's canonical publication timestamp, not GitHub's
server-assigned `published_at`, which does not exist while the complete release
is still an unpublished draft. The final job MUST capture `publishedAt` once,
freeze the manifest and checksum file, upload and verify the draft, then publish
without mutating those bytes. It MUST retain the GitHub API's actual
`published_at` response as release evidence and verify that it is not earlier
than the canonical timestamp. This distinction avoids a post-publication
manifest rewrite and a self-invalidating checksum.

The manifest schema and every value MUST be validated against the downloaded
platform artifacts before draft creation. To avoid a self-referential hash:

1. Hash and record every MSI, PKG, and MCPB in the manifest.
2. Serialize and schema-validate `release-manifest.json`.
3. Generate `content-masking-tool-checksums-<version>.txt` over every MSI, PKG,
   MCPB, and `release-manifest.json`.
4. Do not include the checksum file's own hash inside itself.

The final job MUST compare both byte size and SHA-256 for every asset before
publication.

## Future GitHub Actions release workflow

The future workflow MUST retain locked dependencies, all existing tests,
release-metadata validation, PyInstaller onedir builds, frozen smoke tests,
Windows MCPB packaging, and native macOS arm64/x86_64 MCPB packaging.

It MUST use the following fail-closed stages:

1. **Validation:** validate the strict tag and canonical version, extract the
   matching non-empty changelog section, run metadata/manifest tests, and reject
   dirty, mismatched, or unversioned release input.
2. **Platform build, sign, package, and verify:** build Windows x64 and both
   macOS architectures; run source/frozen/installer tests; sign and notarize
   only for an authorized formal tag; upload each complete platform result as
   an Actions artifact.
3. **Final release:** after every required platform job succeeds, download all
   artifacts, verify the full asset inventory, source identity, versions,
   signatures, notarization evidence, sizes, and hashes; generate the aggregate
   manifest/checksum; create one draft; upload and verify the complete set; then
   publish the draft.

Only the final release job may receive `contents: write`. Build and verification
jobs use minimum permissions, normally `contents: read`. Commands such as
`gh release create ... || true`, uncontrolled `--clobber`, or any equivalent
failure suppression are prohibited. A failed upload may leave an unpublished
draft for diagnosis, but MUST NOT create a partially populated public Release.

Release notes MUST come from the exact target-version `CHANGELOG.md` section;
an automatically generated “Full Changelog” link alone is insufficient.

Pull requests, forks, and ordinary branch builds MUST NOT access production
signing or notarization credentials and MUST NOT upload test installers to a
GitHub Release. Missing credentials on a formal tag are blocking errors, not a
reason to downgrade to unsigned output.

## Secrets and supply-chain controls

Use a protected GitHub Environment named `release-signing`, restricted to
authorized formal tags and designated reviewer approval. Secret values MUST
never appear in this document or the repository. The implementation may use
the following stable secret names:

- `WINDOWS_SIGNING_PFX_BASE64`
- `WINDOWS_SIGNING_PFX_PASSWORD`
- `APPLE_DEVELOPER_ID_APPLICATION_P12_BASE64`
- `APPLE_DEVELOPER_ID_APPLICATION_P12_PASSWORD`
- `APPLE_DEVELOPER_ID_INSTALLER_P12_BASE64`
- `APPLE_DEVELOPER_ID_INSTALLER_P12_PASSWORD`
- `APPLE_NOTARY_KEY_P8_BASE64`
- `APPLE_NOTARY_KEY_ID`
- `APPLE_NOTARY_ISSUER_ID`
- `APPLE_TEMP_KEYCHAIN_PASSWORD`

Publisher/Manufacturer, UpgradeCode, package identifier, Team ID, expected
certificate identities, and RFC 3161 timestamp URL are approved non-secret
configuration, not guessed credentials. Prefer the job's built-in
`GITHUB_TOKEN` for final release access; do not introduce a long-lived personal
access token without a documented need.

Signing jobs MUST import credentials only after build inputs are fixed, disable
command tracing that could expose values, use temporary certificate files and
a temporary macOS keychain, and delete every temporary P12, P8, keychain,
password file, or API key in an unconditional cleanup step. Credential material
MUST NOT enter caches or artifacts. Retained logs may contain only sanitized
verification output and non-secret notarization request IDs.

## Migration from v1.2.0 standalone ZIPs

Moving from v1.2.0 ZIPs to MSI/PKG is an installation-method migration, not an
in-place native-installer upgrade. The new installer establishes a managed
machine-level copy but MUST NOT scan arbitrary disks or user directories for
manually extracted v1.2.0 copies and MUST NOT delete a path merely because it
resembles the product.

No safe, repository-defined fixed legacy standalone directory currently exists.
Documentation therefore tells administrators to verify the managed installation
and remove known old copies through their own scoped policy. If an organization
later provides an explicit MDM-managed legacy path, a separate cleanup MAY be
added only when the exact absolute target, ownership, expected contents,
idempotence, parent-boundary checks, and user-data preservation are approved
and independently tested.

## Release validation requirements

Detailed cases and evidence rules live in [TESTPLAN.md](TESTPLAN.md). A formal
release is blocked until the exact tagged artifacts have dated evidence for:

- all existing source tests, strict version conversion and mismatch failures,
  the side-effect-free `--version` probe, installer metadata, changelog
  extraction, manifest schema/contents, asset inventory, and fail-closed paths;
- Windows clean-environment silent install, complete `_internal`, smoke test,
  repeat install, Major Upgrade, downgrade rejection, silent uninstall, ARP/MDM
  detection, user-data preservation, internal/MSI signatures, expected
  Publisher, timestamp, and SHA-256;
- macOS arm64 and x86_64 silent install, receipt/version, owner/mode,
  architecture, smoke test, repeat install, upgrade, managed-uninstall
  idempotence, user-data preservation, nested code signatures, Installer
  signature, expected Team ID, notarization, staple, Gatekeeper, and SHA-256.

If a GitHub-hosted runner cannot reliably exercise a system scenario, the
implementation MUST provide a repeatable local/VM script and English operator
instructions. The case remains **not run** until evidence from the required
target environment is recorded.

## Rollback contract

Rollback is an MDM deployment decision, not permission to replace an existing
tag's assets. Before rollout, retain the last known-good signed installers and
manifests, prove whether the prior version can read state written by the new
version, and define staged deployment, stop conditions, privacy-appropriate
backup guidance, and a responsible operator.

- Windows downgrade protection remains enabled. To return to an earlier MSI,
  silently uninstall the current ProductCode, then install the last known-good
  signed MSI; leave `%APPDATA%\ContentMaskingTool\` untouched.
- On macOS, run the current package's exact managed uninstaller, verify that
  only package-owned machine files and its receipt were removed, then install
  the last known-good signed/notarized/stapled PKG; leave each user's
  Application Support data untouched.
- MCPB rollback is separate and uses Claude Desktop's supported extension
  installation path.

If backward state compatibility is unproven, rollback is blocked and a new
forward-fix release is required.

## Release operator checklist

Every box requires evidence for the exact tag and commit.

### Approval and identity

- [ ] Explicit authorization to push, tag, and release has been received.
- [ ] The next version is approved; it is not assumed to be v1.3.0.
- [ ] Windows Manufacturer, ARP Publisher, permanent UpgradeCode, Authenticode
  identity, and timestamp service are approved.
- [ ] macOS package-identifier policy, Apple Team ID, and both Developer ID
  identities are approved.
- [ ] `release-signing` protection, reviewers, and required secret names are
  configured without exposing values.

### Source and metadata

- [ ] The release commit is clean, reviewed, and reproducible from a clean
  checkout with locked dependencies.
- [ ] Runtime, MCPB, installer, tag, changelog, asset names, and manifest agree
  on the exact version and commit.
- [ ] `maskingtool-server --version` passes without side effects.
- [ ] Both MCPB manifests declare the same five tools.
- [ ] No secret or user data is present in build inputs or output artifacts.

### Windows

- [ ] The x64 onedir and `_internal` payload are complete.
- [ ] Required internal PE files and the final per-machine MSI are signed,
  timestamped, and verified against the approved Authenticode subject; the ARP
  Publisher independently matches its approved installer metadata.
- [ ] ProductCode is new for this version and UpgradeCode is unchanged.
- [ ] ARP metadata and installed MDM/version detection match the manifest.
- [ ] Silent install, repeat install, Major Upgrade, downgrade block, silent
  uninstall, smoke test, and user-data preservation pass in a clean Windows
  environment.

### macOS

- [ ] Native arm64 and x86_64 payloads have the expected architecture,
  ownership, modes, onedir contents, launcher, and receipt metadata.
- [ ] Nested code is signed inside-out and verified with the approved
  Developer ID Application identity.
- [ ] Each final PKG has the approved identifier, version, Developer ID
  Installer signature, Team ID, successful notarization, and valid staple.
- [ ] Gatekeeper passes without an `xattr` bypass.
- [ ] Silent install, repeat install, upgrade, managed-uninstall idempotence,
  smoke/version probes, and user-data preservation pass on both architectures.

### Finalization

- [ ] All required platform artifacts came from the same tag and commit; no
  standalone ZIP is in the formal asset set.
- [ ] `release-manifest.json`, asset sizes, SHA-256 values, and the checksum file
  validate; release notes match the target changelog section.
- [ ] Temporary signing/notarization material has been removed and sanitized
  logs contain no secrets.
- [ ] Only the final job has `contents: write` and all required jobs succeeded.
- [ ] One complete draft was uploaded and verified before publication.
- [ ] Downloaded public assets were rechecked against signatures and hashes.
- [ ] Staged MDM rollout, monitoring, stop conditions, and rollback assets are
  ready.

## Current readiness

As of 2026-09-14, the next MSI/PKG release is **not releasable**. Installer
projects, approved permanent identities, canonical runtime version probing,
production signing, notarization, manifest generation, unified final-job
orchestration, and clean target-machine evidence remain implementation work.

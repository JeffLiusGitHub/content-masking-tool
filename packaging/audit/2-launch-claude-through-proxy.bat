@echo off
REM Launches Claude Desktop routed through the local capture proxy, using
REM per-process env vars only — your system-wide proxy is NOT changed.
REM Requires: the capture (1-start-capture.bat) is already running, AND the
REM mitmproxy CA cert has been trusted (see AUDIT_GUIDE.md step 2).
REM
REM Fully quit Claude Desktop before running this (tray icon -> Quit).

set HTTP_PROXY=http://127.0.0.1:8080
set HTTPS_PROXY=http://127.0.0.1:8080
set NODE_EXTRA_CA_CERTS=%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.pem

set CLAUDE=%LOCALAPPDATA%\AnthropicClaude\claude.exe
if not exist "%CLAUDE%" set CLAUDE=%LOCALAPPDATA%\Programs\claude\Claude.exe
REM Current Claude Desktop releases may be installed as an MSIX package under
REM WindowsApps. Prefer the executable path reported by a running Desktop
REM process, then fall back to resolving the installed Appx package.
if not exist "%CLAUDE%" for /f "usebackq delims=" %%I in (`powershell.exe -NoProfile -Command "$p = Get-CimInstance Win32_Process -Filter 'Name = ''claude.exe''' | Where-Object { $_.ExecutablePath -like '*WindowsApps*' } | Select-Object -First 1 -ExpandProperty ExecutablePath; if ($p) { $p }"`) do set CLAUDE=%%I
if not exist "%CLAUDE%" for /f "usebackq delims=" %%I in (`powershell.exe -NoProfile -Command "$pkg = Get-AppxPackage | Where-Object { $_.Name -like '*Claude*' } | Select-Object -First 1; if ($pkg) { Join-Path $pkg.InstallLocation 'app\Claude.exe' }"`) do set CLAUDE=%%I
if not exist "%CLAUDE%" (
  echo Could not find claude.exe automatically.
  echo Edit this file and set CLAUDE= to your Claude Desktop path.
  pause
  exit /b 1
)

echo Launching Claude through proxy 127.0.0.1:8080 ...
echo (NODE_EXTRA_CA_CERTS set so Electron trusts the mitmproxy cert)
start "" "%CLAUDE%"

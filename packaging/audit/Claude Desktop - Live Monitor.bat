@echo off
setlocal

rem One-click, user-scoped Claude Desktop network inspection.
rem This does not change the Windows system proxy.

for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
set "AUDIT=%ROOT%\packaging\audit"
set "MITMWEB=%ROOT%\.venv\Scripts\mitmweb.exe"
set "CA=%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.pem"
set "PROXY=http://127.0.0.1:8080"

if not exist "%MITMWEB%" (
  echo ERROR: mitmweb was not found at:
  echo %MITMWEB%
  pause
  exit /b 1
)

if not exist "%CA%" (
  echo ERROR: the mitmproxy CA certificate file is missing:
  echo %CA%
  pause
  exit /b 1
)

rem Reuse an existing live monitor, or start one if ports 8080/8081 are free.
powershell.exe -NoProfile -Command "if (Get-NetTCPConnection -State Listen -LocalPort 8081 -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
  start "Claude Network Monitor" /min "%MITMWEB%" ^
    --mode local:claude.exe ^
    --listen-host 127.0.0.1 ^
    --listen-port 8080 ^
    --web-host 127.0.0.1 ^
    --web-port 8081 ^
    --set web_open_browser=true ^
    --set view_filter="~d anthropic.com|~d claude.ai" ^
    -s "%AUDIT%\sentinel_scan.py" ^
    --set sentinels="Zorbix,Kwframe,Vantalio,Brixworth,Quenndale" ^
    --set auditout="%AUDIT%\audit-network.jsonl" ^
    --set save_stream_file="%AUDIT%\capture.flows"
  timeout /t 2 /nobreak >nul
) else (
  start "" "http://127.0.0.1:8081/"
)

rem Local-capture mode follows every claude.exe connection at OS level. Keep
rem the CA variable as an additional trust hint for Claude's Node subprocesses.
set "NODE_EXTRA_CA_CERTS=%CA%"

set "CLAUDE_DESKTOP=%LOCALAPPDATA%\AnthropicClaude\claude.exe"
if not exist "%CLAUDE_DESKTOP%" set "CLAUDE_DESKTOP=%LOCALAPPDATA%\Programs\claude\Claude.exe"
if not exist "%CLAUDE_DESKTOP%" for /f "usebackq delims=" %%I in (`powershell.exe -NoProfile -Command "$pkg = Get-AppxPackage | Where-Object { $_.Name -like '*Claude*' } | Select-Object -First 1; if ($pkg) { Join-Path $pkg.InstallLocation 'app\Claude.exe' }"`) do set "CLAUDE_DESKTOP=%%I"

if not exist "%CLAUDE_DESKTOP%" (
  echo ERROR: Claude Desktop could not be found automatically.
  pause
  exit /b 1
)

echo ============================================================
echo Claude Desktop is starting through the local live monitor.
echo Live view: http://127.0.0.1:8081/
echo ============================================================
echo.

start "Claude Desktop - MONITORED" "%CLAUDE_DESKTOP%"

endlocal

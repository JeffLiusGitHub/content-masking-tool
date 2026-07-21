@echo off
setlocal

rem One-click, user-scoped Claude Code network inspection.
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

rem Start the live web UI. It opens http://127.0.0.1:8081 automatically.
start "Claude Network Monitor" /min "%MITMWEB%" ^
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

rem Give the proxy a moment to bind before Claude Code starts.
timeout /t 2 /nobreak >nul

set "HTTP_PROXY=%PROXY%"
set "HTTPS_PROXY=%PROXY%"
set "ALL_PROXY=%PROXY%"
set "NO_PROXY=127.0.0.1,localhost"
set "NODE_EXTRA_CA_CERTS=%CA%"

title Claude Code - MONITORED
echo ============================================================
echo Claude Code traffic is routed through the local live monitor.
echo Live view: http://127.0.0.1:8081/
echo Close this window to end Claude Code. The monitor is separate.
echo ============================================================
echo.

claude

endlocal

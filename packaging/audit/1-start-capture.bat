@echo off
REM Starts the mitmproxy capture with the sentinel scanner. Leave this window
REM open during the whole test. Ctrl+C to stop when done.
REM Sentinels = names that appear ONLY in the source test document, so any
REM occurrence on the wire is an unambiguous leak.
set HERE=%~dp0
for %%I in ("%HERE%..\..") do set "ROOT=%%~fI"
set "VENV=%ROOT%\.venv\Scripts"
echo Starting capture on 127.0.0.1:8080 ...
echo Watch this window: each Anthropic request prints "clean" or "LEAK!".
echo Verdicts also saved to %HERE%audit-network.jsonl
echo.
"%VENV%\mitmdump.exe" --listen-port 8080 ^
  -s "%HERE%sentinel_scan.py" ^
  --set sentinels="Zorbix,Kwframe,Vantalio,Brixworth,Quenndale" ^
  --set auditout="%HERE%audit-network.jsonl" ^
  --set save_stream_file="%HERE%capture.flows"

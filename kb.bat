@echo off
REM 四层认知引擎 CLI 包装脚本 (Windows)
REM 供 Obsidian Shell Commands 插件调用，无需关心工作目录。
REM 用法: kb.bat ingest -t "文本"  |  kb.bat qa "问题"  |  kb.bat process --all

setlocal
set "KB_ROOT=%~dp0"
cd /d "%KB_ROOT%"
python kb.py %*
endlocal

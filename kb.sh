#!/usr/bin/env bash
# 四层认知引擎 CLI 包装脚本 (Unix/macOS/Linux)
# 供 Obsidian Shell Commands 插件调用，无需关心工作目录。
# 用法: kb.sh ingest -t "文本"  |  kb.sh qa "问题"  |  kb.sh process --all

set -e
KB_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$KB_ROOT"
python kb.py "$@"

"""四层认知引擎 - 项目根入口脚本。

用法:
    python kb.py ingest -u https://github.com/owner/repo
    python kb.py ingest -t "一条想法..."
    python kb.py process --all
    python kb.py index
    python kb.py qa "什么是 Agent 架构?"
    python kb.py wiki --all
    python kb.py stats

等价于: python -m src.cli <command>
"""

import sys

from src.cli import main

if __name__ == "__main__":
    sys.exit(main())

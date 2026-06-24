"""全局配置与路径常量。

职责:
    * 通过 python-dotenv 加载 .env
    * 暴露四层目录的绝对路径 (raw / processed / wiki / index)
    * 暴露各层默认 LiteLLM 模型字符串
    * 集中管理阈值常量 (关联打分 / Wiki 触发簇大小等)

所有模块统一 `from src.config import settings` 使用。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

# 加载项目根 .env (脚本可能从任意目录调用)
_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Settings:
    """全局配置单例 (实例化即可，无需重复加载)。"""

    # ---- 路径 ----
    PROJECT_ROOT: Path = _PROJECT_ROOT
    KB_ROOT: Path = _PROJECT_ROOT / os.getenv("KB_ROOT", "my_kb")

    RAW_DIR: Path = KB_ROOT / "raw"
    PROCESSED_DIR: Path = KB_ROOT / "processed"
    WIKI_DIR: Path = KB_ROOT / "wiki"
    INDEX_DIR: Path = KB_ROOT / "index"

    # ---- LLM 模型路由 (一层一模型) ----
    MODEL_PROCESS: str = os.getenv("MODEL_PROCESS", "minimax/MiniMax-M3")
    MODEL_WIKI: str = os.getenv("MODEL_WIKI", "minimax/MiniMax-M3")
    MODEL_QA: str = os.getenv("MODEL_QA", "minimax/MiniMax-M3")
    MODEL_FALLBACK: str = os.getenv("MODEL_FALLBACK", "minimax/MiniMax-M3")

    # ---- 外部 API ----
    JINA_API_KEY: str | None = os.getenv("JINA_API_KEY") or None
    LITELLM_LOG: str = os.getenv("LITELLM_LOG", "INFO")

    # ---- 算法阈值 ----
    # 关联打分: 标签重合 +3/个，标题分词重合 +1/个；总分 >= 此阈值才建立双链
    RELATION_SCORE_THRESHOLD: int = 4
    # Wiki 编译触发: 关联簇笔记数 >= 此值才自动编译
    WIKI_CLUSTER_MIN_NOTES: int = 3
    # 关联计算时返回的 Top-N 老笔记数量上限
    RELATION_TOP_N: int = 10

    # ---- 调用参数 ----
    LLM_TEMPERATURE: float = 0.3
    LLM_TIMEOUT: int = 120

    def ensure_dirs(self) -> None:
        """幂等创建四层存储目录。"""
        for d in (self.RAW_DIR, self.PROCESSED_DIR, self.WIKI_DIR, self.INDEX_DIR):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()

"""全包共享的 Pydantic 数据模型。

对应架构 V2.1 各层数据结构:
    RawEntry        - 归一化后的原料层条目 (模块 A -> B1)
    ProcessedNote   - 加工引擎的 LLM 结构化输出 (模块 B2)
    RelationHit     - 确定性关联打分的一次命中 (模块 B3 关联引擎)
    IndexSummary    - summaries.json 中的一条摘要卡片
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------- 原料层 ----------
class SourceType(str, Enum):
    MANUAL = "manual"
    LINK = "link"
    API = "api"
    CRON = "cron"
    FILE = "file"


class RawStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    INDEXED = "indexed"


class RawEntry(BaseModel):
    """归一化后的原料条目，对应 architecture.md 中的 RawEntry。"""

    id: str = Field(..., description="raw_{timestamp}_{short_hash}")
    source_type: SourceType
    source_url: Optional[str] = None
    original_text: str
    ingested_at: str = Field(..., description="ISO8601 时间戳")
    status: RawStatus = RawStatus.PENDING

    def to_meta(self) -> dict:
        """生成 .meta.json 内容 (不含 original_text)。"""
        return self.model_dump(mode="json", exclude={"original_text"})


# ---------- 加工层 (LLM JSON Mode 输出 Schema) ----------
class ProcessedNote(BaseModel):
    """LLM 加工引擎的强类型输出，会被拼装为 Obsidian .md。"""

    title: str = Field(..., description="笔记标题，简洁有信息量")
    conclusion: str = Field(
        ..., description="2-3 句话核心结论，对应 ## 核心结论 段落"
    )
    body_markdown: str = Field(
        ..., description="正文重写，包含 [[双链概念]] 标记"
    )
    tags: list[str] = Field(default_factory=list, description="标签列表")
    related: list[str] = Field(
        default_factory=list, description="相关笔记标题 (由关联引擎填充，LLM 留空即可)"
    )


# ---------- 关联打分 ----------
class RelationHit(BaseModel):
    """一次关联命中: 目标笔记文件名 + 得分。"""

    filename: str
    score: int


# ---------- 索引层摘要卡片 ----------
class IndexSummary(BaseModel):
    """summaries.json 中的单条摘要卡片。"""

    title: str
    conclusion: str
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    source: Optional[str] = None
    updated: Optional[str] = None

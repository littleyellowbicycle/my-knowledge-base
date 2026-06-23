"""MCP (Model Context Protocol) 服务 — 把四层认知引擎封装为标准 Agent 工具。

供 Claude Desktop / Cursor / 其他 MCP 客户端通过 stdio 协议调用。
让 AI Agent 在对话中直接操作知识库：抓取归档、加工笔记、问答、Wiki 编译。

启动方式 (二选一):
    1. 直接运行:        python kb.py mcp
    2. 配置到客户端:     在 claude_desktop_config.json / mcp_servers.json 中添加:
        {
          "mcpServers": {
            "my-knowledge-base": {
              "command": "python",
              "args": ["D:\\project\\my-konwledge-base\\kb.py", "mcp"]
            }
          }
        }

工具清单:
    ingest_url(url)            抓取 URL → 归档 raw 层 (不加工)
    ingest_text(text)         手动录入文本 → 归档 raw 层 (不加工)
    process_pending()         批量加工所有 pending 原料为结构化笔记
    ask(question)             两步走问答 (Wiki 优先 → 降级 Processed)
    compile_wiki(topic?)      编译 Wiki 综述 (不带 topic 编译全部达标簇)
    rebuild_index()           重建索引层
    stats()                   各层条目统计
"""
from __future__ import annotations

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.config import settings
from src import raw_store, processor, indexer, qa_engine, wiki_compiler

logger = logging.getLogger(__name__)

mcp = FastMCP("MyKnowledgeBase")


@mcp.tool()
def ingest_url(url: str) -> str:
    """抓取一个 URL (GitHub/微信公众号/通用网页) 并归档到原料层。
    不执行 LLM 加工，需后续调用 process_pending 才会生成结构化笔记。

    Args:
        url: 目标链接 (如 https://github.com/owner/repo)
    """
    try:
        settings.ensure_dirs()
        entry = raw_store.save_link(url)
        return f"已抓取并归档到原料层: id={entry.id} source_type={entry.source_type.value}"
    except Exception as e:  # noqa: BLE001
        return f"抓取失败: {e}"


@mcp.tool()
def ingest_text(text: str) -> str:
    """手动录入一段文本到原料层。
    不执行 LLM 加工，需后续调用 process_pending 才会生成结构化笔记。

    Args:
        text: 待归档的原文 (笔记/会议纪要/拷贝的文章段落)
    """
    try:
        settings.ensure_dirs()
        entry = raw_store.save_manual(text)
        return f"已归档到原料层: id={entry.id}"
    except Exception as e:  # noqa: BLE001
        return f"录入失败: {e}"


@mcp.tool()
def process_pending() -> str:
    """批量加工所有 pending 状态的原料为结构化 Obsidian 笔记。
    会自动触发关联引擎为每篇笔记建立双链关系。
    返回成功加工的笔记文件名列表及失败原因。
    """
    try:
        settings.ensure_dirs()
        paths = processor.process_pending()
        if not paths:
            return "没有待加工的原料 (raw 层 pending 队列为空)。"
        names = "\n".join(f"- {p.name}" for p in paths)
        return f"成功加工 {len(paths)} 篇笔记:\n{names}"
    except Exception as e:  # noqa: BLE001
        return f"加工失败: {e}"


@mcp.tool()
def ask(question: str) -> str:
    """对个人知识库提问，返回带 [[]] 来源链接的回答。
    采用两步走检索：先查 Wiki 综述层，命中即答宏观问题；
    未命中则降级到 Processed 原子笔记层答细节问题。
    若索引为空会自动重建。

    Args:
        question: 用户问题 (中文或英文)
    """
    try:
        return qa_engine.qa(question, auto_rebuild=True)
    except Exception as e:  # noqa: BLE001
        return f"问答出错: {e}"


@mcp.tool()
def compile_wiki(topic: Optional[str] = None) -> str:
    """编译 Wiki 系统性综述页。
    不指定 topic 时扫描所有节点数 >= 3 的关联簇全量编译 (跳过已编译簇)；
    指定 topic 时按标签/主题编译单个簇。

    Args:
        topic: 可选，标签或主题名 (如 "AI" / "Agent")
    """
    try:
        settings.ensure_dirs()
        if topic:
            path = wiki_compiler.compile_wiki(topic)
            if path:
                return f"Wiki 综述已生成: {path.name}"
            return f"未找到与主题「{topic}」匹配的关联簇，或簇节点数不足。"
        else:
            paths = wiki_compiler.compile_all_wiki()
            if not paths:
                return "未发现新的达标关联簇 (已有对应 wiki 或无 >= 3 节点的簇)。"
            names = "\n".join(f"- {p.name}" for p in paths)
            return f"成功编译 {len(paths)} 篇 wiki 综述:\n{names}"
    except Exception as e:  # noqa: BLE001
        return f"Wiki 编译失败: {e}"


@mcp.tool()
def rebuild_index() -> str:
    """全量扫描 processed/ 和 wiki/ 重建索引层 (summaries/tags/links/moc JSON)。
    问答和 Wiki 编译依赖索引，新增笔记后务必调用。
    """
    try:
        settings.ensure_dirs()
        stats = indexer.rebuild_index()
        return (
            f"索引重建完成: 笔记 {stats['notes']} 篇 / 综述 {stats['wiki']} 篇 / "
            f"标签 {stats['tags']} 个 / 主题 {stats['topics']} 个"
        )
    except Exception as e:  # noqa: BLE001
        return f"重建失败: {e}"


@mcp.tool()
def stats() -> str:
    """返回四层认知引擎各层当前条目统计 (raw/processed/wiki/index)。无参数。"""
    try:
        settings.ensure_dirs()
        raw_n = len(list(settings.RAW_DIR.glob("*.meta.json")))
        proc_n = len(list(settings.PROCESSED_DIR.glob("*.md")))
        wiki_n = len(list(settings.WIKI_DIR.glob("*.md")))
        idx_n = len(list(settings.INDEX_DIR.glob("*.json")))
        return (
            f"原料层 raw:      {raw_n} 条\n"
            f"加工层 processed: {proc_n} 篇\n"
            f"编译层 wiki:     {wiki_n} 篇\n"
            f"索引层 index:    {idx_n} 个文件"
        )
    except Exception as e:  # noqa: BLE001
        return f"统计失败: {e}"


def run_mcp() -> None:
    """以 stdio 模式启动 MCP 服务，供本地 Agent 调用。"""
    settings.ensure_dirs()
    mcp.run()


if __name__ == "__main__":
    run_mcp()
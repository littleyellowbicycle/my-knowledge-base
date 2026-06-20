"""命令行入口 - 四层认知引擎统一 CLI。

命令清单:
    kb ingest -u <url>              抓取链接并落盘 raw/
    kb ingest -t "<text>"           手动输入落盘 raw/
    kb ingest --stdin               从 stdin 读取 (管道时自动检测)
    kb process [--all|--raw <id>]   加工原料为 Obsidian 笔记 (含关联引擎钩子)
    kb index                        全量重建索引层
    kb qa "<question>"              问答流 (查索引->读结论->作答)
    kb wiki [--all|--topic <tag>]   Wiki 编译 (关联簇 >= 3)
    kb wiki --lint                  Wiki 健康自检
    kb list [raw|processed|wiki]    列出条目
    kb stats                        显示各层统计

返回码: 0 成功，1 业务错误，2 参数错误。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from src.config import settings
from src import raw_store
from src import processor
from src import indexer
from src import qa_engine
from src import wiki_compiler


# ---------- 通用工具 ----------
def _emit(msg: str, *, file=None) -> None:
    print(msg, flush=True, file=file)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------- 子命令 ----------
def cmd_ingest(args: argparse.Namespace) -> int:
    if args.url:
        entry = raw_store.save_link(args.url)
        _emit(f"已抓取并归档: {entry.id} (source={entry.source_url})")
        return 0
    # 手动输入
    if args.stdin or (not sys.stdin.isatty() and args.text is None):
        text = sys.stdin.read()
    elif args.text is not None:
        text = args.text
    else:
        _emit("错误: 需要提供 --url 或 --text 或 --stdin", file=sys.stderr)
        return 2
    if not text or not text.strip():
        _emit("错误: 输入内容为空", file=sys.stderr)
        return 2
    entry = raw_store.save_manual(text)
    _emit(f"已归档手动输入: {entry.id}")
    return 0


def cmd_process(args: argparse.Namespace) -> int:
    if args.all:
        paths = processor.process_pending()
        _emit(f"批量加工完成: {len(paths)} 篇")
        for p in paths:
            _emit(f"  -> {p.name}")
        return 0
    if args.raw:
        p = processor.process_note(args.raw)
        _emit(f"加工完成: {p.name}")
        return 0
    _emit("错误: 需要 --all 或 --raw <id>", file=sys.stderr)
    return 2


def cmd_index(args: argparse.Namespace) -> int:
    stats = indexer.rebuild_index()
    _emit(f"索引重建完成: {json.dumps(stats, ensure_ascii=False)}")
    return 0


def cmd_qa(args: argparse.Namespace) -> int:
    answer = qa_engine.qa(args.question, auto_rebuild=args.auto_rebuild)
    _emit(answer)
    return 0


def cmd_wiki(args: argparse.Namespace) -> int:
    if args.lint:
        report = wiki_compiler.lint_wiki()
        _emit(f"Wiki 自检: {json.dumps(report, ensure_ascii=False)}")
        return 0
    if args.all:
        paths = wiki_compiler.compile_all_wiki(force_llm=args.force_llm)
        _emit(f"编译完成: {len(paths)} 篇综述")
        for p in paths:
            _emit(f"  -> {p.name}")
        return 0
    if args.topic:
        p = wiki_compiler.compile_wiki(args.topic, force_llm=args.force_llm)
        if p:
            _emit(f"编译完成: {p.name}")
            return 0
        _emit("簇节点数不足或无有效笔记，未生成综述")
        return 1
    _emit("错误: 需要 --all / --topic <tag> / --lint", file=sys.stderr)
    return 2


def cmd_list(args: argparse.Namespace) -> int:
    kind = args.kind
    if kind == "raw":
        for rid in raw_store.list_raw():
            _emit(rid)
    elif kind == "processed":
        for p in sorted(settings.PROCESSED_DIR.glob("*.md")):
            _emit(p.name)
    elif kind == "wiki":
        for p in sorted(settings.WIKI_DIR.glob("*.md")):
            _emit(p.name)
    elif kind == "pending":
        for rid in raw_store.iter_pending():
            _emit(rid)
    else:
        _emit(f"未知列表类型: {kind}", file=sys.stderr)
        return 2
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    raw_n = len(list(settings.RAW_DIR.glob("*.meta.json")))
    proc_n = len(list(settings.PROCESSED_DIR.glob("*.md")))
    wiki_n = len(list(settings.WIKI_DIR.glob("*.md")))
    idx_n = len(list(settings.INDEX_DIR.glob("*.json")))
    _emit(f"原料层 raw:      {raw_n} 条")
    _emit(f"加工层 processed: {proc_n} 篇")
    _emit(f"编译层 wiki:     {wiki_n} 篇")
    _emit(f"索引层 index:    {idx_n} 个文件")
    return 0


# ---------- 解析器构建 ----------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kb",
        description="四层认知引擎 - 个人知识库 CLI",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="调试日志")
    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    p = sub.add_parser("ingest", help="录入原料 (链接抓取 / 手动输入)")
    p.add_argument("-u", "--url", help="目标 URL (自动路由抓取)")
    p.add_argument("-t", "--text", help="手动输入文本")
    p.add_argument("--stdin", action="store_true", help="从 stdin 读取 (管道时自动检测)")
    p.set_defaults(func=cmd_ingest)

    # process
    p = sub.add_parser("process", help="加工原料为 Obsidian 笔记")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true", help="加工所有 pending 原料")
    g.add_argument("--raw", help="指定原料 ID 加工")
    p.set_defaults(func=cmd_process)

    # index
    p = sub.add_parser("index", help="全量重建索引层")
    p.set_defaults(func=cmd_index)

    # qa
    p = sub.add_parser("qa", help="问答流")
    p.add_argument("question", help="问题")
    p.add_argument("--auto-rebuild", action="store_true", help="索引为空时自动重建")
    p.set_defaults(func=cmd_qa)

    # wiki
    p = sub.add_parser("wiki", help="Wiki 编译层")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true", help="编译所有达标簇")
    g.add_argument("--topic", help="按标签主题编译")
    g.add_argument("--lint", action="store_true", help="Wiki 健康自检")
    p.add_argument("--force-llm", action="store_true", help="跳过 llmwiki，强制自研编译")
    p.set_defaults(func=cmd_wiki)

    # list
    p = sub.add_parser("list", help="列出条目")
    p.add_argument("kind", choices=["raw", "processed", "wiki", "pending"],
                   help="列表类型")
    p.set_defaults(func=cmd_list)

    # stats
    p = sub.add_parser("stats", help="各层统计")
    p.set_defaults(func=cmd_stats)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    settings.ensure_dirs()
    try:
        return args.func(args)
    except Exception as e:  # noqa: BLE001
        logging.error("命令执行失败: %s", e, exc_info=args.verbose)
        _emit(f"错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

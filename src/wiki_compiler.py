"""Wiki 编译层 (模块 B4) - Karpathy 理念落地。

设计 (对应 Implementation_plan Step 6):
    1. 扫描 links.json，用连通分量算法找出节点数 >= 阈值的关联簇
    2. 对每个簇调用编译器生成系统性综述:
       - 优先使用 llmwiki 包 (Hosuke/llmwiki) 作为运行时基座
       - 若 llmwiki 不可用/失败，回退到自研 LLM 编译 (用 MODEL_WIKI 即 Kimi 128k)
    3. 后处理 (胶水层核心): 用确定性关联覆盖 LLM 生成的悬空双链，
       在文末追加 ## 相关笔记 (确定性关联) 段
    4. 保存到 wiki/{topic}.md (带 Frontmatter)，并触发索引增量更新

对外暴露:
    find_clusters()                  -> list[list[str]]   连通分量 (stem 列表)
    compile_wiki(topic_or_stems)     -> Path              编译单个簇
    compile_all_wiki()               -> list[Path]        编译所有达标簇
    rebuild_wiki()                   -> list[Path]        清空 wiki/ 后全量重编
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import re
import shutil
import tempfile
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

import frontmatter

from src.config import settings
from src.indexer import load_links, load_tags, load_summaries, rebuild_index
from src.llm_adapter import llm

logger = logging.getLogger(__name__)

# llmwiki 可选导入 (运行时基座，缺失则走自研编译)
try:  # pragma: no cover - 取决于环境
    import llmwiki as _llmwiki  # type: ignore
    _HAS_LLMWIKI = True
except ImportError:
    _llmwiki = None
    _HAS_LLMWIKI = False

_LINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")


# ---------- 关联簇检测 ----------
def _build_graph(links: dict[str, dict[str, list[str]]]) -> dict[str, set[str]]:
    """从 links.json 构建无向图 (stem -> 邻接 stem 集合)。含孤立节点。"""
    g: dict[str, set[str]] = defaultdict(set)
    # 确保所有节点入图 (含孤立)
    for stem in links:
        g.setdefault(stem, set())
    for stem, dirs in links.items():
        for other in dirs.get("outgoing", []):
            g[stem].add(other)
            g[other].add(stem)
        for other in dirs.get("incoming", []):
            g[stem].add(other)
            g[other].add(stem)
    return g


def find_clusters(min_size: Optional[int] = None) -> list[list[str]]:
    """找出所有连通分量，返回节点数 >= min_size 的簇 (stem 列表)。"""
    min_size = settings.WIKI_CLUSTER_MIN_NOTES if min_size is None else min_size
    links = load_links()
    if not links:
        return []
    g = _build_graph(links)
    visited: set[str] = set()
    clusters: list[list[str]] = []
    for start in links.keys():
        if start in visited:
            continue
        # BFS
        comp: list[str] = []
        q = deque([start])
        visited.add(start)
        while q:
            node = q.popleft()
            comp.append(node)
            for nxt in g.get(node, set()):
                if nxt not in visited:
                    visited.add(nxt)
                    q.append(nxt)
        if len(comp) >= min_size:
            clusters.append(sorted(comp))
    clusters.sort(key=lambda c: (-len(c), c[0]))
    return clusters


# ---------- 簇命名 ----------
def _name_cluster(stems: list[str]) -> str:
    """用簇内最频繁标签命名；无标签则用首篇 stem。"""
    tags_map = load_tags()
    summaries = load_summaries()
    # 统计簇内笔记的标签频次
    stem_to_file = {Path(s).stem: s for s in summaries.keys()}
    freq: dict[str, int] = defaultdict(int)
    for stem in stems:
        fname = stem_to_file.get(stem) or f"{stem}.md"
        s = summaries.get(fname, {})
        for t in s.get("tags", []):
            freq[t] += 1
    if freq:
        return max(freq.items(), key=lambda kv: (kv[1], kv[0]))[0]
    return stems[0]


# ---------- 读取簇内笔记内容 ----------
def _read_note_full(stem: str) -> dict:
    """读取单篇笔记的完整信息 (title, tags, conclusion, body)。"""
    path = settings.PROCESSED_DIR / f"{stem}.md"
    if not path.exists():
        return {"stem": stem, "title": stem, "tags": [], "conclusion": "", "body": ""}
    text = path.read_text(encoding="utf-8")
    post = frontmatter.loads(text)
    body = post.content
    m = re.search(r"##\s*核心结论\s*\n(.*?)(?=\n##\s|\Z)", body, re.DOTALL)
    conclusion = re.sub(r"^\s*>\s?", "", m.group(1).strip(),
                        flags=re.MULTILINE).strip() if m else ""
    # 去掉相关笔记段，避免喂给 LLM 重复信息
    body_clean = re.sub(r"##\s*相关笔记\s*\n.*?(?=\n##\s|\Z)", "", body, flags=re.DOTALL)
    return {
        "stem": stem,
        "title": str(post.metadata.get("title") or stem),
        "tags": list(post.metadata.get("tags") or []),
        "conclusion": conclusion,
        "body": body_clean.strip(),
    }


# ---------- 编译器: llmwiki 优先 ----------
def _compile_via_llmwiki(notes: list[dict], topic: str) -> str:
    """使用 llmwiki 包编译 (基座)。把簇内笔记复制到临时工作区再调用。"""
    if not _HAS_LLMWIKI:
        raise RuntimeError("llmwiki 未安装")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for n in notes:
            (tmp_path / f"{n['stem']}.md").write_text(
                f"# {n['title']}\n\n{n['body']}", encoding="utf-8"
            )
        # llmwiki 的具体 API 因版本而异，这里做一个常见调用约定；
        # 失败则由上层捕获并回退到自研编译。
        if hasattr(_llmwiki, "compile_directory"):
            result = _llmwiki.compile_directory(str(tmp_path), topic=topic)
        elif hasattr(_llmwiki, "compile"):
            result = _llmwiki.compile(str(tmp_path), topic=topic)
        else:
            raise RuntimeError("llmwiki API 不兼容 (无 compile/compile_directory)")
        if isinstance(result, str):
            return result
        return getattr(result, "markdown", str(result))


# ---------- 编译器: 自研 LLM 综述 (兜底) ----------
_COMPILE_SYSTEM = (
    "你是一名知识体系编译器 (受 Karpathy Wiki Compiler 启发)。"
    "把用户提供的多篇原子笔记编译成一篇系统性、结构完整的知识综述。"
    "要求:\n"
    "1) 开头 2-3 句概述该主题知识体系;\n"
    "2) 按子主题分章节 (## 二级标题) 综合多篇笔记，不要简单拼接;\n"
    "3) 在关键概念处使用 [[]] 双链标记 (目标必须是已有笔记的 stem);\n"
    "4) 末尾用 '## 来源笔记' 列出参与编译的所有笔记 [[]] 链接;\n"
    "5) 全程中文，逻辑严密，消除笔记间的断裂与重复。"
)


def _build_compile_prompt(topic: str, notes: list[dict]) -> str:
    parts = [f"主题: {topic}", f"参与笔记数: {len(notes)}", "", "===== 原子笔记 ====="]
    for n in notes:
        parts.append(
            f"\n--- 笔记: [[{n['stem']}]] | 标题: {n['title']} | 标签: {n['tags']} ---\n"
            f"核心结论: {n['conclusion']}\n\n正文:\n{n['body']}\n"
        )
    parts.append("===== 原子笔记结束 =====")
    parts.append(f"\n请把以上笔记编译为一篇关于「{topic}」的系统综述。")
    return "\n".join(parts)


def _compile_via_llm(notes: list[dict], topic: str) -> str:
    """自研兜底: 直接用 MODEL_WIKI (Kimi 128k) 编译综述。"""
    prompt = _build_compile_prompt(topic, notes)
    return llm.chat(
        prompt,
        system=_COMPILE_SYSTEM,
        model=settings.MODEL_WIKI,
        temperature=0.4,
    )


# ---------- 后处理: 确定性双链覆盖 ----------
def _known_stems() -> set[str]:
    """返回所有已知笔记/综述的 stem 集合 (processed/ + wiki/)。"""
    stems = {p.stem for p in settings.PROCESSED_DIR.glob("*.md")}
    stems.update(p.stem for p in settings.WIKI_DIR.glob("*.md"))
    return stems


def _post_process_wiki(content: str, cluster_stems: list[str]) -> str:
    """胶水层核心: 用确定性关联覆盖 LLM 悬空双链。

    策略:
        1) 移除指向不存在笔记的悬空 [[]] (保留概念性双链则保留，仅清理非已知 stem)
           —— 为安全起见，只移除明显悬空且形似文件名的双链
        2) 文末追加 ## 相关笔记 (确定性关联) 段，列出簇内所有笔记 [[stem]]
        3) 若已有 ## 相关笔记 段，替换之
    """
    known = _known_stems()

    # 1) 清理悬空双链 (仅当目标看起来像笔记 stem 且不在 known 中)
    def _replace_link(m: re.Match) -> str:
        target = m.group(1).split("|", 1)[0].strip()
        # 含空格或中文且不在已知笔记 -> 可能是概念双链，保留
        # 仅清理形如 "xxx.md" 或纯英文 stem 且未知的
        if target.endswith(".md") and target[:-3] not in known:
            return target[:-3]
        return m.group(0)

    cleaned = _LINK_RE.sub(_replace_link, content)

    # 2) 追加/替换 ## 相关笔记 段
    related_lines = "\n".join(f"- [[{s}]]" for s in cluster_stems)
    section_re = re.compile(r"##\s*相关笔记\s*\n.*?(?=\n##\s|\Z)", re.DOTALL)
    section = f"## 相关笔记\n{related_lines}\n"
    if section_re.search(cleaned):
        cleaned = section_re.sub(section.rstrip("\n") + "\n", cleaned)
    else:
        if not cleaned.endswith("\n"):
            cleaned += "\n"
        cleaned += "\n" + section
    return cleaned


# ---------- 保存 ----------
def _safe_wiki_name(topic: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\n\r\t]', " ", topic).strip()
    name = re.sub(r"\s+", " ", name) or "未命名综述"
    return name[:80]


def _save_wiki(topic: str, content: str, source_stems: list[str]) -> Path:
    settings.ensure_dirs()
    fname = _safe_wiki_name(topic)
    out_path = settings.WIKI_DIR / f"{fname}.md"
    i = 2
    while out_path.exists():
        out_path = settings.WIKI_DIR / f"{fname} ({i}).md"
        i += 1

    today = _dt.date.today().isoformat()
    post = frontmatter.Post(
        content=content,
        title=f"{fname} (Wiki 综述)",
        type="wiki",
        topic=topic,
        compiled=today,
        updated=today,
        source_notes=source_stems,
        tags=[topic],
    )
    out_path.write_text(frontmatter.dumps(post, sort_keys=False), encoding="utf-8")
    logger.info("Wiki 综述落盘: %s (来源 %d 篇)", out_path.name, len(source_stems))
    return out_path


# ---------- 对外主入口 ----------
def compile_wiki(
    topic: Optional[str] = None,
    *,
    stems: Optional[list[str]] = None,
    force_llm: bool = False,
) -> Optional[Path]:
    """编译一个簇为 Wiki 综述页。

    Args:
        topic: 主题名 (用于命名/命名簇)；与 stems 至少给一个
        stems: 显式指定簇内笔记 stem 列表；None 则用 topic 从 tags.json 取
        force_llm: True 则跳过 llmwiki 直接用自研编译
    Returns:
        生成的 wiki 文件路径；簇不达标返回 None
    """
    # 确定 stems
    if stems is None:
        if topic is None:
            raise ValueError("topic 与 stems 至少提供一个")
        tags_map = load_tags()
        files = tags_map.get(topic, [])
        stems = [Path(f).stem for f in files]
    if len(stems) < settings.WIKI_CLUSTER_MIN_NOTES:
        logger.info("簇节点数 %d < %d，跳过编译", len(stems), settings.WIKI_CLUSTER_MIN_NOTES)
        return None
    if topic is None:
        topic = _name_cluster(stems)

    notes = [_read_note_full(s) for s in stems]
    notes = [n for n in notes if n["body"]]
    if len(notes) < settings.WIKI_CLUSTER_MIN_NOTES:
        logger.info("有效笔记不足，跳过")
        return None

    logger.info("开始编译 Wiki: %s (stem=%d, llmwiki=%s)",
                topic, len(notes), _HAS_LLMWIKI and not force_llm)

    # 编译: llmwiki 优先 -> 自研兜底
    content: Optional[str] = None
    if _HAS_LLMWIKI and not force_llm:
        try:
            content = _compile_via_llmwiki(notes, topic)
        except Exception as e:  # noqa: BLE001
            logger.warning("llmwiki 编译失败，回退自研: %s", e)
    if content is None or not content.strip():
        content = _compile_via_llm(notes, topic)

    # 后处理: 确定性双链覆盖
    content = _post_process_wiki(content, stems)

    out_path = _save_wiki(topic, content, stems)
    # 触发索引更新 (rebuild_index 现在会同时扫描 wiki/ 与 processed/)
    rebuild_index()
    return out_path


def compile_all_wiki(*, force_llm: bool = False) -> list[Path]:
    """扫描所有达标关联簇，逐个编译。"""
    clusters = find_clusters()
    if not clusters:
        logger.info("未发现 >= %d 节点的关联簇，无需编译",
                    settings.WIKI_CLUSTER_MIN_NOTES)
        return []
    results: list[Path] = []
    for stems in clusters:
        try:
            p = compile_wiki(stems=stems, force_llm=force_llm)
            if p:
                results.append(p)
        except Exception as e:  # noqa: BLE001
            logger.error("编译簇失败 %s: %s", stems, e)
    return results


def rebuild_wiki(*, force_llm: bool = False) -> list[Path]:
    """清空 wiki/ 后全量重新编译。"""
    settings.ensure_dirs()
    if settings.WIKI_DIR.exists():
        for f in settings.WIKI_DIR.glob("*.md"):
            f.unlink()
    return compile_all_wiki(force_llm=force_llm)


def lint_wiki() -> dict:
    """Wiki 健康自检 (对应架构 lint_wiki)。

    检查项:
        - wiki/ 文件数
        - 悬空双链数 (指向不存在笔记的 [[]])
        - 每篇 wiki 是否有 ## 相关笔记 段
    """
    known = _known_stems()
    wiki_files = list(settings.WIKI_DIR.glob("*.md"))
    dangling = 0
    missing_related = 0
    for p in wiki_files:
        text = p.read_text(encoding="utf-8")
        for m in _LINK_RE.finditer(text):
            target = m.group(1).split("|", 1)[0].strip()
            if target.endswith(".md"):
                target = target[:-3]
            if target not in known and not target.endswith(("综述",)):
                # 概念双链可能不在 known 中，仅统计疑似悬空
                dangling += 1
        if not re.search(r"##\s*相关笔记", text):
            missing_related += 1
    return {
        "wiki_count": len(wiki_files),
        "suspected_dangling_links": dangling,
        "missing_related_section": missing_related,
    }

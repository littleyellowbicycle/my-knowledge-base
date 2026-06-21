# 🧠 四层认知引擎

个人知识库管理系统，将碎片信息自动加工为结构化笔记，并通过 LLM 问答和 Wiki 综述提供知识服务。

## 架构

```
原料层 (raw/) → 加工层 (processed/) → 编译层 (wiki/) → 索引层 (index/)
   ↓                    ↓                    ↓              ↓
 抓取归档           LLM 结构化           Wiki 综述        快速检索
 多平台路由         双链关联             确定性覆盖        QA 问答
```

## 快速开始

```bash
pip install -r requirements.txt
# 配置 .env: DEEPSEEK_API_KEY=xxx (或其他国产模型)
python kb.py ingest -t "你的第一篇笔记"
python kb.py process --all
python kb.py index
python kb.py qa "你的问题"
```

## 功能

| 命令 | 作用 |
|------|------|
| `kb ingest` | 录入原料 (URL/文本/管道) |
| `kb process` | 加工原料为结构化笔记 |
| `kb index` | 重建索引层 |
| `kb qa` | 基于知识库问答 |
| `kb wiki` | 编译 Wiki 综述 |
| `kb serve` | 启动 API 服务 (供 Obsidian Copilot 对接) |

## Obsidian 对接

将 `my_kb/` 作为 Obsidian 仓库打开，安装 Shell Commands / Obsidian Git / Templater / Copilot 插件，配置快捷键后即可在 Obsidian 内完成知识收集 → 加工 → 问答全流程。

详细配置见 [`docs/ob-plugin.md`](docs/ob-plugin.md)。

## 测试

```bash
pytest tests/ -v
```

## License

MIT

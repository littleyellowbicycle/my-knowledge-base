# 环境变量配置

## 快速配置

项目根目录创建 `.env` 文件：

```bash
cp .env.example .env
```

## 模型供应商

通过 LiteLLM 支持 100+ 模型供应商，只需设置对应 API Key 环境变量：

```ini
# 格式: {供应商大写}_API_KEY=sk-xxx
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...
MINIMAX_API_KEY=sk-...
ZHIPU_API_KEY=...
MOONSHOT_API_KEY=...
```

## 各层模型覆盖

默认使用 `minimax/MiniMax-M3`（需同时设置 `MINIMAX_API_BASE=https://api.minimaxi.com/v1`），可通过环境变量覆盖：

```ini
# 加工层（原料→结构化笔记）
MODEL_PROCESS=deepseek/deepseek-chat

# 编译层（Wiki 综述生成）
MODEL_WIKI=openai/gpt-4o

# 问答层（知识库问答）
MODEL_QA=zhipu/glm-4-flash

# 兜底模型（断网或 API 失败时）
MODEL_FALLBACK=ollama/qwen2.5:7b
```

## 其他配置

```ini
# 知识库根目录（默认 my_kb）
KB_ROOT=D:/path/to/your/vault

# MiniMax 自定义端点
MINIMAX_API_BASE=https://api.minimaxi.com/v1

# LiteLLM 调试日志
LITELLM_LOG=DEBUG
```

完整模型名列表见 [LiteLLM Providers 文档](https://docs.litellm.ai/docs/providers)。

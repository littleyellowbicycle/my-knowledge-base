# 模型配置

## 环境变量

在项目根目录创建 `.env` 文件，填入至少一个 API Key：

```bash
cp .env.example .env
```

## 各层默认模型

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MODEL_PROCESS` | `minimax/MiniMax-M3` | 加工层：原料→结构化笔记 |
| `MODEL_WIKI` | `minimax/MiniMax-M3` | 编译层：Wiki 综述生成 |
| `MODEL_QA` | `minimax/MiniMax-M3` | 问答层：知识库问答 |
| `MODEL_FALLBACK` | `minimax/MiniMax-M3` | 兜底模型 |

## 支持的模型供应商

| 提供商 | 模型示例 | 环境变量 | 用途 |
|--------|----------|----------|------|
| MiniMax | `minimax/MiniMax-M3` | `MINIMAX_API_KEY` | 主力模型 |
| DeepSeek | `deepseek/deepseek-chat` | `DEEPSEEK_API_KEY` | 问答流 |
| 智谱 GLM | `zhipu/glm-4-flash` | `ZHIPU_API_KEY` | 加工层 |
| 月之暗面 Kimi | `moonshot/moonshot-v1-128k` | `MOONSHOT_API_KEY` | 编译层 |
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` | 通用 |
| Ollama | `ollama/qwen2.5:7b` | 无 | 断网兜底 |

> MiniMax 特殊配置：需设置 `MINIMAX_API_BASE=https://api.minimaxi.com/v1`

覆盖默认模型只需在 `.env` 中设置对应变量，例如：

```ini
MODEL_PROCESS=deepseek/deepseek-chat
MODEL_QA=openai/gpt-4o
```

# 🚀 V2.1 Obsidian 对接指南

本文档说明如何将 Obsidian 配置为四层认知引擎的交互前端。系统遵循"文件优先、零数据库依赖、LLM 无关、确定性优先"的核心原则，Obsidian 承担**"交互前端 + 渲染器 + 自动同步器"**的角色。

---

## 一、前置条件

1. 已安装 [Obsidian](https://obsidian.md/) (1.4+)
2. 项目已克隆到本地，依赖已安装 (`pip install -r requirements.txt`)
3. `.env` 已配置至少一个 LLM API Key (如 `DEEPSEEK_API_KEY`)

---

## 二、Obsidian 端配置

### 1. 打开仓库

Obsidian → 打开文件夹作为仓库 → 选择 `my_kb/` 文件夹。

> 项目已在 `my_kb/.obsidian/app.json` 中预配置:
> - 新文件默认创建在 `inbox/` 目录
> - 忽略 `raw/` 和 `index/` 目录 (不索引冗余文件)

### 2. 安装社区插件

进入 `设置 → 社区插件 → 关闭安全模式 → 浏览`，搜索并安装以下插件:

| 插件 | 作用 | 必须 |
|------|------|------|
| **Shell Commands** | 在 Obsidian 内执行后端脚本 | ✅ |
| **Obsidian Git** | 自动同步到 GitHub | ✅ |
| **Templater** | 一键创建闪念/链接笔记模板 | 推荐 |
| **Copilot for Obsidian** | 侧边栏 AI 对话 (对接本地 API) | 推荐 |

> `my_kb/.obsidian/community-plugins.json` 已声明所需插件列表，安装后 Obsidian 会自动识别。

---

## 三、Shell Commands 插件配置

Shell Commands 是核心触发器，让你在 Obsidian 内通过快捷键执行后端脚本，告别命令行。

### 1. 新建命令

进入 `设置 → Shell Commands → 新建命令`，添加以下命令:

#### 命令 A: 抓取剪贴板链接
```
D:\project\my-konwledge-base\kb.bat ingest -u "{{clipboard}}"
```
> macOS/Linux 替换为: `~/path/to/my-konwledge-base/kb.sh ingest -u "{{clipboard}}"`

#### 命令 B: 对选中文字提问
```
D:\project\my-konwledge-base\kb.bat qa "{{selection}}"
```

#### 命令 C: 加工所有待处理原料
```
D:\project\my-konwledge-base\kb.bat process --all
```

#### 命令 D: 重建索引
```
D:\project\my-konwledge-base\kb.bat index
```

#### 命令 E: Wiki 编译
```
D:\project\my-konwledge-base\kb.bat wiki --all
```

### 2. 分配快捷键

进入 `设置 → 快捷键`，为上述命令分配快捷键:
- 抓取链接: `Ctrl+Shift+I` (Ingest)
- 知识问答: `Ctrl+Shift+Q` (Question)
- 加工笔记: `Ctrl+Shift+P` (Process)
- 重建索引: `Ctrl+Shift+R` (Rebuild)
- Wiki 编译: `Ctrl+Shift+W` (Wiki)

### 3. 工作目录设置

在 Shell Commands 插件设置中，确保**工作目录**设为项目根目录:
```
D:\project\my-konwledge-base
```

> `kb.bat` / `kb.sh` 包装脚本已自动切换到脚本所在目录，通常无需额外配置。

---

## 四、Obsidian Git 插件配置

实现知识库自动同步到 GitHub，多端访问。

### 配置项

| 配置项 | 值 |
|--------|-----|
| Auto backup & push | `Every 10 minutes` |
| Commit message | `chore(auto-sync): update knowledge base at {{date}}` |
| Pull on startup | ✅ 开启 |
| Push on backup | ✅ 开启 |

> 确保 `my_kb/` 目录已初始化 git 仓库并关联远程。若知识库单独同步 (非整个项目)，在 `my_kb/` 下运行:
> ```bash
> cd my_kb
> git init && git remote add origin <your-kb-repo-url>
> ```

---

## 五、Templater 插件配置

配合 `inbox/` 目录，一键创建闪念笔记或链接笔记。

### 配置项

1. `设置 → Templater → Template folder location`: `inbox`
2. `设置 → Templater → New file location`: `inbox`
3. 项目已预置两个模板:
   - `inbox/模板-闪念笔记.md` — 快速记录想法
   - `inbox/模板-链接笔记.md` — 待抓取的链接

### 工作流

1. `Ctrl+N` 在 `inbox/` 新建笔记 (基于模板)
2. 写下想法或粘贴链接
3. `Ctrl+S` 保存
4. 按 `Ctrl+Shift+P` (加工笔记) → 后端自动抓取并加工为结构化笔记
5. 几秒后 Obsidian 文件树出现加工好的 `processed/` 笔记，双链自动生成

---

## 六、Copilot for Obsidian 对接

通过本地 FastAPI 服务，让 Obsidian 侧边栏 AI 对话 100% 基于你的个人知识库。

### 1. 启动 API 服务

在项目根目录运行:
```bash
python kb.py serve
```
> 默认监听 `http://127.0.0.1:8000`
> 可指定: `python kb.py serve --host 0.0.0.0 --port 9000`

### 2. API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/chat/completions` | POST | OpenAI 兼容 (供 Copilot/Smart Connections 直接使用) |
| `/qa` | POST | 原生问答 (`{"question": "..."}`) |
| `/ingest` | POST | 录入原料 (`{"url": "..."} 或 {"text": "..."}`) |
| `/process` | POST | 加工原料 (`{"all_pending": true}`) |
| `/index` | POST | 重建索引 |
| `/stats` | GET | 各层统计 |

### 3. Copilot 插件配置

进入 `设置 → Copilot → Model Provider`:
- **API Base URL**: `http://127.0.0.1:8000`
- **API Key**: 任意填 (本地服务不校验)
- **Model**: `kb-qa` (任意值，服务忽略模型名)

现在侧边栏对话将 100% 基于你的知识库回答，附带 `[[]]` 来源链接。

---

## 七、终极工作流体验

配置完毕后，日常操作完全融入 Obsidian，零摩擦:

1. **灵感闪现**: `Ctrl+N` 在 `inbox/` 新建笔记 → 写下想法 → `Ctrl+S` → `Ctrl+Shift+P` → 加工笔记自动出现在 `processed/`，双链自动生成。

2. **网页收集**: 浏览器复制链接 → Obsidian 内 `Ctrl+Shift+I` → 自动抓取并归档 → `Ctrl+Shift+P` → 自动加工为带核心结论的阅读笔记。

3. **知识问答**: 在笔记里写下问题 → 选中文字 → `Ctrl+Shift+Q` → 终端输出基于本地笔记的精准回答及 `[[]]` 来源链接。或在侧边栏 Copilot 直接对话。

4. **无缝同步**: 你只管写和读，`Obsidian Git` 每隔 10 分钟默默把所有新增双链和综述页推送到 GitHub，手机端随时可查。

5. **知识编译**: `Ctrl+Shift+R` 重建索引 → `Ctrl+Shift+W` 编译 Wiki → `wiki/` 目录自动生成系统性综述页，Obsidian 图谱视图即时呈现知识体系。

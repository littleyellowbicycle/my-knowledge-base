"""四层认知引擎 - 源码包入口。

模块清单 (按架构层级):
    config         - 路径与全局配置加载
    llm_adapter    - LiteLLM 统一封装 (chat / chat_json)
    gateway        - 输入网关 (模块 A) -> 归一化 -> 原料层 (模块 B1)
    raw_store      - 原料层只读归档 (模块 B1)
    processor      - 加工引擎 (模块 B2) LLM JSON Mode 结构化产出
    relations      - 确定性关联打分引擎 (jieba + 标签)
    indexer        - 索引层构建 (模块 B3) 四个 JSON 索引
    wiki_compiler  - Wiki 编译层 (模块 B4) llmwiki + 胶水层
    qa_engine      - 输出引擎 - 问答流 (模块 C1)
    cli            - 命令行入口
"""

__version__ = "0.1.0"

# Teacher Assistant RAG Agent

教师助理 RAG 智能体：根据学生(Stu)消息，检索历史对话片段，生成教师(Tea)回复。

## 工作原理

基于 **RAG (Retrieval-Augmented Generation)** 架构：

1. **向量索引**：将历史对话文本分块(Chunk)，使用 Embedding 模型转换为向量，存入 Chroma 向量数据库
2. **相似性检索**：根据学生当前消息，检索向量库中最相似的历史对话片段
3. **LLM 生成**：将检索到的上下文连同提示词，发送给 LLM 生成教师回复

## 核心模块

| 文件 | 职责 |
|------|------|
| `types.py` | 数据结构：DialogueTurn、DialogueChunk |
| `parser.py` | 对话文件解析、Chunk 构建、源文件收集 |
| `vectorstore.py` | 向量存储管理、索引构建、相似性检索 |
| `agent.py` | 主 Agent 类、LLM 调用、CLI 入口 |

## 工作流程

### 1. 构建向量索引 (build-index)

```
archive_dir/*.txt → 解析对话 → 分块(Window) → Embedding → Chroma 向量库
```

- 读取 `archive_dir` 下的 `.txt` 对话文件
- 按 `Tea:` / `Stu:` 模式解析对话轮次
- 使用滑动窗口(WINDOW_SIZE, WINDOW_OVERLAP)生成 Chunks
- 每个 Chunk 包含：chat_id、line_start、line_end、roles_summary、source_file
- 调用 Embedding 模型向量化，存入 Chroma
- 生成 `index_manifest.json` 记录已索引的 Chunk ID

### 2. 生成回复 (reply)

```
学生消息 → 向量检索 → 构建 Prompt → LLM → 教师回复
```

- **同会话检索**：优先在相同 chat_id 下检索 (MMR)
- **全局检索**：若同会话召回不足，最小相似片段数 < MIN_SAME_CHAT_HITS，则触发全库检索
- **弱检索判定**：若最近邻距离 > DISTANCE_THRESHOLD，标记为弱检索
- **Prompt 拼接**：
  - system_role.txt：角色设定
  - task_template.txt：任务模板，填充学生消息、检索上下文
  - constraints.txt：回复约束
  - 弱检索时附加温和确认 + 澄清问题提示

## 输入输出

### CLI 命令

#### build-index

```bash
python -m app.services.agent.agent build-index [--rebuild] [--target-file FILE]
```

| 参数 | 说明 |
|------|------|
| `--rebuild` | 清空原有 collection，全量重建 |
| `--target-file` | 仅处理指定文件或目录 |

**输出示例：**
```json
{
  "ok": true,
  "collection_name": "teacher_assistant",
  "persist_dir": "./data/vectorstore",
  "source_count": 50,
  "turn_count": 1000,
  "chunk_count": 500,
  "added_chunk_count": 0,
  "skipped_chunk_count": 500,
  "rebuild": false,
  "target_file": null
}
```

#### reply

```bash
python -m app.services.agent.agent reply --stu-message "消息内容" [--chat-id ID] [--json-output]
```

| 参数 | 说明 |
|------|------|
| `--stu-message` | 学生发送的消息（必填） |
| `--chat-id` | 会话 ID，用于同会话检索（可选） |
| `--json-output` | 输出完整 JSON 结果 |

**输出示例：**
```json
{
  "ok": true,
  "chat_id": "abc123",
  "stu_message": "这道题怎么做？",
  "reply": "同学你好，请问你能具体描述一下题目中遇到的困难吗？",
  "retrieval": {
    "same_chat_hits": 2,
    "used_global_fallback": false,
    "retrieved_count": 3,
    "weak_retrieval": false,
    "distance_threshold": 1.25
  },
  "used_context": [
    {
      "chunk_id": "abc123:10-15",
      "chat_id": "abc123",
      "line_start": 10,
      "line_end": 15,
      "source_file": "archive/abc123.txt",
      "content": "Tea: 这道题...\nStu: 谢谢老师..."
    }
  ]
}
```

### Python API

```python
from app.services.agent import generate_teacher_reply, build_teacher_assistant_index

# 构建索引
build_teacher_assistant_index(rebuild=False)

# 生成回复
result = generate_teacher_reply(
    stu_message="这道题怎么做？",
    chat_id="abc123"
)
print(result["reply"])
```

## 配置项

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `TEACHER_AGENT_ARCHIVE_DIR` | - | 历史对话存档目录 |
| `TEACHER_AGENT_VECTOR_DIR` | - | 向量库持久化目录 |
| `TEACHER_AGENT_PROMPT_DIR` | - | 提示词文件目录 |
| `TEACHER_AGENT_COLLECTION_NAME` | teacher_assistant | Chroma collection 名 |
| `TEACHER_AGENT_EMBEDDING_PROVIDER` | openai | Embedding 提供商(仅支持 openai) |
| `TEACHER_AGENT_EMBEDDING_MODEL` | text-embedding-3-small | Embedding 模型 |
| `TEACHER_AGENT_EMBEDDING_API_KEY` | - | Embedding API Key |
| `TEACHER_AGENT_EMBEDDING_TOKEN` | - | Embedding API Key 的别名 |
| `TEACHER_AGENT_EMBEDDING_BASE_URL` | - | Embedding 兼容 OpenAI API 端点 |
| `TEACHER_AGENT_EMBEDDING_HOST` | - | Embedding Base URL 的别名 |
| `TEACHER_AGENT_LLM_MODEL` | gpt-4o-mini | LLM 模型 |
| `TEACHER_AGENT_LLM_API_KEY` | - | LLM API Key |
| `TEACHER_AGENT_LLM_TOKEN` | - | LLM API Key 的别名 |
| `TEACHER_AGENT_LLM_BASE_URL` | - | LLM 兼容 OpenAI API 端点 |
| `TEACHER_AGENT_LLM_HOST` | - | LLM Base URL 的别名 |
| `TEACHER_AGENT_LLM_TEMPERATURE` | 0.4 | LLM 温度参数 |
| `TEACHER_AGENT_WINDOW_SIZE` | 6 | 滑动窗口大小 |
| `TEACHER_AGENT_WINDOW_OVERLAP` | 2 | 滑动窗口重叠数 |
| `TEACHER_AGENT_SAME_CHAT_TOP_K` | 4 | 同会话检索 top_k |
| `TEACHER_AGENT_GLOBAL_TOP_K` | 3 | 全局检索 top_k |
| `TEACHER_AGENT_MIN_SAME_CHAT_HITS` | 2 | 触发全局检索的最小同会话召回数 |
| `TEACHER_AGENT_MAX_CONTEXT_CHUNKS` | 6 | 最大上下文 Chunk 数 |
| `TEACHER_AGENT_DISTANCE_THRESHOLD` | 1.25 | 弱检索距离阈值 |

## 提示词文件

`prompt_dir` 目录下需包含：

- `system_role.txt` - 系统角色设定
- `task_template.txt` - 任务模板，支持变量：`{stu_message}`、`{chat_id}`、`{retrieved_context}`
- `constraints.txt` - 回复约束

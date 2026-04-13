# 企业微信消息接收 FastAPI 后端

参考 [企业微信官方文档 - 接收消息与事件](https://developer.work.weixin.qq.com/document/path/90238)。

## 功能

- **消息接收** — 接收企业微信应用推送的消息与事件
  - GET `/` — URL 验证回调
  - POST `/` — 接收消息/事件
- **会话内容存档** — 拉取聊天记录并保存到本地
  - POST `/chat/archive` — 拉取并保存会话内容
- **完整的 AES 加解密与签名校验**
- **被动回复消息**
- 基于 `pydantic` 的消息模型

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env` 配置文件后启动：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 接口说明

### 1. 消息接收回调

| 接口 | 方法 | 说明 |
|---|---|---|
| `/` | GET | 企业微信 URL 验证回调 |
| `/` | POST | 接收消息与事件 |

### 2. 会话内容存档

| 接口 | 方法 | 说明 |
|---|---|---|
| `/chat/archive` | POST | 拉取聊天记录并保存为 JSON |

#### 调用示例

```bash
# 拉取最近24小时的会话记录
curl -X POST "http://localhost:8000/chat/archive"

# 指定时间范围 (时间戳单位：秒)
curl -X POST "http://localhost:8000/chat/archive?starttime=1704067200&endtime=1704153600"
```

#### 返回结果

```json
{
  "errcode": 0,
  "errmsg": "ok",
  "saved_count": 123,
  "save_path": "archive_data/archive_20240101_120000_20240102_120000.json",
  "messages": [
    {"seq": 1, "msgid": "...", "roomid": "...", ...},
    ...
  ]
}
```

## 配置说明 (.env)

| 参数 | 说明 | 必需 |
|---|---|---|
| `WECOM_CORP_ID` | 企业ID | ✅ |
| `WECOM_TOKEN` | 回调 Token | ✅ |
| `WECOM_ENCODING_AES_KEY` | 43位 EncodingAESKey | ✅ |
| `WECOM_AGENT_ID` | 应用 ID | |
| `WECOM_CHAT_ARCHIVE_SECRET` | 聊天内容存档 Secret | 会话存档必需 |
| `WECOM_CHAT_ARCHIVE_SAVE_DIR` | 存档保存目录，默认 `archive_data/` | |

### 获取会话存档配置

1. 登录企业微信管理后台
2. 进入 **管理工具** → **聊天内容存档**
3. 开启并获取 `Secret`

## 项目结构

```
.
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 路由入口
│   ├── config.py            # 配置管理
│   ├── crypto.py            # AES 加解密 + 签名校验
│   ├── models.py           # Pydantic 消息模型
│   ├── service.py          # 消息处理业务逻辑
│   └── chat_archive.py     # 会话内容存档 API
├── archive_data/           # 存档保存目录
├── requirements.txt
├── .env.example
├── run.py
└── README.md
```

## 依赖

- fastapi
- uvicorn[standard]
- pycryptodome
- lxml
- python-dotenv
- xmltodict
- httpx
# 企业微信消息接收 FastAPI 后端

参考 [企业微信官方文档 - 接收消息与事件](https://developer.work.weixin.qq.com/document/path/90238)。

## 功能

- **消息接收** — 接收企业微信应用推送的消息与事件
  - GET `/` — URL 验证回调
  - POST `/` — 接收消息/事件
- **会话内容存档** — 拉取聊天记录并保存到本地
  - POST `/chat/archive` — 拉取并保存会话内容
  - GET `/index` — 前端首页（含“拉取”按钮）
  - GET `/index/modules` — 模块管理页
  - GET `/chat/archive/room-binding/admin` — roomid 绑定管理界面（Vue）
  - `/chat/archive/room-binding*` — roomid 绑定增删改查 API
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

群聊接口文档见：`docs/chat-group-api.md`

### 1. 消息接收回调

| 接口 | 方法 | 说明 |
|---|---|---|
| `/` | GET | 企业微信 URL 验证回调 |
| `/` | POST | 接收消息与事件 |

### 2. 会话内容存档

| 接口 | 方法 | 说明 |
|---|---|---|
| `/chat/archive` | POST | 拉取聊天记录并保存为 JSON |
| `/index` | GET | 前端首页，提供“拉取”按钮调用 `/chat/archive` |
| `/index/modules` | GET | 前端模块管理页 |
| `/chat/archive/room-binding/admin` | GET | 打开 roomid 绑定管理界面（Vue） |

### 3. roomid 绑定管理

| 接口 | 方法 | 说明 |
|---|---|---|
| `/chat/archive/group-modules` | GET | 按本地 JSON 文件列出模块并返回绑定关系 |
| `/chat/archive/group-module/{filename}` | GET | 按 JSON 文件名查看模块详情与消息内容 |
| `/chat/archive/room-binding` | POST | 新增 roomid 与群聊名绑定 |
| `/chat/archive/room-binding/{roomid}` | GET | 查询单个绑定 |
| `/chat/archive/room-bindings` | GET | 查询绑定列表，支持 keyword 过滤 |
| `/chat/archive/room-binding/{roomid}` | PUT | 更新绑定名称 |
| `/chat/archive/room-binding/{roomid}` | DELETE | 删除绑定 |

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
  "skip_duplicate_count": 456,
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
| `WECOM_CORP_SECRET` | 企业应用 Secret（所有接口统一使用） | ✅ |
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
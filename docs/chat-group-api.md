# 群聊接口文档

本文档面向前端，说明当前可用的群聊接口。

## 基础信息

- 接口前缀：`/chat`
- 数据格式：请求与响应均为 `application/json`
- 字符编码：UTF-8

---

## 1) 创建群聊

- 方法：`POST`
- 路径：`/chat/group`
- 说明：创建企业微信群聊，同时将群聊信息写入本地 SQLite 数据库。

### 请求体

```json
{
  "userlist": ["zhangsan", "lisi"],
  "name": "项目讨论组",
  "owner": "zhangsan"
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `userlist` | `string[]` | 是 | 群成员 userid 列表，至少 2 人，最多 2000 人 |
| `name` | `string` | 否 | 群聊名称，后端最多保留前 50 个字符 |
| `owner` | `string` | 否 | 群主 userid，不传由企业微信侧处理 |

### 成功响应示例

> 成功响应来自企业微信创建群聊接口。

```json
{
  "errcode": 0,
  "errmsg": "ok",
  "chatid": "3f2e8b6f4a7c49f4a5e7bf2db0fa1f2a"
}
```

### 失败响应示例

```json
{
  "detail": "创建群聊会话异常: 创建群聊失败: {'errcode': 40058, 'errmsg': 'invalid userlist'}"
}
```

### 前端注意事项

- 当前接口不接收 `chatid`，由后端自动生成 UUID（32 位小写十六进制）并提交给企业微信。
- 当企业微信创建成功但数据库写入失败时，接口会返回错误，请前端按失败处理并提示重试。

---

## 2) 获取全部群聊

- 方法：`GET`
- 路径：`/chat/groups`
- 说明：从本地数据库读取全部群聊记录，按 `created_at` 倒序返回。

### 请求参数

无。

### 成功响应示例

```json
[
  {
    "chatid": "3f2e8b6f4a7c49f4a5e7bf2db0fa1f2a",
    "name": "项目讨论组",
    "owner": "zhangsan",
    "userlist": ["zhangsan", "lisi"],
    "chat_type": 0,
    "created_at": "2026-04-14T08:32:11.125090"
  },
  {
    "chatid": "45a65f90e31a420d8f3b6bb2f3f3d4e9",
    "name": "测试群",
    "owner": null,
    "userlist": ["wangwu", "zhaoliu"],
    "chat_type": 1,
    "created_at": "2026-04-14T08:20:03.552901"
  }
]
```

### 失败响应示例

```json
{
  "detail": "读取群聊列表失败: (sqlite3.OperationalError) ..."
}
```

---

## 通用响应说明

- HTTP 200：请求成功。
- HTTP 422：请求体格式错误（例如字段类型不匹配）。
- HTTP 500：服务端业务或第三方接口异常。

---

## 调试示例（curl）

### 创建群聊

```bash
curl -X POST "http://localhost:8000/chat/group" \
  -H "Content-Type: application/json" \
  -d '{
    "userlist": ["zhangsan", "lisi"],
    "name": "项目讨论组",
    "owner": "zhangsan"
  }'
```

### 获取全部群聊

```bash
curl -X GET "http://localhost:8000/chat/groups"
```

---

## 3) 删除群聊（仅删除本地数据库记录）

- 方法：`DELETE`
- 路径：`/chat/group/{chatid}`
- 说明：仅删除本地数据库 `chat_groups` 表里的记录，不会调用企业微信 API 删除远端群聊。

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chatid` | `string` | 是 | 群聊 ID，仅支持 0-9、a-z、A-Z，最大 32 字符 |

### 成功响应示例

删除成功：

```json
{
  "chatid": "3f2e8b6f4a7c49f4a5e7bf2db0fa1f2a",
  "deleted": true
}
```

记录不存在：

```json
{
  "chatid": "3f2e8b6f4a7c49f4a5e7bf2db0fa1f2a",
  "deleted": false
}
```

### 调试示例（curl）

```bash
curl -X DELETE "http://localhost:8000/chat/group/3f2e8b6f4a7c49f4a5e7bf2db0fa1f2a"
```

---

## 4) 修改群聊

- 方法：`POST`
- 路径：`/chat/group/update`
- 说明：调用企业微信群聊修改接口，同时同步更新本地数据库中的群聊记录。

### 请求体

```json
{
  "chatid": "3f2e8b6f4a7c49f4a5e7bf2db0fa1f2a",
  "name": "新群名",
  "owner": "userid2",
  "add_user_list": ["userid1", "userid2", "userid3"],
  "del_user_list": ["userid3", "userid4"]
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chatid` | `string` | 是 | 群聊 ID |
| `name` | `string` | 否 | 新群名，最多 50 字符 |
| `owner` | `string` | 否 | 新群主 userid |
| `add_user_list` | `string[]` | 否 | 需要添加的成员列表 |
| `del_user_list` | `string[]` | 否 | 需要删除的成员列表 |

说明：`name`、`owner`、`add_user_list`、`del_user_list` 至少传一个。

### 成功响应示例

```json
{
  "errcode": 0,
  "errmsg": "ok"
}
```

### 失败响应示例

```json
{
  "detail": "修改群聊会话异常: 修改群聊失败: {'errcode': 40058, 'errmsg': 'invalid parameter'}"
}
```

### 调试示例（curl）

```bash
curl -X POST "http://localhost:8000/chat/group/update" \
  -H "Content-Type: application/json" \
  -d '{
    "chatid": "3f2e8b6f4a7c49f4a5e7bf2db0fa1f2a",
    "name": "新群名",
    "owner": "userid2",
    "add_user_list": ["userid1", "userid2", "userid3"],
    "del_user_list": ["userid3", "userid4"]
  }'
```

---

## 5) 获取并同步群聊信息

- 方法：`GET`
- 路径：`/chat/group/sync?chatid={chatid}`
- 说明：调用企业微信 `appchat/get` 获取群聊详情，并将 `chat_info` 同步到本地数据库。

### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chatid` | `string` | 是 | 群聊 ID |

### 成功响应示例

```json
{
  "errcode": 0,
  "errmsg": "ok",
  "chat_info": {
    "chatid": "3f2e8b6f4a7c49f4a5e7bf2db0fa1f2a",
    "name": "新群名",
    "owner": "userid2",
    "userlist": ["userid1", "userid2", "userid3"],
    "chat_type": 0
  }
}
```

### 失败响应示例

```json
{
  "detail": "获取并同步群聊会话异常: 获取群聊会话失败: {'errcode': 40058, 'errmsg': 'invalid parameter'}"
}
```

### 调试示例（curl）

```bash
curl -X GET "http://localhost:8000/chat/group/sync?chatid=3f2e8b6f4a7c49f4a5e7bf2db0fa1f2a"
```

---

## 6) 推送 Markdown 消息到指定群聊

- 方法：`POST`
- 路径：`/chat/group/send/markdown`
- 说明：调用企业微信 `appchat/send`，向指定群聊发送 `markdown` 类型消息。

### 请求体

```json
{
  "chatid": "3f2e8b6f4a7c49f4a5e7bf2db0fa1f2a",
  "content": "您的会议室已经预定，稍后会同步到`邮箱`  \\n>**事项详情**  \\n>事　项：<font color=\"info\">开会</font>"
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chatid` | `string` | 是 | 群聊 ID |
| `content` | `string` | 是 | markdown 内容，UTF-8 编码后最长 2048 字节 |

### 成功响应示例

```json
{
  "errcode": 0,
  "errmsg": "ok"
}
```

### 失败响应示例

```json
{
  "detail": "发送 markdown 消息异常: 发送 markdown 消息失败: {'errcode': 40058, 'errmsg': 'invalid parameter'}"
}
```

### 调试示例（curl）

```bash
curl -X POST "http://localhost:8000/chat/group/send/markdown" \
  -H "Content-Type: application/json" \
  -d '{
    "chatid": "3f2e8b6f4a7c49f4a5e7bf2db0fa1f2a",
    "content": "您的会议室已经预定，稍后会同步到`邮箱`  \\n>**事项详情**  \\n>事　项：<font color=\"info\">开会</font>"
  }'
```

---

## 7) 批量云同步群聊信息

- 方法：`POST`
- 路径：`/chat/groups/sync`
- 说明：读取本地已有群聊 `chatid` 列表，逐个调用云端获取接口拉取最新群信息，并覆盖写入本地数据库（以拉取数据为准）。

### 请求参数

无。

### 成功响应示例

```json
{
  "total": 2,
  "success": 1,
  "failed": 1,
  "items": [
    {
      "chatid": "3f2e8b6f4a7c49f4a5e7bf2db0fa1f2a",
      "synced": true
    },
    {
      "chatid": "45a65f90e31a420d8f3b6bb2f3f3d4e9",
      "synced": false,
      "error": "获取并同步群聊会话异常: 获取群聊会话失败: {'errcode': 40058, 'errmsg': 'invalid parameter'}"
    }
  ]
}
```

### 调试示例（curl）

```bash
curl -X POST "http://localhost:8000/chat/groups/sync"
```

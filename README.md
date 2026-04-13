# 企业微信消息接收 FastAPI 后端

参考 [企业微信官方文档 - 接收消息与事件](https://developer.work.weixin.qq.com/document/path/90238)。

## 功能

- GET 接口：URL 验证
- POST 接口：接收消息与事件（文本/图片/语音/视频/位置/链接/各种事件）
- 完整的 AES 加解密与签名校验
- 被动回复消息
- 基于 `pydantic` 的消息模型

## 快速开始

```
# 安装依赖
pip install -r requirements.txt

cp .env.example .env   编辑填入你的企业微信回调参数
# 启动
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 企业微信管理端配置

| 参数 | 说明 |
|---|---|
| URL | `https://你的域名/wecom/callback` |
| Token | 你自定义的 Token，用于签名校验 |
| EncodingAESKey | 43 位 EncodingAESKey |

## 项目结构

```
.
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI 路由入口
│   ├── config.py        # 配置管理（环境变量）
│   ├── crypto.py        # AES 加解密 + 签名校验
│   ├── models.py        # Pydantic 消息模型
│   └── service.py       # 消息处理业务逻辑
├── requirements.txt
├── .env.example
└── README.md
```

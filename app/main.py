"""
FastAPI 主应用 - 企业微信消息接收
"""

import logging
import urllib.parse

import xmltodict
from fastapi import FastAPI, Query, Request
from fastapi.responses import PlainTextResponse, Response

from app.config import settings
from app.crypto import WecomCrypto
from app.service import dispatch_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="WeCom Message Receiver")

crypto = WecomCrypto(
    token=settings.token,
    encoding_aes_key=settings.encoding_aes_key,
    corp_id=settings.corp_id,
)


@app.get("/callback")
async def verify_url(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    """企业微信 URL 验证回调"""
    if not crypto.verify_signature(timestamp, nonce, echostr, msg_signature):
        return PlainTextResponse("signature mismatch", status_code=403)
    verify_msg = crypto.decrypt_echostr(echostr)
    return PlainTextResponse(content=verify_msg)


@app.post("/callback")
async def receive_message(
    request: Request,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
):
    """接收企业微信推送的消息/事件"""
    body = await request.body()
    xml_data = xmltodict.parse(body.decode("utf-8"))["xml"]
    encrypt_msg = xml_data["Encrypt"]

    if not crypto.verify_msg_signature(msg_signature, timestamp, nonce, encrypt_msg):
        return Response(status_code=403, content="msg_signature mismatch")

    decrypted_xml, _, _, _ = crypto.decrypt_message(encrypt_msg)
    msg_dict = xmltodict.parse(decrypted_xml)["xml"]

    logger.info("Decrypted message: %s", msg_dict)

    msg_type = msg_dict.get("MsgType", "")
    reply_content = dispatch_message(msg_type, msg_dict)

    if not reply_content:
        return Response(status_code=200, content="")

    reply_xml = _build_text_reply(
        to_user=msg_dict.get("FromUserName", ""),
        from_user=msg_dict.get("ToUserName", ""),
        content=reply_content,
        timestamp=timestamp,
        nonce=nonce,
    )
    return Response(content=reply_xml, media_type="application/xml")


def _build_text_reply(
    to_user: str, from_user: str, content: str, timestamp: str, nonce: str
) -> str:
    reply_msg = (
        f"<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{int(timestamp)}</CreateTime>"
        f"<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        f"</xml>"
    )
    return crypto.encrypt_message(reply_msg, timestamp, nonce)

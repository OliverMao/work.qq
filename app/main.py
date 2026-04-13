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


@app.get("/")
async def verify_url(
    msg_signature: str = Query(default=None),
    timestamp: str = Query(default=None),
    nonce: str = Query(default=None),
    echostr: str = Query(default=None),
):
    """企业微信 URL 验证回调 - GET"""
    if not all([msg_signature, timestamp, nonce, echostr]):
        return PlainTextResponse("WeCom Message Receiver", status_code=200)

    echostr = urllib.parse.unquote(echostr)

    if not crypto.verify_signature(timestamp, nonce, echostr, msg_signature):
        return PlainTextResponse("signature mismatch", status_code=403)

    verify_msg = crypto.decrypt_echostr(echostr)

    return Response(
        content=verify_msg,
        media_type="text/plain",
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )


@app.post("/")
async def receive_message(
    request: Request,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
):
    """接收企业微信推送的消息/事件 - POST"""
    body = await request.body()
    logger.info("Raw XML body: %s", body.decode("utf-8"))

    xml_data = xmltodict.parse(body.decode("utf-8"))["xml"]
    encrypt_msg = xml_data["Encrypt"]

    if not crypto.verify_msg_signature(msg_signature, timestamp, nonce, encrypt_msg):
        return Response(status_code=403, content="msg_signature mismatch")

    decrypted_xml, _, _, _ = crypto.decrypt_message(encrypt_msg)

    logger.info("=" * 50)
    logger.info("Received Decrypted Message:")
    logger.info("=" * 50)
    logger.info("Decrypted XML:\n%s", decrypted_xml)

    msg_dict = xmltodict.parse(decrypted_xml)["xml"]
    msg_type = msg_dict.get("MsgType", "")
    msg_id = msg_dict.get("MsgId", "")
    from_user = msg_dict.get("FromUserName", "")
    to_user = msg_dict.get("ToUserName", "")

    logger.info("MsgType: %s", msg_type)
    logger.info("MsgId: %s", msg_id)
    logger.info("FromUserName: %s", from_user)
    logger.info("ToUserName: %s", to_user)

    if msg_type == "text":
        logger.info("Content: %s", msg_dict.get("Content", ""))
    elif msg_type == "image":
        logger.info("PicUrl: %s", msg_dict.get("PicUrl", ""))
        logger.info("MediaId: %s", msg_dict.get("MediaId", ""))
    elif msg_type == "voice":
        logger.info("MediaId: %s", msg_dict.get("MediaId", ""))
        logger.info("Format: %s", msg_dict.get("Format", ""))
    elif msg_type == "video":
        logger.info("MediaId: %s", msg_dict.get("MediaId", ""))
        logger.info("ThumbMediaId: %s", msg_dict.get("ThumbMediaId", ""))
    elif msg_type == "location":
        logger.info(
            "Location: %s, %s",
            msg_dict.get("Location_X", ""),
            msg_dict.get("Location_Y", ""),
        )
        logger.info("Label: %s", msg_dict.get("Label", ""))
    elif msg_type == "link":
        logger.info("Title: %s", msg_dict.get("Title", ""))
        logger.info("Url: %s", msg_dict.get("Url", ""))
    elif msg_type == "event":
        event = msg_dict.get("Event", "")
        logger.info("Event: %s", event)
        if event == "click":
            logger.info("EventKey: %s", msg_dict.get("EventKey", ""))

    logger.info("=" * 50)

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

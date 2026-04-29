"""
消息处理服务 - 在这里实现你的业务逻辑
"""

import logging
from typing import Optional

from app.models import (
    ClickEvent,
    EnterAgentEvent,
    ImageMessage,
    LinkMessage,
    LocationEvent,
    LocationMessage,
    TextMessage,
    UnsubscribeEvent,
    VideoMessage,
    VoiceMessage,
)

logger = logging.getLogger(__name__)


def handle_text_message(msg: TextMessage) -> Optional[str]:
    logger.info(
        "Received text from %s (agent=%s): %s",
        msg.FromUserName,
        msg.AgentID,
        msg.Content,
    )
    content = msg.Content.strip().lower()
    if content == "hello":
        return f"你好，{msg.FromUserName}！"
    if content == "help":
        return "支持的命令：\n- hello：打招呼\n- help：显示帮助"
    return f"收到你的消息：{msg.Content}"


def handle_image_message(msg: ImageMessage) -> Optional[str]:
    logger.info("Received image from %s, MediaId=%s", msg.FromUserName, msg.MediaId)
    return "收到图片，谢谢！"


def handle_voice_message(msg: VoiceMessage) -> Optional[str]:
    logger.info("Received voice from %s, Format=%s", msg.FromUserName, msg.Format)
    return "收到语音消息！"


def handle_video_message(msg: VideoMessage) -> Optional[str]:
    logger.info("Received video from %s, MediaId=%s", msg.FromUserName, msg.MediaId)
    return "收到视频消息！"


def handle_location_message(msg: LocationMessage) -> Optional[str]:
    logger.info(
        "Location from %s: %.4f, %.4f",
        msg.FromUserName,
        msg.Location_X,
        msg.Location_Y,
    )
    return f"收到位置：{msg.Label}"


def handle_link_message(msg: LinkMessage) -> Optional[str]:
    logger.info("Link from %s: %s", msg.FromUserName, msg.Url)
    return "收到链接消息！"


def handle_subscribe_event(msg_dict: dict) -> Optional[str]:
    logger.info("%s subscribed!", msg_dict.get("FromUserName"))
    return "欢迎使用！"


def handle_unsubscribe_event(msg_dict: dict) -> Optional[str]:
    logger.info("%s unsubscribed", msg_dict.get("FromUserName"))
    return None


def handle_enter_agent_event(msg_dict: dict) -> Optional[str]:
    logger.info("%s entered the app", msg_dict.get("FromUserName"))
    return None


def handle_location_event(msg_dict: dict) -> Optional[str]:
    logger.info(
        "Location event from %s: %.4f, %.4f",
        msg_dict.get("FromUserName"),
        msg_dict.get("Latitude", 0),
        msg_dict.get("Longitude", 0),
    )
    return None


def handle_click_event(msg_dict: dict) -> Optional[str]:
    event = ClickEvent(**msg_dict)
    logger.info("Menu click from %s, key=%s", event.FromUserName, event.EventKey)
    return f"点击了菜单：{event.EventKey}"


def handle_msgaudit_notify_event(msg_dict: dict) -> Optional[str]:
    logger.info("收到消息存档通知: %s", msg_dict)
    try:
        from app.services.redis_queue import redis_queue_service

        message = {
            "event": "msgaudit_notify",
            "timestamp": msg_dict.get("CreateTime", ""),
            "agent_id": msg_dict.get("AgentID", ""),
            "to_user": msg_dict.get("ToUserName", ""),
            "from_user": msg_dict.get("FromUserName", ""),
        }
        redis_queue_service.push_message(message)
        logger.info("消息已推送到Redis队列")
    except Exception as e:
        logger.error("处理msgaudit_notify失败: %s", e)
    return None


def dispatch_message(msg_type: str, msg_dict: dict) -> Optional[str]:
    if msg_type == "text":
        return handle_text_message(TextMessage(**msg_dict))
    if msg_type == "image":
        return handle_image_message(ImageMessage(**msg_dict))
    if msg_type == "voice":
        return handle_voice_message(VoiceMessage(**msg_dict))
    if msg_type == "video":
        return handle_video_message(VideoMessage(**msg_dict))
    if msg_type == "location":
        return handle_location_message(LocationMessage(**msg_dict))
    if msg_type == "link":
        return handle_link_message(LinkMessage(**msg_dict))
    if msg_type == "event":
        event_name = msg_dict.get("Event", "")
        handlers = {
            "subscribe": handle_subscribe_event,
            "unsubscribe": handle_unsubscribe_event,
            "enter_agent": handle_enter_agent_event,
            "location": handle_location_event,
            "click": handle_click_event,
            "msgaudit_notify": handle_msgaudit_notify_event,
        }
        handler = handlers.get(event_name)
        if handler:
            return handler(msg_dict)
        logger.info("Unhandled event: %s", event_name)
        return None
    logger.warning("Unknown msg_type: %s", msg_type)
    return None

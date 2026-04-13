"""
企业微信消息与事件模型
"""

from typing import Optional
from pydantic import BaseModel


class BaseWecomMessage(BaseModel):
    ToUserName: str
    FromUserName: str
    CreateTime: int
    MsgType: str
    AgentID: Optional[int] = None


class TextMessage(BaseWecomMessage):
    MsgType: str = "text"
    Content: str
    MsgId: int


class ImageMessage(BaseWecomMessage):
    MsgType: str = "image"
    PicUrl: str
    MediaId: str
    MsgId: int


class VoiceMessage(BaseWecomMessage):
    MsgType: str = "voice"
    MediaId: str
    Format: str
    MsgId: int


class VideoMessage(BaseWecomMessage):
    MsgType: str = "video"
    MediaId: str
    ThumbMediaId: str
    MsgId: int


class LocationMessage(BaseWecomMessage):
    MsgType: str = "location"
    Location_X: float
    Location_Y: float
    Scale: int
    Label: str
    MsgId: int
    AppType: Optional[str] = None


class LinkMessage(BaseWecomMessage):
    MsgType: str = "link"
    Title: str
    Description: str
    Url: str
    MsgId: int


class BaseEventMessage(BaseWecomMessage):
    MsgType: str = "event"
    Event: str


class SubscribeEvent(BaseEventMessage):
    Event: str = "subscribe"
    EventKey: Optional[str] = None


class UnsubscribeEvent(BaseEventMessage):
    Event: str = "unsubscribe"
    EventKey: Optional[str] = None


class EnterAgentEvent(BaseEventMessage):
    Event: str = "enter_agent"
    EventKey: Optional[str] = None


class LocationEvent(BaseEventMessage):
    Event: str = "LOCATION"
    Latitude: float
    Longitude: float
    Precision: float
    AppType: Optional[str] = None


class BatchJobResultEvent(BaseEventMessage):
    Event: str = "batch_job_result"
    BatchJob: dict


class ClickEvent(BaseEventMessage):
    Event: str = "click"
    EventKey: str


class ViewEvent(BaseEventMessage):
    Event: str = "view"
    EventKey: str


class ScanCodePushEvent(BaseEventMessage):
    Event: str = "scancode_push"
    EventKey: str
    ScanCodeInfo: dict


class ScanCodeWaitMsgEvent(BaseEventMessage):
    Event: str = "scancode_waitmsg"
    EventKey: str
    ScanCodeInfo: dict

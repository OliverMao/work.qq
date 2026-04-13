"""
企业微信会话内容存档 — HTTP 调用版
无需 C SDK，纯 REST API 实现
"""

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

WECOM_API = "https://qyapi.weixin.qq.com"
_token_lock = threading.Lock()
_access_token: str = ""
_token_expires_at: float = 0


def _fetch_access_token() -> str:
    """获取会话存档专用的 access_token"""
    global _access_token, _token_expires_at
    now = time.time()
    if _access_token and now < _token_expires_at:
        return _access_token

    with _token_lock:
        if _access_token and time.time() < _token_expires_at:
            return _access_token

        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f"{WECOM_API}/cgi-bin/gettoken",
                params={
                    "corpid": settings.corp_id,
                    "corpsecret": settings.chat_archive_secret,
                },
            )
        data = resp.json()
        if data.get("errcode", 0) != 0:
            raise RuntimeError(f"获取 access_token 失败: {data}")

        _access_token = data["access_token"]
        _token_expires_at = time.time() + data.get("expires_in", 7200) - 300
        return _access_token


def _req_api(url: str, params: dict, data: dict = None) -> dict:
    params["access_token"] = _fetch_access_token()
    with httpx.Client(timeout=30) as client:
        if data:
            resp = client.post(url, params=params, json=data)
        else:
            resp = client.get(url, params=params)
    return resp.json()


def get_cur_page_count(starttime: int, endtime: int) -> int:
    """
    获取会话记录页数 (每页100条)
    文档: https://developer.work.weixin.qq.com/document/path/95013
    """
    data = _req_api(
        f"{WECOM_API}/cgi-bin/finance/getcurpagecountcount",
        params={"starttime": starttime, "endtime": endtime},
    )
    if data.get("errcode", 0) != 0:
        raise RuntimeError(f"getcurpagecount 失败: {data}")
    return data.get("page_cnt", 0)


def get_page_content(starttime: int, endtime: int, page: int) -> dict:
    """
    获取指定页会话记录
    文档: https://developer.work.weixin.qq.com/document/path/95014
    """
    data = _req_api(
        f"{WECOM_API}/cgi-bin/finance/getpagecontent",
        params={"starttime": starttime, "endtime": endtime, "page": page},
    )
    if data.get("errcode", 0) != 0:
        raise RuntimeError(f"getpagecontent 失败: {data}")
    return data


def archive_to_file(
    starttime: Optional[int] = None,
    endtime: Optional[int] = None,
    save_dir: Optional[str] = None,
) -> dict:
    """
    拉取会话内容并保存为 JSON 文件

    Returns:
        {
            "errcode": 0,
            "errmsg": "ok",
            "saved_count": 123,
            "save_path": "/path/to/archive_xxx.json",
            "messages": [{...}, ...]
        }
    """
    now_ts = int(time.time())
    if not endtime:
        endtime = now_ts
    if not starttime:
        starttime = now_ts - 86400

    save_dir = save_dir or settings.chat_archive_save_dir
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    try:
        page_cnt = get_cur_page_count(starttime, endtime)
    except Exception as e:
        # 尝试直接拉取 page=0
        try:
            page_data = get_page_content(starttime, endtime, 0)
            page_cnt = 1 if page_data.get("chat_data") else 0
        except Exception as e2:
            return {"errcode": -1, "errmsg": str(e2), "saved_count": 0}

    if page_cnt == 0:
        return {
            "errcode": 0,
            "errmsg": "没有找到会话记录",
            "saved_count": 0,
            "save_path": None,
            "messages": [],
        }

    all_messages: List[Dict[str, Any]] = []
    for page_idx in range(page_cnt):
        try:
            logger.info("拉取第 %d/%d 页...", page_idx + 1, page_cnt)
            data = get_page_content(starttime, endtime, page_idx)
            chat_list = data.get("chat_data", [])
            all_messages.extend(chat_list)
        except Exception as e:
            logger.error("第 %d 页拉取失败: %s", page_idx + 1, e)
            continue

    if not all_messages:
        return {
            "errcode": 0,
            "errmsg": "会话记录为空",
            "saved_count": 0,
            "save_path": None,
            "messages": [],
        }

    ts_str = datetime.fromtimestamp(starttime).strftime("%Y%m%d_%H%M%S")
    ts_end = datetime.fromtimestamp(endtime).strftime("%Y%m%d_%H%M%S")
    filename = f"archive_{ts_str}_{ts_end}.json"
    save_path = os.path.join(save_dir, filename)

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(all_messages, f, ensure_ascii=False, indent=2)

    logger.info("已保存 %d 条会话记录 => %s", len(all_messages), save_path)
    return {
        "errcode": 0,
        "errmsg": "ok",
        "saved_count": len(all_messages),
        "save_path": save_path,
        "messages": all_messages,
    }

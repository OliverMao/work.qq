from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException

from app.config import settings


router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.get("/models")
async def list_available_models() -> Dict[str, Any]:
    """获取可用的 LLM 模型列表"""
    base_url = settings.teacher_agent_llm_base_url
    api_key = settings.teacher_agent_llm_api_key

    if not api_key:
        raise HTTPException(status_code=500, detail="未配置 LLM API Key")

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{base_url}/models",
                headers={"x-api-key": f"{api_key}","anthropic-version": "2023-06-01"},
                
            )
            resp.raise_for_status()
            data = resp.json()

        models = data.get("data", [])
        return {
            "ok": True,
            "models": [
                {
                    "id": m.get("id"),
                    "object": m.get("object"),
                }
                for m in models
            ],
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"获取模型列表失败: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")
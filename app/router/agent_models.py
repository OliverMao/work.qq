from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException

from app.config import settings


router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.get("/models")
async def list_available_models() -> Dict[str, Any]:
    """获取可用的 LLM 模型列表（包含默认模型和别名映射）"""
    from pathlib import Path
    
    base_url = settings.teacher_agent_llm_base_url
    api_key = settings.teacher_agent_llm_api_key
    aliases = settings.teacher_agent_model_aliases
    default_models = settings.teacher_agent_default_models

    result_models = []
    added_ids = set()

    prompt_dir = Path(settings.teacher_agent_prompt_dir)
    config_file = prompt_dir / "auto_reply_config.txt"
    default_model = "deepseek/deepseek-v4-flash"
    if config_file.exists():
        for line in config_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("model="):
                default_model = line.split("=", 1)[1].strip()
                break

    default_model_mapped = aliases.get(default_model, default_model)
    result_models.insert(0, {
        "id": default_model,
        "name": default_model_mapped,
        "object": "model",
        "default": True,
    })
    added_ids.add(default_model)

    for dm in default_models:
        model_id = dm.get("id", "")
        if model_id and model_id not in added_ids:
            mapped_name = aliases.get(model_id, dm.get("name", model_id))
            result_models.append({
                "id": model_id,
                "name": mapped_name,
                "object": "model",
            })
            added_ids.add(model_id)

    if api_key and base_url:
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(
                    f"{base_url}/models",
                    headers={"x-api-key": f"{api_key}", "anthropic-version": "2023-06-01"},
                )
                resp.raise_for_status()
                data = resp.json()

            for m in data.get("data", []):
                model_id = m.get("id", "")
                if model_id and model_id not in added_ids:
                    mapped_name = aliases.get(model_id, model_id)
                    result_models.append({
                        "id": model_id,
                        "name": mapped_name,
                        "object": m.get("object"),
                    })
                    added_ids.add(model_id)
        except Exception:
            pass

    return {
        "ok": True,
        "models": result_models,
        "aliases": aliases,
    }
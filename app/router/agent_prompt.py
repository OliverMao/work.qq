from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings


class PromptSaveRequest(BaseModel):
	content: str
	filename: str


router = APIRouter(prefix="/api/agent/prompt", tags=["Agent Prompt"])


def _get_prompt_dir() -> Path:
	return Path(settings.teacher_agent_prompt_dir)


@router.get("/{filename}")
async def get_prompt(filename: str):
	prompt_dir = _get_prompt_dir()
	file_path = prompt_dir / filename
	if not file_path.exists():
		raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")
	return FileResponse(path=str(file_path), media_type="text/plain; charset=utf-8")


@router.post("/save")
async def save_prompt(req: PromptSaveRequest):
	prompt_dir = _get_prompt_dir()
	prompt_dir.mkdir(parents=True, exist_ok=True)

	allowed_files = {"system_role.txt", "task_template.txt", "constraints.txt", "auto_reply_config.txt"}
	if req.filename not in allowed_files:
		raise HTTPException(status_code=400, detail=f"不允许的文件名: {req.filename}")

	file_path = prompt_dir / req.filename
	file_path.write_text(req.content, encoding="utf-8")
	return {"ok": True, "filename": req.filename, "path": str(file_path)}


@router.get("/")
async def list_prompts():
	prompt_dir = _get_prompt_dir()
	allowed_files = ["system_role.txt", "task_template.txt", "constraints.txt", "auto_reply_config.txt"]
	files = []
	for name in allowed_files:
		file_path = prompt_dir / name
		files.append({
			"name": name,
			"path": str(file_path),
			"exists": file_path.exists(),
			"size": file_path.stat().st_size if file_path.exists() else 0,
		})
	return {"files": files}


@router.get("/config/auto-reply")
async def get_auto_reply_config():
	"""获取自动发信配置"""
	prompt_dir = _get_prompt_dir()
	file_path = prompt_dir / "auto_reply_config.txt"
	if not file_path.exists():
		return {
			"model": "deepseek/deepseek-v4-flash",
			"target_chatid": "fangya001",
		}
	content = file_path.read_text(encoding="utf-8")
	config = {}
	for line in content.splitlines():
		line = line.strip()
		if not line or line.startswith("#"):
			continue
		if "=" in line:
			key, value = line.split("=", 1)
			config[key.strip()] = value.strip()
	return config


class AutoReplyConfigSaveRequest(BaseModel):
	model: str
	target_chatid: str


@router.post("/config/auto-reply")
async def save_auto_reply_config(req: AutoReplyConfigSaveRequest):
	"""保存自动发信配置"""
	prompt_dir = _get_prompt_dir()
	prompt_dir.mkdir(parents=True, exist_ok=True)
	file_path = prompt_dir / "auto_reply_config.txt"
	content = f"# 自动发信配置\nmodel={req.model}\ntarget_chatid={req.target_chatid}\n"
	file_path.write_text(content, encoding="utf-8")
	return {"ok": True, "model": req.model, "target_chatid": req.target_chatid}
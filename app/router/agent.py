from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.agent.agent import generate_teacher_reply, build_teacher_assistant_index


class TeacherReplyRequest(BaseModel):
	stu_message: str
	chat_id: Optional[str] = None
	history: Optional[List[Dict[str, Any]]] = None
	model: Optional[str] = None


class TeacherReplyResponse(BaseModel):
	ok: bool
	chat_id: Optional[str]
	stu_message: str
	model: Optional[str]
	reply: str
	history: Optional[List[Dict[str, Any]]]
	retrieval: Dict[str, Any]
	used_context: List[Dict[str, Any]]


class BuildIndexRequest(BaseModel):
	rebuild: bool = False
	target_file: Optional[str] = None


class BuildIndexResponse(BaseModel):
	ok: bool
	collection_name: str
	persist_dir: str
	source_count: int
	turn_count: int
	chunk_count: int
	added_chunk_count: int
	skipped_chunk_count: int
	rebuild: bool
	target_file: Optional[str]


router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.post("/reply", response_model=TeacherReplyResponse)
async def teacher_reply(req: TeacherReplyRequest) -> TeacherReplyResponse:
	try:
		result = generate_teacher_reply(
			stu_message=req.stu_message,
			chat_id=req.chat_id,
			history=req.history,
			model=req.model,
		)
		return TeacherReplyResponse(**result)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc))
	except RuntimeError as exc:
		raise HTTPException(status_code=500, detail=str(exc))
	except Exception as exc:
		raise HTTPException(status_code=500, detail=f"Agent 执行失败: {exc}")


@router.post("/build-index", response_model=BuildIndexResponse)
async def build_index(req: BuildIndexRequest) -> BuildIndexResponse:
	try:
		result = build_teacher_assistant_index(
			rebuild=req.rebuild,
			target_file=req.target_file,
		)
		return BuildIndexResponse(**result)
	except Exception as exc:
		raise HTTPException(status_code=500, detail=f"索引构建失败: {exc}")
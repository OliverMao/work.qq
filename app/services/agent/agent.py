import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.agent.parser import collect_source_files
from app.services.agent.types import DialogueChunk
from app.services.agent.vectorstore import VectorStoreManager


logger = logging.getLogger(__name__)


class TeacherAssistantRAGAgent:
	def __init__(
		self,
		archive_dir: Optional[str] = None,
		persist_dir: Optional[str] = None,
		prompt_dir: Optional[str] = None,
		collection_name: Optional[str] = None,
	) -> None:
		self.archive_dir = Path(archive_dir or settings.teacher_agent_archive_dir)
		self.persist_dir = Path(persist_dir or settings.teacher_agent_vector_dir)
		self.prompt_dir = Path(prompt_dir or settings.teacher_agent_prompt_dir)
		self.collection_name = collection_name or settings.teacher_agent_collection_name

		self.window_size = max(2, settings.teacher_agent_window_size)
		self.window_overlap = max(1, settings.teacher_agent_window_overlap)
		self.same_chat_top_k = max(1, settings.teacher_agent_same_chat_top_k)
		self.global_top_k = max(1, settings.teacher_agent_global_top_k)
		self.min_same_chat_hits = max(1, settings.teacher_agent_min_same_chat_hits)
		self.max_context_chunks = max(1, settings.teacher_agent_max_context_chunks)
		self.distance_threshold = settings.teacher_agent_distance_threshold

		self._vectorstore_manager: Optional[VectorStoreManager] = None
		self._llm = None

	def _get_vectorstore_manager(self) -> VectorStoreManager:
		if self._vectorstore_manager is None:
			self._vectorstore_manager = VectorStoreManager(
				persist_dir=self.persist_dir,
				collection_name=self.collection_name,
				embedding_api_key=settings.teacher_agent_embedding_api_key,
				embedding_model=settings.teacher_agent_embedding_model,
				embedding_base_url=settings.teacher_agent_embedding_base_url or "",
				window_size=self.window_size,
				window_overlap=self.window_overlap,
			)
		return self._vectorstore_manager

	def _read_prompt_file(self, filename: str) -> str:
		prompt_path = self.prompt_dir / filename
		if not prompt_path.exists():
			raise FileNotFoundError(f"提示词文件不存在: {prompt_path}")
		return prompt_path.read_text(encoding="utf-8").strip()

	def _load_prompts(self) -> Dict[str, str]:
		return {
			"system": self._read_prompt_file("system_role.txt"),
			"task": self._read_prompt_file("task_template.txt"),
			"constraints": self._read_prompt_file("constraints.txt"),
		}

	@staticmethod
	def _normalize_reply_content(content: Any) -> str:
		if isinstance(content, str):
			return content.strip()

		if isinstance(content, list):
			text_parts: List[str] = []
			for item in content:
				if isinstance(item, str):
					text_parts.append(item)
					continue
				if isinstance(item, dict):
					text = item.get("text")
					if text:
						text_parts.append(str(text))
			return "\n".join(part.strip() for part in text_parts if part.strip())

		return str(content).strip()

	@staticmethod
	def _build_history_context(history: Optional[List[Dict[str, Any]]]) -> str:
		if not history:
			return "无历史上下文"

		turns: List[str] = []
		for turn in history:
			role = turn.get("role", "unknown")
			text = turn.get("content", "") or turn.get("text", "")
			if text:
				turns.append(f"{role}: {text.strip()}")
		if not turns:
			return "无历史上下文"
		return "\n".join(turns)

	@staticmethod
	def _build_context_payload(docs: List[Any]) -> str:
		if not docs:
			return "无可用历史片段。"

		chunks: List[str] = []
		for idx, doc in enumerate(docs, start=1):
			metadata = getattr(doc, "metadata", {}) or {}
			chat_id = metadata.get("chat_id", "unknown")
			line_start = metadata.get("line_start", "?")
			line_end = metadata.get("line_end", "?")
			source_file = metadata.get("source_file", "")
			body = str(getattr(doc, "page_content", "")).strip()
			chunks.append(
				f"[片段{idx}] chat_id={chat_id}, lines={line_start}-{line_end}, source={source_file}\n{body}"
			)
		return "\n\n".join(chunks)

	def _ensure_index_ready(self) -> None:
		vectorstore_manager = self._get_vectorstore_manager()
		manifest = vectorstore_manager._load_manifest()
		indexed_chunk_ids = manifest.get("indexed_chunk_ids") or []
		if indexed_chunk_ids:
			return
		logger.info("向量索引为空，开始自动建库")
		self.build_vector_store(rebuild=False)

	def build_vector_store(
		self,
		rebuild: bool = False,
		target_file: Optional[str] = None,
	) -> Dict[str, Any]:
		vectorstore_manager = self._get_vectorstore_manager()
		return vectorstore_manager.build(
			archive_dir=self.archive_dir,
			rebuild=rebuild,
			target_file=target_file,
		)

	def _retrieve_context(self, stu_message: str, chat_id: Optional[str]) -> tuple[List[Any], Dict[str, Any]]:
		vectorstore_manager = self._get_vectorstore_manager()
		return vectorstore_manager.retrieve(
			stu_message=stu_message,
			chat_id=chat_id,
			same_chat_top_k=self.same_chat_top_k,
			global_top_k=self.global_top_k,
			min_same_chat_hits=self.min_same_chat_hits,
			max_context_chunks=self.max_context_chunks,
			distance_threshold=self.distance_threshold,
		)

	def _get_llm(self, model: Optional[str] = None):
		override_key = f"_llm_{model}"
		if hasattr(self, override_key) and getattr(self, override_key) is not None:
			return getattr(self, override_key)

		try:
			from langchain_openai import ChatOpenAI
		except ImportError as exc:
			raise RuntimeError(
				"缺少 langchain-openai，请先安装 requirements.txt 中新增依赖"
			) from exc

		api_key = settings.teacher_agent_llm_api_key
		if not api_key:
			raise RuntimeError("缺少 LLM API Key，请配置 TEACHER_AGENT_LLM_API_KEY")

		kwargs: Dict[str, Any] = {
			"model": model or settings.teacher_agent_llm_model,
			"api_key": api_key,
			"temperature": settings.teacher_agent_llm_temperature,
		}
		if settings.teacher_agent_llm_base_url:
			kwargs["base_url"] = settings.teacher_agent_llm_base_url

		llm = ChatOpenAI(**kwargs)
		if model:
			setattr(self, override_key, llm)
		else:
			self._llm = llm
		return llm

	def generate_teacher_reply(
		self,
		stu_message: str,
		chat_id: Optional[str] = None,
		history: Optional[List[Dict[str, Any]]] = None,
		model: Optional[str] = None,
		auto_build_index: bool = True,
	) -> Dict[str, Any]:
		content = str(stu_message or "").strip()
		if not content:
			raise ValueError("Stu 消息不能为空")

		normalized_chat_id = str(chat_id or "").strip() or None

		if auto_build_index:
			self._ensure_index_ready()

		docs, retrieval_info = self._retrieve_context(
			stu_message=content,
			chat_id=normalized_chat_id,
		)

		prompts = self._load_prompts()
		context_text = self._build_context_payload(docs)
		history_context = self._build_history_context(history)
		fallback_hint = (
			"当前检索依据偏弱：请优先给出温和确认 + 1个澄清问题 + 保守可执行建议。"
			if retrieval_info.get("weak_retrieval")
			else "当前检索依据可用：请在不编造事实的前提下生成具体建议。"
		)

		task_prompt = prompts["task"].format(
			stu_message=content,
			chat_id=normalized_chat_id or "unknown",
			retrieved_context=context_text,
			history_context=history_context,
		)

		human_prompt = (
			f"{task_prompt}\n\n"
			f"【回复约束】\n{prompts['constraints']}\n\n"
			f"【检索判定】\n{fallback_hint}"
		)

		try:
			from langchain_core.messages import HumanMessage, SystemMessage
		except ImportError as exc:
			raise RuntimeError(
				"缺少 langchain-core，请先安装 requirements.txt 中新增依赖"
			) from exc

		llm = self._get_llm(model=model)
		llm_response = llm.invoke(
			[
				SystemMessage(content=prompts["system"]),
				HumanMessage(content=human_prompt),
			]
		)
		reply = self._normalize_reply_content(getattr(llm_response, "content", ""))

		used_context = []
		for doc in docs:
			metadata = getattr(doc, "metadata", {}) or {}
			used_context.append(
				{
					"chunk_id": metadata.get("chunk_id"),
					"chat_id": metadata.get("chat_id"),
					"line_start": metadata.get("line_start"),
					"line_end": metadata.get("line_end"),
					"source_file": metadata.get("source_file"),
					"content": str(getattr(doc, "page_content", "")),
				}
			)

		return {
			"ok": True,
			"chat_id": normalized_chat_id,
			"stu_message": content,
			"model": model,
			"reply": reply,
			"history": history,
			"retrieval": retrieval_info,
			"used_context": used_context,
		}


teacher_assistant_agent = TeacherAssistantRAGAgent()


def build_teacher_assistant_index(
	rebuild: bool = False,
	target_file: Optional[str] = None,
) -> Dict[str, Any]:
	return teacher_assistant_agent.build_vector_store(
		rebuild=rebuild,
		target_file=target_file,
	)


def generate_teacher_reply(
	stu_message: str,
	chat_id: Optional[str] = None,
	history: Optional[List[Dict[str, Any]]] = None,
	model: Optional[str] = None,
	auto_build_index: bool = True,
) -> Dict[str, Any]:
	return teacher_assistant_agent.generate_teacher_reply(
		stu_message=stu_message,
		chat_id=chat_id,
		history=history,
		model=model,
	)


import argparse
import json


def _build_cli_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Teacher Assistant RAG Agent")
	subparsers = parser.add_subparsers(dest="command", required=True)

	build_parser = subparsers.add_parser("build-index", help="构建或增量更新向量库")
	build_parser.add_argument(
		"--rebuild",
		action="store_true",
		help="清空原 collection 后全量重建",
	)
	build_parser.add_argument(
		"--target-file",
		default=None,
		help="仅处理单个文件或指定目录，如 wrgMDdBgAA_IJn_FDcoEBqxakJNPNcFw.txt",
	)

	reply_parser = subparsers.add_parser("reply", help="根据 Stu 消息生成 Tea 回复")
	reply_parser.add_argument("--stu-message", required=True, help="Stu 当前消息")
	reply_parser.add_argument("--chat-id", default=None, help="会话 chat_id（可选）")
	reply_parser.add_argument(
		"--history",
		default=None,
		help="历史对话 JSON 字符串，如 [{role:stu,content:xxx},{role:tea,content:xxx}]",
	)
	reply_parser.add_argument(
		"--model",
		default=None,
		help="LLM 模型名称，覆盖环境变量默认值，如 gpt-4o",
	)
	reply_parser.add_argument(
		"--json-output",
		action="store_true",
		help="以 JSON 输出完整检索与回复结果",
	)

	return parser


def main() -> None:
	parser = _build_cli_parser()
	args = parser.parse_args()

	if args.command == "build-index":
		result = build_teacher_assistant_index(
			rebuild=bool(args.rebuild),
			target_file=args.target_file,
		)
		print(json.dumps(result, ensure_ascii=False, indent=2))
		return

	if args.command == "reply":
		history = None
		if args.history:
			import ast
			import json

			raw = args.history.strip()
			try:
				history = json.loads(raw)
			except Exception:
				try:
					history = ast.literal_eval(raw)
				except Exception:
					pass
		result = generate_teacher_reply(
			stu_message=args.stu_message,
			chat_id=args.chat_id,
			history=history,
			model=args.model,
		)
		if args.json_output:
			print(json.dumps(result, ensure_ascii=False, indent=2))
		else:
			print(result["reply"])
		return

	parser.print_help()


if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
	main()
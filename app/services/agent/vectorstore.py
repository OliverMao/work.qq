import json
import time
import logging
from pathlib import Path
from typing import Any, Dict, List

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_ollama import OllamaEmbeddings

from app.config import settings
from app.services.agent.parser import build_chunks_for_turns, collect_source_files, parse_dialogue_file
from app.services.agent.types import DialogueChunk


logger = logging.getLogger(__name__)


def empty_manifest() -> Dict[str, Any]:
	return {
		"indexed_chunk_ids": [],
		"files": {},
		"last_build_at": None,
	}


class VectorStoreManager:
	def __init__(
		self,
		persist_dir: Path,
		collection_name: str,
		embedding_api_key: str,
		embedding_model: str,
		embedding_base_url: str,
		window_size: int,
		window_overlap: int,
	) -> None:
		self.persist_dir = persist_dir
		self.collection_name = collection_name
		self.embedding_api_key = embedding_api_key
		self.embedding_model = embedding_model
		self.embedding_base_url = embedding_base_url
		self.window_size = window_size
		self.window_overlap = window_overlap
		self.manifest_path = persist_dir / "index_manifest.json"
		self._embeddings: OllamaEmbeddings | OpenAIEmbeddings | None = None
		self._vectorstore: Chroma | None = None

	def _get_embeddings(self) -> OllamaEmbeddings | OpenAIEmbeddings:
		if self._embeddings is not None:
			return self._embeddings

		if self.embedding_base_url and self.embedding_base_url.startswith("http"):
			if not self.embedding_model:
				raise RuntimeError("使用 Ollama 时需要配置 embedding_model")
			self._embeddings = OllamaEmbeddings(
				model=self.embedding_model,
				base_url=self.embedding_base_url.rstrip("/"),
			)
			return self._embeddings

		if not str(self.embedding_api_key or "").strip():
			raise RuntimeError(
				"缺少 Embedding API Key，请配置 TEACHER_AGENT_EMBEDDING_API_KEY "
				"或 TEACHER_AGENT_EMBEDDING_TOKEN"
			)
		kwargs: Dict[str, Any] = {
			"model": self.embedding_model,
			"api_key": self.embedding_api_key.strip(),
		}
		if self.embedding_base_url:
			kwargs["base_url"] = self.embedding_base_url
		self._embeddings = OpenAIEmbeddings(**kwargs)
		return self._embeddings

	def _get_vectorstore(self) -> Chroma:
		if self._vectorstore is None:
			self.persist_dir.mkdir(parents=True, exist_ok=True)
			self._vectorstore = Chroma(
				collection_name=self.collection_name,
				persist_directory=str(self.persist_dir),
				embedding_function=self._get_embeddings(),
			)
		return self._vectorstore

	def _reset_vectorstore(self) -> None:
		vectorstore = self._get_vectorstore()
		try:
			vectorstore.delete_collection()
		except Exception as exc:
			logger.warning("删除旧 collection 失败，将继续覆盖式写入: %s", exc)
		self._vectorstore = None

	def _load_manifest(self) -> Dict[str, Any]:
		if not self.manifest_path.exists():
			return empty_manifest()
		try:
			payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
		except Exception:
			return empty_manifest()
		if not isinstance(payload, dict):
			return empty_manifest()
		payload.setdefault("indexed_chunk_ids", [])
		payload.setdefault("files", {})
		payload.setdefault("last_build_at", None)
		return payload

	def _save_manifest(self, manifest: Dict[str, Any]) -> None:
		self.persist_dir.mkdir(parents=True, exist_ok=True)
		self.manifest_path.write_text(
			json.dumps(manifest, ensure_ascii=False, indent=2),
			encoding="utf-8",
		)

	def build(
		self,
		archive_dir: Path,
		rebuild: bool = False,
		target_file: str | None = None,
	) -> Dict[str, Any]:
		from app.config import settings
		
		exclude_roomids = set(settings.teacher_agent_exclude_roomids)
		
		source_files = collect_source_files(archive_dir, target_file)
		if rebuild:
			self._reset_vectorstore()
			manifest = empty_manifest()
		else:
			manifest = self._load_manifest()

		indexed_ids = set(str(item) for item in manifest.get("indexed_chunk_ids", []))
		files_meta = manifest.get("files", {})

		docs_to_add: List[Document] = []
		ids_to_add: List[str] = []
		total_turns = 0
		total_chunks = 0
		skipped_chunks = 0

		for file_path in source_files:
			turns = parse_dialogue_file(file_path)
			chunks = build_chunks_for_turns(
				file_path=file_path,
				turns=turns,
				window_size=self.window_size,
				window_overlap=self.window_overlap,
			)

			total_turns += len(turns)
			total_chunks += len(chunks)

			for chunk in chunks:
				if not rebuild and chunk.chunk_id in indexed_ids:
					skipped_chunks += 1
					continue
				
				if exclude_roomids and chunk.chat_id in exclude_roomids:
					skipped_chunks += 1
					continue

				docs_to_add.append(
					Document(
						page_content=chunk.content,
						metadata={
							"chunk_id": chunk.chunk_id,
							"chat_id": chunk.chat_id,
							"line_start": chunk.line_start,
							"line_end": chunk.line_end,
							"roles_summary": chunk.roles_summary,
							"source_file": chunk.source_file,
						},
					)
				)
				ids_to_add.append(chunk.chunk_id)
				indexed_ids.add(chunk.chunk_id)

			files_meta[str(file_path.as_posix())] = {
				"turn_count": len(turns),
				"chunk_count": len(chunks),
			}

		added_chunks = 0
		if docs_to_add:
			vectorstore = self._get_vectorstore()
			try:
				vectorstore.add_documents(documents=docs_to_add, ids=ids_to_add)
			except Exception as exc:
				message = str(exc).lower()
				if (
					"authenticationerror" in exc.__class__.__name__.lower()
					or "401" in message
					or "invalid proxy server token" in message
					or "token_not_found_in_db" in message
				):
					raise RuntimeError(
						"Embedding 鉴权失败。请检查 TEACHER_AGENT_EMBEDDING_API_KEY "
						"或 TEACHER_AGENT_EMBEDDING_TOKEN，以及 "
						"TEACHER_AGENT_EMBEDDING_BASE_URL 或 "
						"TEACHER_AGENT_EMBEDDING_HOST。"
					) from exc
				raise
			added_chunks = len(docs_to_add)

		manifest["indexed_chunk_ids"] = sorted(indexed_ids)
		manifest["files"] = files_meta
		manifest["last_build_at"] = int(time.time())
		self._save_manifest(manifest)

		return {
			"ok": True,
			"collection_name": self.collection_name,
			"persist_dir": str(self.persist_dir.as_posix()),
			"source_count": len(source_files),
			"turn_count": total_turns,
			"chunk_count": total_chunks,
			"added_chunk_count": added_chunks,
			"skipped_chunk_count": skipped_chunks,
			"rebuild": rebuild,
			"target_file": target_file,
		}

	def retrieve(
		self,
		stu_message: str,
		chat_id: str | None,
		same_chat_top_k: int,
		global_top_k: int,
		min_same_chat_hits: int,
		max_context_chunks: int,
		distance_threshold: float,
	) -> tuple[List[Any], Dict[str, Any]]:
		vectorstore = self._get_vectorstore()

		same_chat_docs: List[Any] = []
		
		if chat_id:
			try:
				same_chat_docs = vectorstore.max_marginal_relevance_search(
					query=stu_message,
					k=same_chat_top_k,
					fetch_k=max(8, same_chat_top_k * 3),
					filter={"chat_id": chat_id},
				)
			except Exception as exc:
				logger.warning("同会话检索失败，将退化为全库检索: %s", exc)

		retrieved_docs = list(same_chat_docs)
		used_global_fallback = len(retrieved_docs) < min_same_chat_hits

		if used_global_fallback:
			global_docs = vectorstore.max_marginal_relevance_search(
				query=stu_message,
				k=global_top_k,
				fetch_k=max(12, global_top_k * 4),
			)
			retrieved_docs = self._merge_docs(retrieved_docs, global_docs)

		retrieved_docs = retrieved_docs[:max_context_chunks]
		weak_retrieval = self._check_weak_retrieval(vectorstore, stu_message, chat_id, retrieved_docs, distance_threshold)

		retrieval_info = {
			"same_chat_hits": len(same_chat_docs),
			"used_global_fallback": used_global_fallback,
			"retrieved_count": len(retrieved_docs),
			"weak_retrieval": weak_retrieval,
			"distance_threshold": distance_threshold,
		}
		return retrieved_docs, retrieval_info

	@staticmethod
	def _merge_docs(base_docs: List[Any], extra_docs: List[Any]) -> List[Any]:
		merged: List[Any] = []
		seen = set()
		for doc in list(base_docs) + list(extra_docs):
			key = getattr(doc, "metadata", {}) or {}
			chunk_id = key.get("chunk_id")
			if chunk_id:
				key = str(chunk_id)
			else:
				key = f"fallback::{hash(getattr(doc, 'page_content', ''))}"
			if key in seen:
				continue
			seen.add(key)
			merged.append(doc)
		return merged

	def _check_weak_retrieval(
		self,
		vectorstore: Chroma,
		stu_message: str,
		chat_id: str | None,
		docs: List[Any],
		distance_threshold: float,
	) -> bool:
		if not docs:
			return True
		filter_payload = {"chat_id": chat_id} if chat_id else None
		score: float | None = None
		try:
			if filter_payload:
				scored_docs = vectorstore.similarity_search_with_score(
					stu_message, k=1, filter=filter_payload
				)
				if not scored_docs:
					scored_docs = vectorstore.similarity_search_with_score(stu_message, k=1)
			else:
				scored_docs = vectorstore.similarity_search_with_score(stu_message, k=1)
			if scored_docs:
				score = float(scored_docs[0][1])
		except Exception as exc:
			logger.warning("检索分数评估失败，将按已有召回继续: %s", exc)
		if score is None:
			return False
		return score > distance_threshold
import re
from pathlib import Path
from typing import List, Sequence

from app.services.agent.types import DialogueChunk, DialogueTurn


ROLE_LINE_PATTERN = re.compile(r"^\s*(Tea|Stu)\s*:\s*(.*)$", re.IGNORECASE)


def restore_text(text: str) -> str:
	return str(text).replace("\\r\\n", "\n").replace("\\n", "\n").strip()


def parse_dialogue_file(file_path: Path) -> List[DialogueTurn]:
	lines = file_path.read_text(encoding="utf-8").splitlines()
	turns: List[DialogueTurn] = []

	for line_no, raw_line in enumerate(lines, start=1):
		line = raw_line.strip()
		if not line:
			continue

		match = ROLE_LINE_PATTERN.match(line)
		if not match:
			continue

		role = match.group(1).title()
		text = restore_text(match.group(2))
		if not text:
			continue

		turns.append(DialogueTurn(role=role, text=text, line_no=line_no))

	return turns


def roles_summary(turns: Sequence[DialogueTurn]) -> str:
	tea_count = sum(1 for turn in turns if turn.role == "Tea")
	stu_count = sum(1 for turn in turns if turn.role == "Stu")
	return f"Tea:{tea_count},Stu:{stu_count}"


def build_chunks_for_turns(
	file_path: Path,
	turns: Sequence[DialogueTurn],
	window_size: int,
	window_overlap: int,
) -> List[DialogueChunk]:
	if not turns:
		return []

	chat_id = file_path.stem
	source_file = str(file_path.as_posix())

	step = max(1, window_size - window_overlap)
	chunks: List[DialogueChunk] = []

	for start in range(0, len(turns), step):
		window_turns = turns[start : start + window_size]
		if not window_turns:
			continue

		line_start = window_turns[0].line_no
		line_end = window_turns[-1].line_no
		roles_summ = roles_summary(window_turns)
		content = "\n".join(f"{turn.role}: {turn.text}" for turn in window_turns)
		chunk_id = f"{chat_id}:{line_start}-{line_end}"

		chunks.append(
			DialogueChunk(
				chunk_id=chunk_id,
				chat_id=chat_id,
				line_start=line_start,
				line_end=line_end,
				roles_summary=roles_summ,
				source_file=source_file,
				content=content,
			)
		)

		if start + window_size >= len(turns):
			break

	return chunks


def collect_source_files(archive_dir: Path, target_file: str | None = None) -> List[Path]:
	if target_file:
		raw_candidate = Path(target_file)
		if raw_candidate.is_absolute():
			candidate = raw_candidate
		else:
			project_candidate = Path(__file__).resolve().parents[3] / raw_candidate
			if project_candidate.exists():
				candidate = project_candidate
			else:
				candidate = archive_dir / raw_candidate

		if candidate.is_dir():
			files = sorted(path for path in candidate.rglob("*.txt") if path.is_file())
		elif candidate.is_file():
			files = [candidate]
		else:
			raise FileNotFoundError(f"找不到目标文件或目录: {candidate}")
	else:
		if not archive_dir.exists():
			raise FileNotFoundError(f"存档目录不存在: {archive_dir}")
		files = sorted(path for path in archive_dir.rglob("*.txt") if path.is_file())

	if not files:
		raise FileNotFoundError("未找到可建库的 txt 对话文件")
	return files

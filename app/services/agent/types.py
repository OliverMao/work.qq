from dataclasses import dataclass


@dataclass(frozen=True)
class DialogueTurn:
	role: str
	text: str
	line_no: int


@dataclass(frozen=True)
class DialogueChunk:
	chunk_id: str
	chat_id: str
	line_start: int
	line_end: int
	roles_summary: str
	source_file: str
	content: str
import re
import uuid
from collections import defaultdict

from civsim.memory.store import MemoryRecord, MemoryStore


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class InMemoryMemory(MemoryStore):
    def __init__(self) -> None:
        self._records: dict[str, list[MemoryRecord]] = defaultdict(list)

    def record_idea(
        self,
        text: str,
        entity_id: str | None,
        outcome: str,
        turn: int,
        game_id: str,
    ) -> MemoryRecord:
        record = MemoryRecord(
            id=str(uuid.uuid4())[:8],
            kind="idea",
            text=text,
            metadata={"entity_id": entity_id, "outcome": outcome},
            turn=turn,
        )
        self._records[game_id].append(record)
        return record

    def record_event(
        self,
        event_type: str,
        description: str,
        impacts: list[dict],
        turn: int,
        game_id: str,
    ) -> MemoryRecord:
        record = MemoryRecord(
            id=str(uuid.uuid4())[:8],
            kind="event",
            text=f"{event_type}: {description}",
            metadata={"impacts": impacts},
            turn=turn,
        )
        self._records[game_id].append(record)
        return record

    def search_similar(self, query: str, game_id: str, limit: int = 5) -> list[MemoryRecord]:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        scored: list[tuple[float, MemoryRecord]] = []
        for record in self._records.get(game_id, []):
            r_tokens = _tokenize(record.text)
            if not r_tokens:
                continue
            overlap = len(q_tokens & r_tokens) / len(q_tokens | r_tokens)
            if overlap > 0:
                scored.append((overlap, record))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:limit]]

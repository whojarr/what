"""
Weaviate adapter stub — future implementation.

To integrate:
1. pip install weaviate-client
2. Implement MemoryStore methods using Weaviate collections
3. Use vectorizer for search_similar; bag-of-words in InMemoryMemory is the v1 fallback

Example collection schema:
- class: GameMemory
- properties: game_id, kind, text, turn, metadata (json)
"""

from civsim.memory.store import MemoryStore


class WeaviateMemory(MemoryStore):
    """Placeholder — raises NotImplementedError until Weaviate is configured."""

    def __init__(self, url: str, api_key: str | None = None) -> None:
        self.url = url
        self.api_key = api_key

    def record_idea(self, text, entity_id, outcome, turn, game_id):
        raise NotImplementedError("Weaviate adapter not implemented in v1")

    def record_event(self, event_type, description, impacts, turn, game_id):
        raise NotImplementedError("Weaviate adapter not implemented in v1")

    def search_similar(self, query, game_id, limit=5):
        raise NotImplementedError("Weaviate adapter not implemented in v1")

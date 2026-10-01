import json
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from colorstack_ai.ingestion.models import (
    DeletedDiscordMessage,
    NormalizedDiscordMessage,
)

logger = logging.getLogger(__name__)


class MessageStore(ABC):
    @abstractmethod
    def has(self, message_id: str) -> bool:
        pass

    @abstractmethod
    async def insert(self, message: NormalizedDiscordMessage) -> bool:
        pass

    @abstractmethod
    async def upsert(self, message: NormalizedDiscordMessage) -> None:
        pass

    @abstractmethod
    async def mark_deleted(self, deletion: DeletedDiscordMessage) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass


class JsonlMessageStore(MessageStore):
    """Append-only verification store that preserves updates and tombstones."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._known_message_ids: set[str] = set()
        self._file: TextIO | None = None

    async def open(self) -> "JsonlMessageStore":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.touch(exist_ok=True)
        self._load_known_message_ids()
        self._file = self._path.open("a", encoding="utf-8", buffering=1)
        return self

    def has(self, message_id: str) -> bool:
        return message_id in self._known_message_ids

    async def insert(self, message: NormalizedDiscordMessage) -> bool:
        if self.has(message.id):
            return False

        self._known_message_ids.add(message.id)
        self._append("upsert", "message", message)
        return True

    async def upsert(self, message: NormalizedDiscordMessage) -> None:
        self._known_message_ids.add(message.id)
        self._append("upsert", "message", message)

    async def mark_deleted(self, deletion: DeletedDiscordMessage) -> None:
        self._append("delete", "deletion", deletion)

    async def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def _load_known_message_ids(self) -> None:
        with self._path.open(encoding="utf-8") as records:
            for line_number, line in enumerate(records, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if record.get("operation") == "upsert":
                        message_id = record.get("message", {}).get("id")
                        if message_id:
                            self._known_message_ids.add(str(message_id))
                except (json.JSONDecodeError, AttributeError):
                    logger.warning(
                        "Skipping malformed record in %s at line %d",
                        self._path,
                        line_number,
                    )

    def _append(
        self,
        operation: str,
        payload_key: str,
        payload: NormalizedDiscordMessage | DeletedDiscordMessage,
    ) -> None:
        if self._file is None:
            raise RuntimeError("JSONL store is not open")

        record = {
            "operation": operation,
            "recordedAt": datetime.now(UTC).isoformat(),
            payload_key: payload.model_dump(mode="json", by_alias=True),
        }
        self._file.write(json.dumps(record, separators=(",", ":")) + "\n")

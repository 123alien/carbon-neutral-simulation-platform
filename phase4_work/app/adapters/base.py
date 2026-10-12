from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ExtractedRecord:
    payload: dict[str, Any]

class DataSourceAdapter(ABC):
    def __init__(self, config: dict, credentials: dict | None = None):
        self.config=config; self.credentials=credentials or {}
    @abstractmethod
    def test_connection(self) -> dict: ...
    @abstractmethod
    def extract(self) -> list[ExtractedRecord]: ...

class AdapterRegistry:
    _adapters={}
    @classmethod
    def register(cls, source_type, adapter): cls._adapters[source_type]=adapter
    @classmethod
    def create(cls, source_type, config, credentials=None):
        if source_type not in cls._adapters: raise ValueError(f"unsupported source_type: {source_type}")
        return cls._adapters[source_type](config, credentials)
    @classmethod
    def types(cls): return sorted(cls._adapters)

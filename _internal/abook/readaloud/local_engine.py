"""Common local engine frame; adapters wrap providers without importing optional runtimes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence, runtime_checkable

from .model import Synthesis, Voice


@runtime_checkable
class LocalEngine(Protocol):
    id: str

    def voices(self) -> Sequence[Voice]: ...
    def capabilities(self) -> dict[str, Any]: ...
    def resource_needs(self) -> dict[str, Any]: ...
    def synthesize(self, text: str, voice: str) -> Synthesis: ...
    def forget(self) -> None: ...


@dataclass
class ProviderEngine:
    """One model/tier of a local provider, including future providers registered in ReadAloud."""

    id: str
    provider: Any
    offered: Sequence[Voice]

    def voices(self) -> Sequence[Voice]:
        return self.offered

    def capabilities(self) -> dict[str, Any]:
        return {"offline": True, "streaming": True, "languages": sorted({v.language for v in self.offered})}

    def resource_needs(self) -> dict[str, Any]:
        # Actual RAM is measured on this machine, never a vendor estimate.
        return {"device": "cpu", "runtime": "download-on-demand", "ramMb": None}

    def synthesize(self, text: str, voice: str) -> Synthesis:
        if voice not in {v.id for v in self.offered}:
            raise ValueError("Giọng không thuộc máy đọc này")
        return self.provider.synthesize(text, voice.partition(":")[2])

    def forget(self) -> None:
        self.provider.forget()

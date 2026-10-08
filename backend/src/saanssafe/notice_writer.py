"""Optional AI rewriting of a Parent Notice, behind a small protocol.

A NoticeWriter turns NoticeFacts into a ParentNotice in facts.language. It is never
authoritative: notice_service validates every result with notice_guard and serves the
deterministic template whenever the writer fails, is slow, or is disabled.

Only FakeNoticeWriter exists for now. The planned StrandsBedrockWriter (Strands Agents +
Amazon Bedrock, no tools, structured output) will implement the same protocol; nothing
here imports strands or calls Bedrock.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from saanssafe.notice_facts import NoticeFacts, ParentNotice


class NoticeWriterError(Exception):
    """The writer could not produce a notice (service error, throttling, bad output)."""


class NoticeWriter(Protocol):
    name: str  # reported as generated_by, e.g. "bedrock"
    model_id: str

    def write(self, facts: NoticeFacts) -> ParentNotice: ...


class FakeNoticeWriter:
    """Test writer: returns a fixed or computed notice, raises, or sleeps. No network."""

    def __init__(
        self,
        notice: ParentNotice | Callable[[NoticeFacts], ParentNotice] | None = None,
        *,
        error: Exception | None = None,
        delay_s: float = 0.0,
        name: str = "fake",
        model_id: str = "fake-model-v1",
    ) -> None:
        self._notice = notice
        self._error = error
        self._delay_s = delay_s
        self.name = name
        self.model_id = model_id
        self.calls: list[NoticeFacts] = []

    def write(self, facts: NoticeFacts) -> ParentNotice:
        self.calls.append(facts)
        if self._delay_s:
            time.sleep(self._delay_s)
        if self._error is not None:
            raise self._error
        if self._notice is None:
            raise NoticeWriterError("FakeNoticeWriter has no notice configured")
        return self._notice(facts) if callable(self._notice) else self._notice

from dataclasses import dataclass
import re


FUNCTION_BLOCK_RE = re.compile(r"<function\s*=\s*[^>]*>.*?</function>", re.IGNORECASE | re.DOTALL)
FUNCTION_TAG_RE = re.compile(r"</?function[^>]*>?", re.IGNORECASE)
TOOL_JSON_RE = re.compile(
    r"(?m)^\s*\{[^\n{}]*(?:specialty_name|doctor_id|slot_id|explicit_confirmation|"
    r"document_number|insurance_name|limit)[^\n{}]*\}\s*$"
)
PARTIAL_FUNCTION_RE = re.compile(r"<function\s*=\s*.*$", re.IGNORECASE | re.DOTALL)
WHITESPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")


@dataclass(frozen=True)
class SanitizedResponse:
    text: str
    was_sanitized: bool


def sanitize_agent_response(text: str) -> SanitizedResponse:
    original = text
    cleaned = FUNCTION_BLOCK_RE.sub("", text)
    cleaned = PARTIAL_FUNCTION_RE.sub("", cleaned)
    cleaned = FUNCTION_TAG_RE.sub("", cleaned)
    cleaned = TOOL_JSON_RE.sub("", cleaned)
    cleaned = WHITESPACE_BEFORE_PUNCT_RE.sub(r"\1", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return SanitizedResponse(text=cleaned, was_sanitized=cleaned != original.strip())


class StreamingFunctionCallSanitizer:
    def __init__(self) -> None:
        self._buffer = ""
        self.was_sanitized = False

    def push(self, chunk: str) -> str:
        self._buffer += chunk
        return self._drain(keep_tail=True)

    def flush(self) -> str:
        drained = self._drain(keep_tail=False)
        if self._buffer:
            sanitized = sanitize_agent_response(self._buffer)
            self.was_sanitized = self.was_sanitized or sanitized.was_sanitized
            self._buffer = ""
            drained += sanitized.text
        return drained

    def _drain(self, keep_tail: bool) -> str:
        output = ""
        while self._buffer:
            lower = self._buffer.lower()
            start = lower.find("<function")
            if start == -1:
                if keep_tail:
                    tail_len = min(len(self._buffer), len("<function") - 1)
                    if len(self._buffer) == tail_len:
                        break
                    output += self._buffer[:-tail_len]
                    self._buffer = self._buffer[-tail_len:]
                else:
                    output += self._buffer
                    self._buffer = ""
                break

            if start > 0:
                output += self._buffer[:start]
                self._buffer = self._buffer[start:]
                continue

            end = lower.find("</function>")
            if end == -1:
                break

            self.was_sanitized = True
            self._buffer = self._buffer[end + len("</function>") :]
        return output

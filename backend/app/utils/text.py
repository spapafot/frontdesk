import re

# Mirror of the frontend boundary regex in speechQueue.ts: a period only counts
# when followed by whitespace (so "6.50" doesn't split), while ! ? newline ; and
# the Greek ; / middle dot always do.
_BOUNDARY = re.compile(r"\.(?=\s)|[!?\n;·]")


class SentenceChunker:
    """Accumulates streamed text and emits complete sentences as they form.

    Used on the voice path to synthesize TTS per sentence so audio can start
    playing while the rest of the reply is still streaming.
    """

    def __init__(self) -> None:
        self._buffer = ""

    def push(self, delta: str) -> list[str]:
        """Add a chunk of text; return any complete sentences it produced."""
        self._buffer += delta
        sentences: list[str] = []
        while True:
            match = _BOUNDARY.search(self._buffer)
            if not match:
                break
            end = match.end()
            sentence = self._buffer[:end].strip()
            self._buffer = self._buffer[end:]
            if sentence:
                sentences.append(sentence)
        return sentences

    def flush(self) -> str | None:
        """Return the trailing partial sentence (if any) and clear the buffer."""
        rest = self._buffer.strip()
        self._buffer = ""
        return rest or None

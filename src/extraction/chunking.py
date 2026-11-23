"""
Semantic text chunker: splits large documents at semantic boundaries.
Estimates token counts using tiktoken and preserves context across chunks.
"""
from __future__ import annotations

import re
from typing import List, Optional

from src.monitoring.logger import get_logger

logger = get_logger("extraction.chunking")


def estimate_tokens(text: str) -> int:
    """
    Estimate token count without loading tiktoken (which needs network).
    Approximation: 1 token ≈ 4 characters for English text.
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # Fallback: character-based estimate
        return len(text) // 4


class SemanticChunker:
    """
    Splits text at semantic boundaries (paragraphs, headings, sections).
    
    Priority order for split points:
    1. Major headings (##, ###)
    2. Double newlines (paragraph breaks)
    3. Single newlines
    4. Sentence boundaries (. ! ?)
    5. Word boundaries (last resort)
    """

    def __init__(
        self,
        max_tokens: int = 4000,
        overlap_tokens: int = 200,
        min_chunk_tokens: int = 100,
    ):
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.min_chunk_tokens = min_chunk_tokens

    def _split_at_boundaries(self, text: str) -> List[str]:
        """Split text into semantic segments."""
        # Try headings first
        sections = re.split(r"\n(?=#{1,3}\s)", text)
        if len(sections) > 1:
            return sections

        # Paragraph splits
        paragraphs = re.split(r"\n{2,}", text)
        if len(paragraphs) > 1:
            return paragraphs

        # Sentence splits
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) > 1:
            return sentences

        # Character chunks (last resort)
        chunk_size = max(500, len(text) // 4)
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    def chunk(self, text: str) -> List[str]:
        """
        Split text into token-bounded chunks with semantic awareness.
        Returns list of text chunks, each within max_tokens.
        """
        if not text:
            return []

        total_tokens = estimate_tokens(text)
        if total_tokens <= self.max_tokens:
            return [text]

        logger.info(
            f"Chunking text: {total_tokens} tokens → max {self.max_tokens} per chunk"
        )

        segments = self._split_at_boundaries(text)
        chunks: List[str] = []
        current_chunk = ""
        current_tokens = 0

        for segment in segments:
            seg_tokens = estimate_tokens(segment)

            if seg_tokens > self.max_tokens:
                # Segment itself is too large: recursively chunk it
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                    current_tokens = 0
                sub_chunks = self.chunk(segment)
                chunks.extend(sub_chunks)
                continue

            if current_tokens + seg_tokens > self.max_tokens:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # Start new chunk with overlap
                overlap_text = self._get_overlap(current_chunk)
                current_chunk = overlap_text + segment
                current_tokens = estimate_tokens(current_chunk)
            else:
                current_chunk += ("\n\n" if current_chunk else "") + segment
                current_tokens += seg_tokens

        if current_chunk and estimate_tokens(current_chunk) >= self.min_chunk_tokens:
            chunks.append(current_chunk.strip())

        logger.info(f"Produced {len(chunks)} chunks from {total_tokens} tokens")
        return chunks

    def _get_overlap(self, text: str) -> str:
        """Get the last ~overlap_tokens worth of text for context continuity."""
        if not text:
            return ""
        # Approximate: take last N chars
        overlap_chars = self.overlap_tokens * 4
        return text[-overlap_chars:] if len(text) > overlap_chars else text

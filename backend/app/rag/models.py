from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from datetime import datetime


# ── Extraction ─────────────────────────────────────────────────

@dataclass
class ExtractedElement:
    element_type: str          # "text" | "title" | "table" | "image"
    text: str                  # Raw text content (or LLaVA caption for images)
    page_number: int = 0
    section_heading: str = ""  # Most recent Title seen before this element
    formatted_content: str = ""  # For tables: markdown version
    image_bytes: bytes = b""     # For images: raw bytes for LLaVA


# ── Two-tier chunks ─────────────────────────────────────────────

@dataclass
class ParentChunk:
    parent_id: str
    text: str                        # Full section text (all paragraphs combined)
    source_filename: str
    course_id: str
    section_heading: str             # Title element that opened this section
    page_number: int                 # First page of this section
    page_range: Tuple[int, int]      # (first_page, last_page)
    file_id: str = ""                # Which uploaded file this belongs to
    child_chunk_ids: List[str] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    @property
    def num_children(self) -> int:
        return len(self.child_chunk_ids)

    def to_dict(self) -> dict:
        return {
            "parent_id":        self.parent_id,
            "text":             self.text,
            "source_filename":  self.source_filename,
            "course_id":        self.course_id,
            "file_id":          self.file_id,
            "section_heading":  self.section_heading,
            "page_number":      self.page_number,
            "page_range":       list(self.page_range),
            "child_chunk_ids":  self.child_chunk_ids,
            "created_at":       self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ParentChunk":
        return cls(
            parent_id       = d["parent_id"],
            text            = d["text"],
            source_filename = d["source_filename"],
            course_id       = d["course_id"],
            file_id         = d.get("file_id", ""),
            section_heading = d["section_heading"],
            page_number     = d["page_number"],
            page_range      = tuple(d["page_range"]),
            child_chunk_ids = d.get("child_chunk_ids", []),
            created_at      = d.get("created_at", ""),
        )


@dataclass
class RetrievalChunk:
    chunk_id: str
    text: str                   # What gets embedded and searched
    element_type: str           # "text" | "table" | "image"
    page_number: int
    section_heading: str        # Inherited from parent section
    chunk_index: int            # Position within parent section
    source_filename: str
    file_id: str
    course_id: str
    user_id: str
    parent_id: str              # Links to ParentChunk
    created_at: str = ""
    embedder_version: str = "nomic-embed-text-v1"

    formatted_content: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_chroma_metadata(self) -> dict:

        return {
            "chunk_id":          self.chunk_id,
            "parent_id":         self.parent_id,
            "file_id":           self.file_id,
            "course_id":         self.course_id,
            "user_id":           self.user_id,
            "source_filename":   self.source_filename,
            "page_number":       self.page_number,
            "section_heading":   self.section_heading,
            "element_type":      self.element_type,
            "chunk_index":       self.chunk_index,
            "embedder_version":  self.embedder_version,
            "created_at":        self.created_at,
            "formatted_content": self.formatted_content[:500] if self.formatted_content else "",
        }


#  Retrieval results

@dataclass
class RetrievedResult:

    retrieval_chunk: RetrievalChunk
    context_chunk: Optional[object]  # Always None — kept for API compatibility
    parent_chunk: Optional[ParentChunk]

    # Scores (0.0 – 1.0, higher = more relevant)
    vector_score: float = 0.0
    bm25_score: float = 0.0
    combined_score: float = 0.0

    @property
    def citation_label(self) -> str:
        c = self.retrieval_chunk
        section_part = f" — {c.section_heading}" if c.section_heading else ""
        return f"{c.source_filename}{section_part}, p.{c.page_number} ({c.element_type})"


# Ingestion result

@dataclass
class IndexResult:
    # Summary returned after a document is ingested.
    file_id: str
    filename: str
    course_id: str
    total_elements: int = 0
    parent_chunks: int = 0
    retrieval_chunks: int = 0
    text_chunks: int = 0
    table_chunks: int = 0
    image_chunks: int = 0
    status: str = "success"   # "success" | "error" | "duplicate"
    error: str = ""
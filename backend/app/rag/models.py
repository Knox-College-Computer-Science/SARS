from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

### Extraction ###

@dataclass
class ExtractedElement:
    """
    Metadata of atomic element returned by unstructured
    """

    element_type: str  # "text" | "title" | "table" | "image"
    text: str  # Raw text content (or LLaVA caption for images)
    page_number: int = 0
    section_heading: str = ""  # Most recent Title seen before this element
    formatted_content: str = ""  # For tables: Markdown version
    image_bytes: bytes = b""  # For images: raw bytes for Llava


### Chunking ###

@dataclass
class ParentChunk:
    """
    parent_id links all child RetrievalChunks back to this section.
    """
    parent_id: str
    text: str  # Full section text
    source_filename: str
    course_id: str
    section_heading: str  # The Title element that opened this section
    page_number: int  # First page of this section
    page_range: tuple[int, int]  # (first_page, last_page)
    child_chunk_ids: list[str] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    @property
    def num_children(self) -> int:
        return len(self.child_chunk_ids)

    def to_dict(self) -> dict:
        return {
            "parent_id": self.parent_id,
            "text": self.text,
            "source_filename": self.source_filename,
            "course_id": self.course_id,
            "section_heading": self.section_heading,
            "page_number": self.page_number,
            "page_range": list(self.page_range),
            "child_chunk_ids": self.child_chunk_ids,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ParentChunk":
        return cls(
            parent_id=d["parent_id"],
            text=d["text"],
            source_filename=d["source_filename"],
            course_id=d["course_id"],
            section_heading=d["section_heading"],
            page_number=d["page_number"],
            page_range=tuple(d["page_range"]),
            child_chunk_ids=d.get("child_chunk_ids", []),
            created_at=d.get("created_at", ""),
        )


@dataclass
class RetrievalChunk:
    """
    Small, clean chunk for embedding and vector search.
    """
    chunk_id: str
    text: str  # What gets embedded and searched
    element_type: str  # "text" | "table" | "image"
    page_number: int
    section_heading: str  # Inherited from parent section
    chunk_index: int  # Position within parent section
    source_filename: str
    file_id: str
    course_id: str
    user_id: str
    parent_id: str  # Links to ParentChunk
    created_at: str = ""
    embedder_version: str = "nomic-embed-text-v1"

    # Atomic element extras
    # For tables: LLM sees this (markdown) instead of flat text
    # For images: empty (LLM sees the caption which is already in .text)
    formatted_content: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_chroma_metadata(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "parent_id": self.parent_id,
            "file_id": self.file_id,
            "course_id": self.course_id,
            "user_id": self.user_id,
            "source_filename": self.source_filename,
            "page_number": self.page_number,
            "section_heading": self.section_heading,
            "element_type": self.element_type,
            "chunk_index": self.chunk_index,
            "embedder_version": self.embedder_version,
            "created_at": self.created_at,
            # Truncate to stay within ChromaDB metadata size limit
            "formatted_content": self.formatted_content[:500] if self.formatted_content else "",
        }


@dataclass
class ContextChunk:
    """
    What the LLM actually reads.
    The header tells the LLM where this came from so it can cite accurately.
    """
    chunk_id: str  # Same ID as the RetrievalChunk
    text: str  # Header + original chunk text
    parent_id: str
    source_filename: str
    section_heading: str
    page_number: int
    element_type: str
    citation_label: str

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "parent_id": self.parent_id,
            "source_filename": self.source_filename,
            "section_heading": self.section_heading,
            "page_number": self.page_number,
            "element_type": self.element_type,
            "citation_label": self.citation_label,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ContextChunk":
        return cls(
            chunk_id=d["chunk_id"],
            text=d["text"],
            parent_id=d["parent_id"],
            source_filename=d["source_filename"],
            section_heading=d["section_heading"],
            page_number=d["page_number"],
            element_type=d["element_type"],
            citation_label=d["citation_label"],
        )


### Retrieval results ###

@dataclass
class RetrievedResult:
    """
    One result from the hybrid retrieval pipeline.
    Carries the retrieval chunk plus its context and parent,
    and the scores from vector and BM25 search.
    """
    retrieval_chunk: RetrievalChunk
    context_chunk: Optional[ContextChunk]
    parent_chunk: Optional[ParentChunk]

    # Scores (0.0 – 1.0, higher = more relevant)
    vector_score: float = 0.0
    bm25_score: float = 0.0
    combined_score: float = 0.0

    @property
    def citation_label(self) -> str:
        if self.context_chunk:
            return self.context_chunk.citation_label
        c = self.retrieval_chunk
        return f"{c.source_filename} — {c.section_heading}, p.{c.page_number}"


###Ingestion result ###

@dataclass
class IndexResult:
    """Summary returned after a document is ingested."""
    file_id: str
    filename: str
    course_id: str
    total_elements: int = 0
    parent_chunks: int = 0
    retrieval_chunks: int = 0
    text_chunks: int = 0
    table_chunks: int = 0
    image_chunks: int = 0
    status: str = "success"  # "success" | "error"
    error: str = ""

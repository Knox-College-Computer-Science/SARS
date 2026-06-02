from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from datetime import datetime
import uuid

from sqlalchemy import (
    Column, String, Integer, Float, Text,
    DateTime, Boolean, ForeignKey, Index, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base

def _array_column(item_type=String, **kwargs):
    if os.getenv("DATABASE_URL", "").startswith("postgresql"):
        from sqlalchemy.dialects.postgresql import ARRAY
        return Column(ARRAY(item_type), default=list, **kwargs)
    return Column(JSON, default=list, **kwargs)

def _vector_column(dimensions=768, **kwargs):
    if os.getenv("DATABASE_URL", "").startswith("postgresql"):
        from pgvector.sqlalchemy import Vector
        return Column(Vector(dimensions), nullable=True, **kwargs)
    return Column(JSON, nullable=True, **kwargs)

def _jsonb_column(**kwargs):
    if os.getenv("DATABASE_URL", "").startswith("postgresql"):
        from sqlalchemy.dialects.postgresql import JSONB
        return Column(JSONB, **kwargs)
    return Column(JSON, **kwargs)

def generate_uuid():
    return str(uuid.uuid4())

### EXTRACTION ###

@dataclass
class ExtractedElement:
    element_type: str          # "text" | "title" | "table" | "image"
    text: str                  # Raw text content
    page_number: int = 0
    section_heading: str = ""  # Most recent Title seen before this element
    formatted_content: str = ""  # For tables: markdown version
    image_bytes: bytes = b""     # For images


### CHUNK DATACLASSES ###

@dataclass
class ParentChunkData:
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
    def from_dict(cls, d: dict) -> ParentChunkData:
        return cls(
            parent_id=d["parent_id"],
            text=d["text"],
            source_filename=d["source_filename"],
            course_id=d["course_id"],
            file_id=d.get("file_id", ""),
            section_heading=d["section_heading"],
            page_number=d["page_number"],
            page_range=tuple(d["page_range"]),
            child_chunk_ids=d.get("child_chunk_ids", []),
            created_at=d.get("created_at", ""),
        )


@dataclass
class RetrievalChunkData:
    file_id: str
    filename: str
    course_id: str
    chunk_id: str
    text: str                   # What gets embedded and searched
    element_type: str           # "text" | "table" | "image"
    page_number: int
    section_heading: str        # Inherited from parent section
    chunk_index: int            # Position within parent section
    source_filename: str
    user_id: str
    parent_id: str              # Links to ParentChunk
    created_at: str = ""
    embedder_version: str = "gemini-embedding-001"

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


### RETRIEVAL RESULTS ###

@dataclass
class RetrievedResult:
    retrieval_chunk: RetrievalChunkData
    parent_chunk: Optional[ParentChunkData]
    context_chunk: Optional[object] = None  # kept for API compatibility
    vector_score: float = 0.0
    bm25_score: float = 0.0
    combined_score: float = 0.0
    rerank_score: float = 0.0

    @property
    def citation_label(self) -> str:
        c = self.retrieval_chunk
        section_part = f" — {c.section_heading}" if c.section_heading else ""
        return f"{c.source_filename}{section_part}, p.{c.page_number} ({c.element_type})"


### INGESTION RESULT ###

@dataclass
class IndexResult:
    file_id: str
    filename: str
    course_id: str
    total_elements: int = 0
    parent_chunks: int = 0
    retrieval_chunks: int = 0
    text_chunks: int = 0
    table_chunks: int = 0
    image_chunks: int = 0
    status: str = "success"  # "success" | "error" | "duplicate"
    error: str = ""


### ORM MODELS ###

class RAGFile(Base):
    __tablename__ = "rag_files"

    id = Column(String, primary_key=True, default=generate_uuid)
    course_id = Column(String, nullable=False, index=True)  # stores school_course_id (Google Classroom ID)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False, default="uploaded")
    labels = _array_column()
    drive_file_id = Column(String(255), nullable=True)
    local_path = Column(String(500), nullable=True)
    md5_hash = Column(String(32), nullable=True, unique=True)
    file_size = Column(Integer, nullable=True)
    indexing_status = Column(String(50), default="pending")
    indexed_at = Column(DateTime, nullable=True)
    quality_assessment = _jsonb_column(nullable=True)
    warnings = _array_column()
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User")
    retrieval_chunks = relationship("RetrievalChunk", back_populates="file", cascade="all, delete-orphan")
    parent_chunks = relationship("ParentChunk", back_populates="file", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "course_id": self.course_id,
            "user_id": self.user_id,
            "filename": self.filename,
            "source_type": self.source_type,
            "drive_file_id": self.drive_file_id,
            "indexing_status": self.indexing_status,
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
            "quality_assessment": self.quality_assessment,
            "warnings": self.warnings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ParentChunk(Base):
    __tablename__ = "parent_chunks"

    id = Column(String, primary_key=True, default=generate_uuid)
    parent_id = Column(String(100), unique=True, nullable=False, index=True)
    course_id = Column(String, nullable=False, index=True)  # stores school_course_id
    file_id = Column(String, ForeignKey("rag_files.id", ondelete="CASCADE"), nullable=False)
    section_heading = Column(String(500), nullable=True)
    page_number = Column(Integer, nullable=True)
    page_range_start = Column(Integer, nullable=True)
    page_range_end = Column(Integer, nullable=True)
    source_filename = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    child_chunk_ids = _array_column()
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    file = relationship("RAGFile", back_populates="parent_chunks")
    retrieval_chunks = relationship("RetrievalChunk", back_populates="parent", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "course_id": self.course_id,
            "file_id": self.file_id,
            "section_heading": self.section_heading,
            "page_number": self.page_number,
            "page_range": [self.page_range_start, self.page_range_end] if self.page_range_start else None,
            "source_filename": self.source_filename,
            "child_chunk_ids": self.child_chunk_ids,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RetrievalChunk(Base):
    __tablename__ = "retrieval_chunks"

    id = Column(String, primary_key=True, default=generate_uuid)
    chunk_id = Column(String(100), unique=True, nullable=False, index=True)
    course_id = Column(String, nullable=False, index=True)  # stores school_course_id
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    file_id = Column(String, ForeignKey("rag_files.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(String, ForeignKey("parent_chunks.parent_id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    element_type = Column(String(50), nullable=False)
    page_number = Column(Integer, nullable=True)
    section_heading = Column(String(500), nullable=True)
    source_filename = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    formatted_content = Column(Text, nullable=True)
    embedding = _vector_column(3072)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    file = relationship("RAGFile", back_populates="retrieval_chunks")
    parent = relationship("ParentChunk", back_populates="retrieval_chunks")

    def to_dict(self):
        return {
            "id": self.id,
            "chunk_id": self.chunk_id,
            "course_id": self.course_id,
            "user_id": self.user_id,
            "file_id": self.file_id,
            "parent_id": self.parent_id,
            "chunk_index": self.chunk_index,
            "element_type": self.element_type,
            "page_number": self.page_number,
            "section_heading": self.section_heading,
            "source_filename": self.source_filename,
            "text": self.text,
            "formatted_content": self.formatted_content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RAGRetrievalLog(Base):
    __tablename__ = "rag_retrieval_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    query = Column(Text, nullable=False)
    query_variants = _array_column()
    retrieval_latency_ms = Column(Float, nullable=True)
    num_results = Column(Integer, default=0)
    confidence_level = Column(String(50), nullable=True)
    hit_at_5 = Column(Boolean, default=False)
    retrieved_chunk_ids = _array_column()
    rerank_scores = _array_column()
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "course_id": self.course_id,
            "user_id": self.user_id,
            "query": self.query,
            "query_variants": self.query_variants,
            "retrieval_latency_ms": self.retrieval_latency_ms,
            "num_results": self.num_results,
            "confidence_level": self.confidence_level,
            "hit_at_5": self.hit_at_5,
            "retrieved_chunk_ids": self.retrieved_chunk_ids,
            "rerank_scores": self.rerank_scores,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UserAcademicProfile(Base):
    __tablename__ = "user_academic_profile"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    declared_major = Column(String(255), nullable=True)
    declared_minor = Column(String(255), nullable=True)
    courses_taken = _array_column()
    interests = _array_column()
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "declared_major": self.declared_major,
            "declared_minor": self.declared_minor,
            "courses_taken": self.courses_taken,
            "interests": self.interests,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

from typing import List, Tuple

import re
import uuid
import logging
from datetime import datetime

import numpy as np

from app.rag.config import (
    CHUNK_MIN_CHARS,
    CHUNK_SEMANTIC_TRIGGER,
    SEMANTIC_BREAKPOINT_PCTILE,
    IMAGE_MIN_CAPTION_CHARS,
)
from app.rag.models import ExtractedElement, ParentChunk, RetrievalChunk

logger = logging.getLogger("sars.rag.chunker")

_NO_TITLE = "Document"


# entry point

def chunk_document(
    elements:  List[ExtractedElement],
    filename:  str,
    file_id:   str,
    course_id: str,
    user_id:   str,
    doc_type:  str = "structured",
) -> Tuple[List[ParentChunk], List[RetrievalChunk]]:

    if doc_type == "unstructured":
        logger.info(f"Using page-based chunking for {filename} (doc_type=unstructured)")
        return _chunk_by_page(elements, filename, file_id, course_id, user_id)

    # doc_type == "structured": section-based parent-child chunking
    # Step 1: Group elements by section (Title boundaries)
    sections = _group_by_section(elements)

    parents:   List[ParentChunk]   = []
    retrieval: List[RetrievalChunk] = []
    global_chunk_index = 0

    for section_heading, section_elements in sections:
        # Step 2: Build ParentChunk for this section
        parent = _make_parent(
            section_heading=section_heading,
            elements=section_elements,
            filename=filename,
            file_id=file_id,
            course_id=course_id,
        )
        parents.append(parent)

        # Step 3: Separate text from atomic elements
        text_elements   = [e for e in section_elements if e.element_type in ("text", "title")]
        atomic_elements = [e for e in section_elements if e.element_type in ("table", "image")]

        # Step 4: Create retrieval chunks from text elements
        text_chunks = _chunk_text_elements(
            elements        = text_elements,
            parent          = parent,
            filename        = filename,
            file_id         = file_id,
            course_id       = course_id,
            user_id         = user_id,
            start_index     = global_chunk_index,
        )
        retrieval.extend(text_chunks)
        global_chunk_index += len(text_chunks)

        # Step 5: Create one retrieval chunk per atomic element
        atomic_chunks = _chunk_atomic_elements(
            elements    = atomic_elements,
            parent      = parent,
            filename    = filename,
            file_id     = file_id,
            course_id   = course_id,
            user_id     = user_id,
            start_index = global_chunk_index,
        )
        retrieval.extend(atomic_chunks)
        global_chunk_index += len(atomic_chunks)

        # Step 6: Update parent with child IDs
        child_ids = [c.chunk_id for c in text_chunks + atomic_chunks]
        parent.child_chunk_ids.extend(child_ids)

    logger.info(
        f"Chunked {filename}: {len(parents)} parents, "
        f"{len(retrieval)} retrieval chunks "
        f"({sum(1 for c in retrieval if c.element_type == 'text')} text, "
        f"{sum(1 for c in retrieval if c.element_type == 'table')} tables, "
        f"{sum(1 for c in retrieval if c.element_type == 'image')} images)"
    )
    return parents, retrieval


# ── Section grouping ────────────────────────────────────────────

def _group_by_section(
    elements: List[ExtractedElement],
) -> List[Tuple[str, List[ExtractedElement]]]:
    """
    Group elements by their parent section (Title boundaries).
    """
    sections: List[Tuple[str, List[ExtractedElement]]] = []
    current_heading = _NO_TITLE
    current_group: List[ExtractedElement] = []

    for elem in elements:
        if elem.element_type == "title":
            # Save the previous group (if non-empty)
            if current_group:
                sections.append((current_heading, current_group))
            current_heading = elem.text
            current_group = []
        else:
            current_group.append(elem)

    if current_group:
        sections.append((current_heading, current_group))

    # If document has no titles at all, we still have one section
    if not sections and elements:
        sections = [(_NO_TITLE, elements)]

    return sections


#  Parent chunk

def _make_parent(
    section_heading: str,
    elements: List[ExtractedElement],
    filename: str,
    file_id: str,
    course_id: str,
) -> ParentChunk:
    """
    Build a ParentChunk from all elements in a section.
    """
    pages     = [e.page_number for e in elements if e.page_number]
    page_min  = min(pages) if pages else 0
    page_max  = max(pages) if pages else 0
    full_text = " ".join(e.text for e in elements if e.text.strip())

    return ParentChunk(
        parent_id       = str(uuid.uuid4()),
        text            = full_text,
        source_filename = filename,
        course_id       = course_id,
        section_heading = section_heading,
        page_number     = page_min,
        page_range      = (page_min, page_max),
        child_chunk_ids = [],
        created_at      = datetime.now().isoformat(),
    )


#  Text chunking

def _chunk_text_elements(
    elements:    List[ExtractedElement],
    parent:      ParentChunk,
    filename:    str,
    file_id:     str,
    course_id:   str,
    user_id:     str,
    start_index: int,
) -> List[RetrievalChunk]:

    if not elements:
        return []

    # Collect paragraphs (merge buffered small ones)
    paragraphs = _merge_small_paragraphs(elements)

    chunks: List[RetrievalChunk] = []
    idx = start_index

    for para_text, page_num in paragraphs:
        if len(para_text) <= CHUNK_SEMANTIC_TRIGGER:
            # Paragraph is a reasonable size — one chunk
            chunks.append(_make_retrieval_chunk(
                text            = para_text,
                element_type    = "text",
                page_number     = page_num,
                section_heading = parent.section_heading,
                chunk_index     = idx,
                filename        = filename,
                file_id         = file_id,
                course_id       = course_id,
                user_id         = user_id,
                parent_id       = parent.parent_id,
            ))
            idx += 1
        else:
            # Paragraph is large — split semantically
            sub_texts = _semantic_split(para_text)
            for sub_text in sub_texts:
                if len(sub_text.strip()) < CHUNK_MIN_CHARS:
                    continue  # Skip remnants below minimum size
                chunks.append(_make_retrieval_chunk(
                    text            = sub_text,
                    element_type    = "text",
                    page_number     = page_num,
                    section_heading = parent.section_heading,
                    chunk_index     = idx,
                    filename        = filename,
                    file_id         = file_id,
                    course_id       = course_id,
                    user_id         = user_id,
                    parent_id       = parent.parent_id,
                ))
                idx += 1

    return chunks


def _merge_small_paragraphs(
    elements: List[ExtractedElement],
) -> List[Tuple[str, int]]:

    result:  List[Tuple[str, int]] = []
    buffer:  List[str]             = []
    buf_page: int                  = 0

    for elem in elements:
        text = elem.text.strip()
        if not text:
            continue

        if len(text) < CHUNK_MIN_CHARS:
            # Too small — add to buffer
            if not buffer:
                buf_page = elem.page_number
            buffer.append(text)
        else:
            # Flush buffer into current element if non-empty
            if buffer:
                combined = " ".join(buffer) + " " + text
                result.append((combined.strip(), buf_page))
                buffer = []
            else:
                result.append((text, elem.page_number))

    # Flush any remaining buffer
    if buffer:
        result.append((" ".join(buffer).strip(), buf_page))

    return result


# ── Semantic splitting ───────────────────────────────────────────

def _semantic_split(text: str) -> List[str]:

    from app.rag.modules.embedder import embed_texts

    sentences = _split_sentences(text)
    if len(sentences) <= 2:
        return [text]   # Too short to bother splitting

    try:
        embeddings = embed_texts(sentences)
    except Exception as e:
        logger.warning(f"Semantic split embedding failed, keeping paragraph whole: {e}")
        return [text]

    # Compute cosine distances between consecutive sentences
    distances = []
    for i in range(len(embeddings) - 1):
        distances.append(_cosine_distance(embeddings[i], embeddings[i + 1]))

    if not distances:
        return [text]

    threshold = float(np.percentile(distances, SEMANTIC_BREAKPOINT_PCTILE))

    # Build groups of sentences separated at breakpoints
    groups: List[List[str]] = [[sentences[0]]]
    for i, dist in enumerate(distances):
        if dist > threshold:
            groups.append([sentences[i + 1]])
        else:
            groups[-1].append(sentences[i + 1])

    return [" ".join(g) for g in groups if g]


def _split_sentences(text: str) -> List[str]:

    # Protect abbreviations
    text = re.sub(
        r"\b(Dr|Mr|Mrs|Ms|Prof|Sr|Jr|e\.g|i\.e|etc|vs|approx|Fig|fig|Eq|eq)\.",
        r"\1<DOT>",
        text,
    )
    # Split on sentence-ending punctuation
    sentences = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    # Restore protected dots and filter tiny fragments
    return [
        s.replace("<DOT>", ".").strip()
        for s in sentences
        if len(s.strip()) > 10
    ]


def _cosine_distance(v1: List[float], v2: List[float]) -> float:
    a, b = np.array(v1), np.array(v2)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 1.0
    return float(1.0 - np.dot(a, b) / norm)


#  Atomic element chunking

def _chunk_atomic_elements(
    elements:    List[ExtractedElement],
    parent:      ParentChunk,
    filename:    str,
    file_id:     str,
    course_id:   str,
    user_id:     str,
    start_index: int,
) -> List[RetrievalChunk]:

    chunks: List[RetrievalChunk] = []
    idx = start_index

    for elem in elements:
        if elem.element_type == "table":
            embed_text = elem.text  # Flat text — good for semantic search
            chunks.append(_make_retrieval_chunk(
                text              = embed_text,
                element_type      = "table",
                page_number       = elem.page_number,
                section_heading   = parent.section_heading,
                chunk_index       = idx,
                filename          = filename,
                file_id           = file_id,
                course_id         = course_id,
                user_id           = user_id,
                parent_id         = parent.parent_id,
                formatted_content = elem.formatted_content,
            ))
            idx += 1

        elif elem.element_type == "image":
            caption = elem.text
            if len(caption) < IMAGE_MIN_CAPTION_CHARS:
                # Caption too short — not useful to index
                logger.debug(f"Skipping image (caption too short): {caption!r}")
                continue
            chunks.append(_make_retrieval_chunk(
                text            = caption,
                element_type    = "image",
                page_number     = elem.page_number,
                section_heading = parent.section_heading,
                chunk_index     = idx,
                filename        = filename,
                file_id         = file_id,
                course_id       = course_id,
                user_id         = user_id,
                parent_id       = parent.parent_id,
            ))
            idx += 1

    return chunks


#  RetrievalChunk

def _make_retrieval_chunk(
    text:              str,
    element_type:      str,
    page_number:       int,
    section_heading:   str,
    chunk_index:       int,
    filename:          str,
    file_id:           str,
    course_id:         str,
    user_id:           str,
    parent_id:         str,
    formatted_content: str = "",
) -> RetrievalChunk:
    return RetrievalChunk(
        chunk_id          = str(uuid.uuid4()),
        text              = text.strip(),
        element_type      = element_type,
        page_number       = page_number,
        section_heading   = section_heading,
        chunk_index       = chunk_index,
        source_filename   = filename,
        file_id           = file_id,
        course_id         = course_id,
        user_id           = user_id,
        parent_id         = parent_id,
        formatted_content = formatted_content,
        created_at        = datetime.now().isoformat(),
        embedder_version  = "nomic-embed-text-v1",
    )

# ── Page-based chunking (for unstructured documents / slides) ───

def _chunk_by_page(
    elements:  List[ExtractedElement],
    filename:  str,
    file_id:   str,
    course_id: str,
    user_id:   str,
) -> Tuple[List[ParentChunk], List[RetrievalChunk]]:

    from itertools import groupby

    parents:   List[ParentChunk]    = []
    retrieval: List[RetrievalChunk] = []
    global_index = 0

    # Group elements by page number
    sorted_elements = sorted(elements, key=lambda e: e.page_number)
    for page_num, page_elements in groupby(sorted_elements, key=lambda e: e.page_number):
        page_elements = list(page_elements)

        # Parent = full text of this page
        full_text = " ".join(e.text for e in page_elements if e.text.strip())
        if not full_text.strip():
            continue

        parent = ParentChunk(
            parent_id       = str(uuid.uuid4()),
            text            = full_text,
            source_filename = filename,
            course_id       = course_id,
            section_heading = f"Page {page_num}",
            page_number     = page_num,
            page_range      = (page_num, page_num),
            child_chunk_ids = [],
            created_at      = datetime.now().isoformat(),
        )
        parents.append(parent)

        # One retrieval chunk per element on this page
        for elem in page_elements:
            if not elem.text.strip():
                continue
            if elem.element_type in _SKIP_TYPES:
                continue

            chunk = _make_retrieval_chunk(
                text              = elem.text,
                element_type      = elem.element_type,
                page_number       = page_num,
                section_heading   = f"Page {page_num}",
                chunk_index       = global_index,
                filename          = filename,
                file_id           = file_id,
                course_id         = course_id,
                user_id           = user_id,
                parent_id         = parent.parent_id,
                formatted_content = getattr(elem, "formatted_content", ""),
            )
            parent.child_chunk_ids.append(chunk.chunk_id)
            retrieval.append(chunk)
            global_index += 1

    return parents, retrieval

# Types to skip in page-based chunking
_SKIP_TYPES = {"title"}  # Titles become section_heading, not separate chunks
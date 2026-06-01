import logging
import re
from typing import List, Tuple

from app.rag.config import (
    CHUNK_MIN_CHARS,
    CHUNK_MAX_CHARS,
    CHUNK_OVERLAP_CHARS,
    SLIDE_MERGE_THRESHOLD,
    QUALITY_TIER_HIGH_MIN_CHARS,
    QUALITY_TIER_HIGH_MIN_DIVERSITY,
    QUALITY_TIER_MEDIUM_MIN_CHARS,
    QUALITY_TIER_MEDIUM_MIN_DIVERSITY,
    QUALITY_TIER_LOW_MIN_CHARS,
)
from app.rag.models import ExtractedElement, ParentChunkData, RetrievalChunkData

logger = logging.getLogger(__name__)


### QUALITY ASSESSMENT ###

def assess_quality(elements: List[ExtractedElement]) -> dict:
    text_elements = [e for e in elements if e.element_type in ("text", "title")]
    if not text_elements:
        return {"tier": "empty", "avg_chars": 0, "diversity": 0.0, "warnings": []}

    avg_chars = sum(len(e.text) for e in text_elements) / len(text_elements)

    all_words = " ".join(e.text.lower() for e in text_elements).split()
    diversity = (
        len(set(all_words)) / len(all_words) if all_words else 0.0
    )

    warnings = []

    if avg_chars >= QUALITY_TIER_HIGH_MIN_CHARS and diversity >= QUALITY_TIER_HIGH_MIN_DIVERSITY:
        tier = "high"
    elif avg_chars >= QUALITY_TIER_MEDIUM_MIN_CHARS and diversity >= QUALITY_TIER_MEDIUM_MIN_DIVERSITY:
        tier = "medium"
        warnings.append("Low text density — retrieval quality may be reduced")
    elif avg_chars >= QUALITY_TIER_LOW_MIN_CHARS:
        tier = "low"
        warnings.append("Very low text density — consider re-uploading a higher quality version")
    else:
        tier = "empty"
        warnings.append("Document appears to contain no extractable text")

    return {
        "tier":      tier,
        "avg_chars": round(avg_chars, 1),
        "diversity": round(diversity, 3),
        "warnings":  warnings,
    }


### SPLITTING ###

def _split_text(text: str, max_chars: int, overlap: int) -> List[str]:
    if len(text) <= max_chars:
        return [text]

    chunks = []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current} {sentence}".strip() if current else sentence
        else:
            if current:
                chunks.append(current)
            if len(sentence) > max_chars:
                for i in range(0, len(sentence), max_chars - overlap):
                    chunks.append(sentence[i : i + max_chars])
                current = ""
            else:
                current = sentence

    if current:
        chunks.append(current)

    return chunks if chunks else [text[:max_chars]]


### PARENT + RETRIEVAL CHUNK BUILDERS ###

def _make_parent(
    elements: List[ExtractedElement],
    file_id: str,
    course_id: str,
    filename: str,
    section_heading: str,
    parent_index: int,
) -> ParentChunkData:
    full_text = "\n\n".join(e.text for e in elements)
    pages = [e.page_number for e in elements if e.page_number]
    page_start = min(pages) if pages else 0
    page_end = max(pages) if pages else 0

    return ParentChunkData(
        parent_id       = f"{file_id}_section_{parent_index}",
        text            = full_text,
        source_filename = filename,
        course_id       = course_id,
        file_id         = file_id,
        section_heading = section_heading,
        page_number     = page_start,
        page_range      = (page_start, page_end),
    )


def _make_retrieval_chunks(
    parent: ParentChunkData,
    elements: List[ExtractedElement],
    file_id: str,
    course_id: str,
    user_id: str,
    filename: str,
    chunk_counter: int,
) -> Tuple[List[RetrievalChunkData], int]:
    chunks: List[RetrievalChunkData] = []

    for elem in elements:
        if elem.element_type in ("table", "image"):
            chunk = RetrievalChunkData(
                chunk_id        = f"{file_id}_chunk_{chunk_counter}",
                text            = elem.text,
                element_type    = elem.element_type,
                page_number     = elem.page_number,
                section_heading = parent.section_heading,
                chunk_index     = len(chunks),
                source_filename = filename,
                filename        = filename,
                file_id         = file_id,
                course_id       = course_id,
                user_id         = user_id,
                parent_id       = parent.parent_id,
                formatted_content = elem.formatted_content,
            )
            chunks.append(chunk)
            chunk_counter += 1

        elif elem.element_type in ("text", "title"):
            splits = _split_text(elem.text, CHUNK_MAX_CHARS, CHUNK_OVERLAP_CHARS)
            for split_text in splits:
                if len(split_text.strip()) < CHUNK_MIN_CHARS:
                    continue
                chunk = RetrievalChunkData(
                    chunk_id        = f"{file_id}_chunk_{chunk_counter}",
                    text            = split_text,
                    element_type    = "text",
                    page_number     = elem.page_number,
                    section_heading = parent.section_heading,
                    chunk_index     = len(chunks),
                    source_filename = filename,
                    filename        = filename,
                    file_id         = file_id,
                    course_id       = course_id,
                    user_id         = user_id,
                    parent_id       = parent.parent_id,
                )
                chunks.append(chunk)
                chunk_counter += 1

    return chunks, chunk_counter


### SLIDE-AWARE GROUPING ###

def _group_slides(elements: List[ExtractedElement]) -> List[List[ExtractedElement]]:
    slides: List[List[ExtractedElement]] = []
    current: List[ExtractedElement] = []

    for elem in elements:
        if elem.element_type == "title" and current:
            slides.append(current)
            current = [elem]
        else:
            current.append(elem)

    if current:
        slides.append(current)

    merged: List[List[ExtractedElement]] = []
    buffer: List[ExtractedElement] = []

    for slide in slides:
        slide_text = " ".join(e.text for e in slide)
        buffer.extend(slide)
        if len(slide_text) >= SLIDE_MERGE_THRESHOLD:
            merged.append(buffer)
            buffer = []

    if buffer:
        merged.append(buffer)

    return merged


### SECTION GROUPING ###

def _group_by_section(elements: List[ExtractedElement]) -> List[List[ExtractedElement]]:
    sections: List[List[ExtractedElement]] = []
    current: List[ExtractedElement] = []

    for elem in elements:
        if elem.element_type == "title" and current:
            sections.append(current)
            current = [elem]
        else:
            current.append(elem)

    if current:
        sections.append(current)

    return sections if sections else [elements]


### PUBLIC API ###

def chunk(
    elements: List[ExtractedElement],
    file_id: str,
    course_id: str,
    user_id: str,
    filename: str,
    is_slides: bool = False,
) -> Tuple[List[ParentChunkData], List[RetrievalChunkData]]:
    if not elements:
        return [], []

    quality = assess_quality(elements)
    if quality["tier"] == "empty":
        logger.warning(f"Empty document: {filename}")
        return [], []

    logger.info(
        f"Chunking {filename} | quality={quality['tier']} "
        f"avg_chars={quality['avg_chars']} diversity={quality['diversity']}"
    )

    groups = _group_slides(elements) if is_slides else _group_by_section(elements)

    parents: List[ParentChunkData] = []
    retrieval_chunks: List[RetrievalChunkData] = []
    chunk_counter = 0

    for i, group in enumerate(groups):
        heading = next(
            (e.text for e in group if e.element_type == "title"),
            f"Section {i + 1}",
        )

        parent = _make_parent(
            elements       = group,
            file_id        = file_id,
            course_id      = course_id,
            filename       = filename,
            section_heading = heading,
            parent_index   = i,
        )

        r_chunks, chunk_counter = _make_retrieval_chunks(
            parent        = parent,
            elements      = group,
            file_id       = file_id,
            course_id     = course_id,
            user_id       = user_id,
            filename      = filename,
            chunk_counter = chunk_counter,
        )

        if not r_chunks:
            continue

        parent.child_chunk_ids = [c.chunk_id for c in r_chunks]
        parents.append(parent)
        retrieval_chunks.extend(r_chunks)

    logger.info(
        f"Produced {len(parents)} parent chunks and "
        f"{len(retrieval_chunks)} retrieval chunks from {filename}"
    )
    return parents, retrieval_chunks
from typing import List, Tuple

import io
import re
import hashlib
import logging
import unicodedata

from app.rag.config import VISION_MODEL, EXTRACT_IMAGES, EXTRACTION_STRATEGY
from app.rag.models import ExtractedElement

logger = logging.getLogger("sars.rag.extractor")

# Element categories from unstructured that we treat as narrative text
_TEXT_CATEGORIES = {
    "NarrativeText",
    "ListItem",
    "UncategorizedText",
    "FigureCaption",
}

# Categories we explicitly skip (noise)
_SKIP_CATEGORIES = {"Header", "Footer", "PageBreak"}


def compute_md5(file_bytes: bytes) -> str:
    """Return MD5 hex digest of file bytes. Used for duplicate detection."""
    return hashlib.md5(file_bytes).hexdigest()


def extract_elements(file_bytes: bytes, filename: str) -> List[ExtractedElement]:

    from unstructured.partition.pdf import partition_pdf

    logger.info(f"Extracting: {filename} (strategy={EXTRACTION_STRATEGY}, images={EXTRACT_IMAGES})")

    try:
        raw_elements = partition_pdf(
            file=io.BytesIO(file_bytes),
            strategy=EXTRACTION_STRATEGY,          # "fast" or "hi_res" (OCR)
            include_page_breaks=True,
            extract_images_in_pdf=EXTRACT_IMAGES,  # controlled by config
        )
    except Exception as e:
        logger.error(f"PDF extraction failed for {filename}: {e}")
        raise ValueError(f"Could not parse {filename}: {e}")

    extracted: List[ExtractedElement] = []
    current_section = ""   # Tracks the most recent Title element

    for elem in raw_elements:
        category = elem.category
        text     = _clean_text(str(elem))
        page_num = getattr(elem.metadata, "page_number", 0) or 0

        if not text:
            continue

        if category in _SKIP_CATEGORIES:
            continue

        if category == "Title":
            current_section = text
            extracted.append(ExtractedElement(
                element_type    = "title",
                text            = text,
                page_number     = page_num,
                section_heading = current_section,
            ))

        elif category == "Table":
            html = getattr(elem.metadata, "text_as_html", "") or ""
            formatted   = _html_table_to_markdown(html) if html else text
            linearized  = _linearize_table(html) if html else text

            extracted.append(ExtractedElement(
                element_type      = "table",
                text              = linearized,
                page_number       = page_num,
                section_heading   = current_section,
                formatted_content = formatted,
            ))

        elif category == "Image":
            if EXTRACT_IMAGES:
                image_b64 = getattr(elem.metadata, "image_base64", None)
                if image_b64:
                    caption = _caption_image_safe(image_b64, filename, page_num)
                    if caption:
                        extracted.append(ExtractedElement(
                            element_type    = "image",
                            text            = caption,
                            page_number     = page_num,
                            section_heading = current_section,
                        ))

        elif category in _TEXT_CATEGORIES:
            if len(text) < 10:
                continue
            extracted.append(ExtractedElement(
                element_type    = "text",
                text            = text,
                page_number     = page_num,
                section_heading = current_section,
            ))

        else:
            if len(text) > 40:
                extracted.append(ExtractedElement(
                    element_type    = "text",
                    text            = text,
                    page_number     = page_num,
                    section_heading = current_section,
                ))

    logger.info(
        f"Extracted {len(extracted)} elements from {filename}: "
        f"{sum(1 for e in extracted if e.element_type == 'text')} text, "
        f"{sum(1 for e in extracted if e.element_type == 'title')} titles, "
        f"{sum(1 for e in extracted if e.element_type == 'table')} tables, "
        f"{sum(1 for e in extracted if e.element_type == 'image')} images"
    )
    return extracted


def detect_document_type(elements: List[ExtractedElement]) -> str:

    if not elements:
        return "unstructured"
    title_count = sum(1 for e in elements if e.element_type == "title")
    ratio = title_count / len(elements)
    doc_type = "structured" if ratio > 0.12 else "unstructured"
    logger.debug(f"Document type detected: {doc_type} (title ratio={ratio:.2f})")
    return doc_type


# ── Private helpers ──────────────────────────────────────────────

def _clean_text(text: str) -> str:

    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _html_table_to_markdown(html: str) -> str:

    try:
        text = html
        text = re.sub(r"</?table[^>]*>", "", text)
        text = re.sub(r"</?thead[^>]*>", "", text)
        text = re.sub(r"</?tbody[^>]*>", "", text)
        text = re.sub(r"</tr>", "\n", text)
        text = re.sub(r"<tr[^>]*>", "| ", text)
        text = re.sub(r"</t[dh]>\s*<t[dh][^>]*>", " | ", text)
        text = re.sub(r"<t[dh][^>]*>", "", text)
        text = re.sub(r"</t[dh]>", " |", text)
        text = re.sub(r"<[^>]+>", "", text)

        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        if len(lines) >= 1:
            col_count = lines[0].count("|") - 1
            if col_count > 0:
                separator = "| " + " | ".join(["---"] * col_count) + " |"
                lines.insert(1, separator)

        return "\n".join(lines)
    except Exception:
        return html


def _linearize_table(html: str) -> str:

    try:
        # Extract all rows
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
        if not rows:
            return _html_table_to_markdown(html)

        # Parse header row
        header_cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", rows[0], re.DOTALL)
        headers = [re.sub(r"<[^>]+>", "", c).strip() for c in header_cells]

        lines = []
        for row_idx, row in enumerate(rows[1:], 1):
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)
            cell_texts = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]

            row_label = cell_texts[0] if cell_texts else f"Row {row_idx}"

            pairs = []
            for col_idx, cell in enumerate(cell_texts[1:], 1):
                if cell and col_idx < len(headers):
                    pairs.append(f"{headers[col_idx]}={cell}")

            if pairs:
                lines.append(f"Row {row_idx} ({row_label}): {' | '.join(pairs)}")

        return "\n".join(lines) if lines else _html_table_to_markdown(html)

    except Exception:
        return _html_table_to_markdown(html)


def _caption_image_safe(image_b64: str, filename: str, page: int) -> str:
    """
    Caption an image using LLaVA via Ollama..

    Retries up to 3 times with exponential backoff before giving up.
    """
    import time
    import base64
    import ollama as _ollama

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            image_bytes = base64.b64decode(image_b64)
            response = _ollama.generate(
                model=VISION_MODEL,
                prompt=(
                    "Describe this image from an academic document. "
                    "Include any text, labels, axes, data values, or diagrams. "
                    "Be factual and concise."
                ),
                images=[image_bytes],
            )
            caption = response.get("response", "").strip()
            if caption:
                logger.debug(f"Captioned image p.{page} of {filename}: {caption[:60]}…")
            return caption

        except Exception as e:
            if attempt < max_attempts - 1:
                wait = 2 ** attempt  # 1s, 2s
                logger.warning(f"Image captioning attempt {attempt+1} failed, retrying in {wait}s: {e}")
                time.sleep(wait)
            else:
                logger.warning(
                    f"Image captioning skipped (p.{page} of {filename}) after {max_attempts} attempts: {e}. "
                    f"Pull llava with: ollama pull llava"
                )
                return ""

    return ""
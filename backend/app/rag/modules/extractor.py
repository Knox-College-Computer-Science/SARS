import io
import re
import logging
import unicodedata

from app.rag.config import VISION_MODEL
from app.rag.models import ExtractedElement

logger = logging.getLogger("nexus.rag.extractor")

# Element categories from unstructured that we treat as narrative text
_TEXT_CATEGORIES = {
    "NarrativeText",
    "ListItem",
    "UncategorizedText",
    "FigureCaption",
}

# Categories we explicitly skip (noise)
_SKIP_CATEGORIES = {"Header", "Footer", "PageBreak"}


def extract_elements(file_bytes: bytes, filename: str) -> list[ExtractedElement]:
    """
    Parse a PDF into typed ExtractedElement objects.

    """
    from unstructured.partition.pdf import partition_pdf

    logger.info(f"Extracting: {filename}")

    try:
        raw_elements = partition_pdf(
            file=io.BytesIO(file_bytes),
            strategy="fast",
            include_page_breaks=True,
            # extract_images_in_pdf=True,  # Enable when LLaVA is stable
        )
    except Exception as e:
        logger.error(f"PDF extraction failed for {filename}: {e}")
        raise ValueError(f"Could not parse {filename}: {e}")

    extracted: list[ExtractedElement] = []
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
            # Update running section heading
            current_section = text
            # Titles are indexed too — they often contain key terminology
            extracted.append(ExtractedElement(
                element_type    = "title",
                text            = text,
                page_number     = page_num,
                section_heading = current_section,
            ))

        elif category == "Table":
            # Build a markdown representation from the HTML unstructured provides
            html = getattr(elem.metadata, "text_as_html", "") or ""
            formatted = _html_table_to_markdown(html) if html else text

            extracted.append(ExtractedElement(
                element_type      = "table",
                text              = text,        # Flat text for embedding
                page_number       = page_num,
                section_heading   = current_section,
                formatted_content = formatted,   # Markdown for LLM
            ))

        elif category == "Image":
            # Attempt LLaVA captioning; fall back gracefully if unavailable
            image_b64 = getattr(elem.metadata, "image_base64", None)
            if image_b64:
                caption = _caption_image_safe(image_b64, filename, page_num)
                if caption:
                    extracted.append(ExtractedElement(
                        element_type    = "image",
                        text            = caption,   # Caption becomes the searchable text
                        page_number     = page_num,
                        section_heading = current_section,
                    ))
            # If no image data or captioning failed, skip silently

        elif category in _TEXT_CATEGORIES:
            if len(text) < 10:  # Skip tiny fragments
                continue
            extracted.append(ExtractedElement(
                element_type    = "text",
                text            = text,
                page_number     = page_num,
                section_heading = current_section,
            ))

        else:
            # Catch-all: index as text if substantial
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


# ── Helpers ─────────────────────────────────────────────────────

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
        return html   # Fallback: return raw HTML


def _caption_image_safe(
    image_b64: str, filename: str, page: int
) -> str:
    """
    Caption an image using LLaVA via Ollama.
.
    """
    try:
        import base64
        import ollama as _ollama

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
            logger.debug(
                f"Captioned image p.{page} of {filename}: {caption[:60]}…"
            )
        return caption
    except Exception as e:
        logger.warning(
            f"Image captioning skipped (p.{page} of {filename}): {e}. "
            f"Pull llava with: ollama pull llava"
        )
        return ""
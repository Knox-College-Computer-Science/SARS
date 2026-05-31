import hashlib
import json
import logging
from pathlib import Path
from typing import List, Optional

import google.generativeai as genai

from app.rag.config import (
    GOOGLE_API_KEY,
    IMAGE_CAPTION_ENABLED,
    IMAGE_CAPTION_MODEL,
    PARSE_RESULT_CACHE_ENABLED,
    PARSE_CACHE_DIR,
)
from app.rag.models import ExtractedElement

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md"}

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)


### CACHE ###

def _cache_path(md5: str) -> Path:
    return PARSE_CACHE_DIR / f"{md5}.json"


def _load_cache(md5: str) -> Optional[List[dict]]:
    path = _cache_path(md5)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _save_cache(md5: str, elements: List[dict]) -> None:
    try:
        _cache_path(md5).write_text(
            json.dumps(elements, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")


### IMAGE CAPTIONING ###

def _caption_image(image_bytes: bytes, context: str = "") -> str:
    if not GOOGLE_API_KEY or not image_bytes:
        return "[Image: caption unavailable]"
    try:
        model = genai.GenerativeModel(IMAGE_CAPTION_MODEL)
        prompt = (
            "Describe this image precisely for academic retrieval. "
            "List all visible text exactly as written. "
            "Identify all labels, axes, column headers, and row labels. "
            "State the type of figure (diagram, chart, table, equation, photo). "
            f"Context from surrounding text: {context[:300] if context else 'none'}."
        )
        response = model.generate_content([
            {"mime_type": "image/png", "data": image_bytes},
            prompt,
        ])
        return response.text.strip()
    except Exception as e:
        logger.warning(f"Image captioning failed: {e}")
        return "[Image: caption failed]"


### DOCLING EXTRACTION ###

def _extract_with_docling(file_bytes: bytes, filename: str) -> List[ExtractedElement]:
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        import tempfile, os

        pipeline_opts = PdfPipelineOptions(
            do_table_structure=True,
            do_ocr=True,
        )

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)
            }
        )

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=Path(filename).suffix
        ) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            result = converter.convert(tmp_path)
        finally:
            os.unlink(tmp_path)

        elements: List[ExtractedElement] = []
        current_heading = ""

        for item, _ in result.document.iterate_items():
            label = getattr(item, "label", "text")
            text = getattr(item, "text", "").strip()
            page = (
                getattr(getattr(item, "prov", [None])[0], "page", 0)
                if getattr(item, "prov", None)
                else 0
            )

            if not text:
                continue

            if label in ("section_header", "title"):
                current_heading = text
                elements.append(ExtractedElement(
                    element_type    = "title",
                    text            = text,
                    page_number     = page,
                    section_heading = current_heading,
                ))

            elif label == "table":
                md_table = getattr(item, "export_to_markdown", lambda: text)()
                elements.append(ExtractedElement(
                    element_type      = "table",
                    text              = md_table,
                    page_number       = page,
                    section_heading   = current_heading,
                    formatted_content = md_table,
                ))

            elif label == "picture":
                if IMAGE_CAPTION_ENABLED:
                    img_bytes = getattr(item, "image_bytes", b"")
                    caption = _caption_image(img_bytes, current_heading)
                    elements.append(ExtractedElement(
                        element_type    = "image",
                        text            = caption,
                        page_number     = page,
                        section_heading = current_heading,
                        image_bytes     = img_bytes,
                    ))

            else:
                elements.append(ExtractedElement(
                    element_type    = "text",
                    text            = text,
                    page_number     = page,
                    section_heading = current_heading,
                ))

        return elements

    except ImportError:
        logger.warning("Docling not installed, falling back to plain text extraction")
        return _extract_plain_text(file_bytes, filename)
    except Exception as e:
        logger.error(f"Docling extraction failed for {filename}: {e}")
        raise


def _extract_plain_text(file_bytes: bytes, filename: str) -> List[ExtractedElement]:
    ext = Path(filename).suffix.lower()
    if ext in (".txt", ".md"):
        text = file_bytes.decode("utf-8", errors="replace")
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return [
            ExtractedElement(element_type="text", text=p, page_number=i + 1)
            for i, p in enumerate(paragraphs)
        ]
    return [ExtractedElement(
        element_type = "text",
        text         = file_bytes.decode("utf-8", errors="replace"),
        page_number  = 1,
    )]


### PUBLIC API ###

def extract(file_bytes: bytes, filename: str) -> List[ExtractedElement]:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    md5 = hashlib.md5(file_bytes).hexdigest()

    if PARSE_RESULT_CACHE_ENABLED:
        cached = _load_cache(md5)
        if cached:
            logger.info(f"Cache hit for {filename} ({md5[:8]})")
            return [ExtractedElement(**e) for e in cached]

    logger.info(f"Extracting {filename} ({len(file_bytes):,} bytes)")
    elements = _extract_with_docling(file_bytes, filename)

    if PARSE_RESULT_CACHE_ENABLED:
        serializable = [
            {k: v for k, v in e.__dict__.items() if k != "image_bytes"}
            for e in elements
        ]
        _save_cache(md5, serializable)

    logger.info(f"Extracted {len(elements)} elements from {filename}")
    return elements


def compute_md5(file_bytes: bytes) -> str:
    return hashlib.md5(file_bytes).hexdigest()
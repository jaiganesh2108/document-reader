from pathlib import Path
import pymupdf


def read_pdf(file_path):
    """
    Extracts text content page-by-page from a PDF document.
    Handles empty pages gracefully while preserving page numbering.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    pages = []
    with pymupdf.open(str(path)) as document:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            
            # Preserve page even if empty, with helpful placeholder
            display_text = text if text else "(No readable text detected on this page)"
            pages.append({
                "number": page_number,
                "text": display_text,
                "is_empty": not bool(text)
            })

    return pages

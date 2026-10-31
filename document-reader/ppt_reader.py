from pathlib import Path
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


def extract_shape_text(shape):
    """
    Recursively extracts text from presentation shapes, group shapes, and tables.
    """
    parts = []

    # Handle grouped shapes
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for child in shape.shapes:
            parts.extend(extract_shape_text(child))
        return parts

    # Handle text frame
    if shape.has_text_frame:
        text = shape.text.strip()
        if text:
            parts.append(text)

    # Handle tables
    if shape.has_table:
        for row in shape.table.rows:
            cells = [
                cell.text.strip()
                for cell in row.cells
                if cell.text.strip()
            ]
            if cells:
                parts.append(" | ".join(cells))

    return parts


def read_ppt(file_path):
    """
    Extracts text content slide-by-slide from a PowerPoint (.pptx) file.
    Handles empty slides gracefully while maintaining continuous slide numbering.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PowerPoint file not found: {file_path}")

    presentation = Presentation(str(path))
    slides = []

    for slide_number, slide in enumerate(presentation.slides, start=1):
        parts = []

        for shape in slide.shapes:
            parts.extend(extract_shape_text(shape))

        text = "\n".join(parts).strip()
        display_text = text if text else "(No readable text detected on this slide)"

        slides.append({
            "number": slide_number,
            "text": display_text,
            "is_empty": not bool(text)
        })

    return slides

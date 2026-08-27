import io

import pdfplumber
import pypdfium2 as pdfium
import pytesseract

from . import ExtractedPage


def extract_pdf(file_bytes: bytes) -> list[ExtractedPage]:
    pages: list[ExtractedPage] = []

    pdf = pdfium.PdfDocument(file_bytes)

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as plumber_pdf:
            for index, pdf_page in enumerate(pdf, start=1):
                text_page = pdf_page.get_textpage()
                text = text_page.get_text_range().strip()

                metadata = {
                    "page_number": index,
                    "ocr_required": len(text) < 50,
                }

                if len(text) < 50:
                    bitmap = pdf_page.render(scale=2)
                    image = bitmap.to_pil()
                    text = pytesseract.image_to_string(
                        image,
                        config="--psm 6",
                    ).strip()

                    pages.append(
                        ExtractedPage(
                            page_number=index,
                            content=text,
                            content_type="text",
                            metadata=metadata,
                        )
                    )
                else:
                    pages.append(
                        ExtractedPage(
                            page_number=index,
                            content=text,
                            content_type="text",
                            metadata=metadata,
                        )
                    )

                plumber_page = plumber_pdf.pages[index - 1]

                tables = plumber_page.extract_tables()

                for table_index, table in enumerate(tables, start=1):
                    if not table:
                        continue

                    rows = []
                    for row in table:
                        cells = [
                            "" if cell is None else str(cell)
                            for cell in row
                        ]
                        rows.append("| " + " | ".join(cells) + " |")

                    if not rows:
                        continue

                    column_count = len(table[0]) if table[0] else 0

                    if column_count:
                        separator = (
                            "| "
                            + " | ".join(["---"] * column_count)
                            + " |"
                        )

                        markdown = (
                            rows[0]
                            + "\n"
                            + separator
                            + "\n"
                            + "\n".join(rows[1:])
                        )
                    else:
                        markdown = "\n".join(rows)

                    pages.append(
                        ExtractedPage(
                            page_number=index,
                            content=markdown,
                            content_type="table",
                            metadata={
                                "page_number": index,
                                "table_index": table_index,
                            },
                        )
                    )

                text_page.close()
                pdf_page.close()

    finally:
        pdf.close()

    return pages
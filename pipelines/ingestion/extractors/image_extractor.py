import base64
import io

from PIL import Image
import pytesseract

from providers.base import ChatMessage
from . import ExtractedPage


async def extract_image(
    file_bytes: bytes,
    provider,
) -> list[ExtractedPage]:
    image = Image.open(io.BytesIO(file_bytes))
    image = image.convert("RGB")

    image.thumbnail((1024, 1024))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)

    image_data = base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")

    ocr_text = pytesseract.image_to_string(image).strip()

    message = ChatMessage(
        role="user",
        content=[
            {
                "type": "text",
                "text": (
                    "Describe this image in detail, including "
                    "objects, layout, visible text, and important "
                    "visual information."
                ),
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": (
                        f"data:image/jpeg;base64,{image_data}"
                    )
                },
            },
        ],
    )

    result = await provider.complete([message])

    description = result.content.strip()

    content = (
        description
        + "\n\nText found in image: "
        + ocr_text
    )

    return [
        ExtractedPage(
            page_number=1,
            content=content,
            content_type="image_description",
            metadata={
                "source_type": "image",
                "width": image.width,
                "height": image.height,
                "ocr_text": bool(ocr_text),
            },
        )
    ]
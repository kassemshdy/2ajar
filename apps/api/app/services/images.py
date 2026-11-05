"""Image validation & normalization. Content is sniffed, never trusted by extension or client MIME."""

import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps

from app.core.errors import ValidationFailed

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PIXELS = 40_000_000  # ~ 8000x5000
MAX_EDGE = 2048
MIN_EDGE = 200


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    content_type: str
    width: int
    height: int


def process_image(raw: bytes) -> ProcessedImage:
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(raw)) as probe:
                fmt = probe.format
                if fmt not in ALLOWED_FORMATS:
                    raise ValidationFailed("Only JPEG, PNG or WebP images are allowed")
                if probe.width * probe.height > MAX_PIXELS:
                    raise ValidationFailed("Image dimensions are too large")
                probe.verify()
            with Image.open(io.BytesIO(raw)) as src:
                src.load()
                img: Image.Image = ImageOps.exif_transpose(src) or src
                if min(img.size) < MIN_EDGE:
                    raise ValidationFailed(f"Image must be at least {MIN_EDGE}px on each side")
                img = img.convert("RGB")
                img.thumbnail((MAX_EDGE, MAX_EDGE))
                out = io.BytesIO()
                # Re-encoding drops EXIF/GPS metadata and any appended payload.
                img.save(out, format="WEBP", quality=82, method=4)
                return ProcessedImage(out.getvalue(), "image/webp", img.width, img.height)
        except ValidationFailed:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ValidationFailed("Image dimensions are too large") from exc
        except Exception as exc:
            raise ValidationFailed("File is not a valid image") from exc

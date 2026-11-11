import warnings
from io import BytesIO
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models.fields.files import ImageFieldFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 20_000_000


def prepare_image(upload: ImageFieldFile) -> tuple[ContentFile, ContentFile]:
    if upload.size > MAX_BYTES:
        raise ValidationError("Image must be no larger than 5 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            upload.seek(0)
            with Image.open(upload) as original:
                if original.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValidationError("Only JPEG, PNG and WebP images are allowed.")
                if original.width * original.height > MAX_PIXELS:
                    raise ValidationError("Image dimensions are too large.")
                original.load()
                picture = ImageOps.exif_transpose(original).convert("RGB")
        picture.thumbnail((1600, 1600))
        main = BytesIO()
        picture.save(main, "WEBP", quality=85)
        picture.thumbnail((400, 400))
        thumb = BytesIO()
        picture.save(thumb, "WEBP", quality=80)
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValidationError("Invalid image.") from exc
    key = uuid4().hex
    return ContentFile(main.getvalue(), name=f"{key}.webp"), ContentFile(
        thumb.getvalue(), name=f"{key}-thumb.webp"
    )

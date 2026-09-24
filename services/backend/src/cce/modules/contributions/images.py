from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from cce.modules.contributions.repository import ContributionError

MAX_AVATAR_BYTES = 524288


@dataclass(frozen=True)
class VerifiedImage:
    content: bytes
    sha256: str
    width: int
    height: int


def verify_image(content: bytes, content_type: str) -> VerifiedImage:
    if not content or len(content) > MAX_AVATAR_BYTES:
        raise ContributionError(413, "Avatar en fazla 512 KiB olabilir")
    formats = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
    if content_type not in formats:
        raise ContributionError(415, "Yalnız PNG, JPEG veya WebP kabul edilir")
    try:
        with Image.open(BytesIO(content), formats=[formats[content_type]]) as source:
            if not (32 <= source.width <= 2048 and 32 <= source.height <= 2048):
                raise ContributionError(422, "Avatar boyutları 32–2048 piksel olmalı")
            if getattr(source, "n_frames", 1) != 1:
                raise ContributionError(422, "Animasyonlu avatar kabul edilmez")
            source.load()
            oriented = ImageOps.exif_transpose(source).convert("RGBA")
            # Copy pixels into a fresh image so EXIF/ICC/text/trailing payloads are not retained.
            clean = Image.new("RGBA", oriented.size)
            clean.paste(oriented)
            output = BytesIO()
            clean.save(output, format="PNG")
            normalized = output.getvalue()
            if len(normalized) > MAX_AVATAR_BYTES:
                raise ContributionError(413, "Doğrulanmış PNG 512 KiB sınırını aşıyor")
            return VerifiedImage(
                normalized, sha256(normalized).hexdigest(), clean.width, clean.height
            )
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ContributionError(422, "Avatar içeriği doğrulanamadı") from None

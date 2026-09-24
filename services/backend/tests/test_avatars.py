from io import BytesIO

import pytest
from PIL import Image, PngImagePlugin

from cce.modules.contributions.images import MAX_AVATAR_BYTES, verify_image
from cce.modules.contributions.repository import ContributionError


def png() -> bytes:
    output = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private-note", "Must be stripped")
    Image.new("RGB", (64, 64), "blue").save(output, format="PNG", pnginfo=metadata)
    return output.getvalue()


def test_image_is_decoded_and_metadata_is_removed() -> None:
    result = verify_image(png() + b"<script>ignored trailing data</script>", "image/png")
    assert result.width == result.height == 64
    with Image.open(BytesIO(result.content)) as image:
        assert image.format == "PNG" and image.info == {}
    assert b"script" not in result.content


@pytest.mark.parametrize(
    "content,mime,status",
    [
        (b"<svg></svg>", "image/svg+xml", 415),
        (b"<html></html>", "image/png", 422),
        (b"x" * (MAX_AVATAR_BYTES + 1), "image/png", 413),
        (png(), "image/jpeg", 422),
    ],
    ids=["svg", "invalid-bytes", "oversized", "mismatched-type"],
)
def test_invalid_images_rejected(content: bytes, mime: str, status: int) -> None:
    with pytest.raises(ContributionError) as error:
        verify_image(content, mime)
    assert error.value.status == status


def test_dimensions_and_animation_are_bounded() -> None:
    output = BytesIO()
    Image.new("RGB", (2049, 32)).save(output, format="PNG")
    with pytest.raises(ContributionError):
        verify_image(output.getvalue(), "image/png")
    output = BytesIO()
    Image.new("RGB", (64, 64), "red").save(
        output,
        format="PNG",
        save_all=True,
        append_images=[Image.new("RGB", (64, 64), "blue")],
        duration=100,
    )
    with pytest.raises(ContributionError):
        verify_image(output.getvalue(), "image/png")

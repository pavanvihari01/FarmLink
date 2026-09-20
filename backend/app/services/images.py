"""Image sniffing.

The upload endpoint already validates the declared content type. This checks
the actual bytes, so a file named `.jpg` that is really an HTML document, a zip,
or a shell script is rejected rather than stored and later served back.

This is a signature check, not a decode. A file with valid JPEG magic bytes
followed by arbitrary data passes. Decoding would need Pillow, which is not a
dependency, and for images served as static files the practical risk of a
signature-correct-but-invalid image is low.
"""

# Longest-first so a shorter prefix cannot shadow a longer one.
_SIGNATURES: list[tuple[bytes, str]] = [
    (b'\x89PNG\r\n\x1a\n', 'image/png'),
    (b'\xff\xd8\xff', 'image/jpeg'),
]

# WebP is RIFF-framed, so the type marker sits at an offset rather than the
# start. Checked separately.
_RIFF = b'RIFF'
_WEBP = b'WEBP'

def sniff_image_type(data: bytes) -> str | None:
    """The image type the bytes actually are, or None if they are not an image.

    Returns one of 'image/jpeg', 'image/png', 'image/webp'.
    """
    if not data:
        return None

    if data[:4] == _RIFF and len(data) >= 12 and data[8:12] == _WEBP:
        return 'image/webp'

    for signature, mime in _SIGNATURES:
        if data.startswith(signature):
            return mime

    return None

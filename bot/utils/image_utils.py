import base64
import io
from PIL import Image


def compress_image(image_bytes: bytes, max_size_mb: int = 10, quality: int = 85) -> bytes:
    """Compress image to fit within max size"""
    img = Image.open(io.BytesIO(image_bytes))

    # Convert to RGB if necessary (for PNG with transparency)
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background

    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality, optimize=True)

    # Reduce quality if still too large
    while output.tell() > max_size_mb * 1024 * 1024 and quality > 20:
        quality -= 10
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)

    return output.getvalue()


def image_to_base64(image_bytes: bytes) -> str:
    """Convert image bytes to base64 string"""
    return base64.b64encode(image_bytes).decode('utf-8')


def base64_to_image(base64_string: str) -> bytes:
    """Convert base64 string to image bytes"""
    return base64.b64decode(base64_string)


def resize_for_telegram(image_bytes: bytes, max_dimension: int = 2000) -> bytes:
    """Resize image for Telegram (max 2000px on largest side)"""
    img = Image.open(io.BytesIO(image_bytes))

    # Check if resize needed
    if max(img.size) <= max_dimension:
        return image_bytes

    # Calculate new size maintaining aspect ratio
    ratio = max_dimension / max(img.size)
    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))

    img = img.resize(new_size, Image.Resampling.LANCZOS)

    output = io.BytesIO()

    # Preserve format
    if img.mode == 'RGBA':
        img.save(output, format='PNG')
    else:
        img.save(output, format='JPEG', quality=90)

    return output.getvalue()


def resize_for_marketplace(image_bytes: bytes, width: int = 900, height: int = 1200) -> bytes:
    """Resize image to marketplace dimensions (WB/Ozon 3:4 ratio)"""
    img = Image.open(io.BytesIO(image_bytes))

    # Convert to RGB if needed
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        if img.mode == 'RGBA':
            background.paste(img, mask=img.split()[-1])
        else:
            background.paste(img)
        img = background

    # Resize to target dimensions
    img = img.resize((width, height), Image.Resampling.LANCZOS)

    output = io.BytesIO()
    img.save(output, format='JPEG', quality=95)

    return output.getvalue()


def get_image_dimensions(image_bytes: bytes) -> tuple[int, int]:
    """Get image width and height"""
    img = Image.open(io.BytesIO(image_bytes))
    return img.size


def convert_to_png(image_bytes: bytes) -> bytes:
    """Convert image to PNG format (for transparency support)"""
    img = Image.open(io.BytesIO(image_bytes))

    # Convert to RGBA if not already
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    output = io.BytesIO()
    img.save(output, format='PNG')

    return output.getvalue()

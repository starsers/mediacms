"""
Watermark download view — adds WAIC logo + date watermark to images and PDFs.
Triggered when ?dl=1 is appended to media file URL.
"""

import io
import os
from datetime import date

from django.conf import settings
from django.http import HttpResponse, Http404, FileResponse
from PIL import Image, ImageDraw, ImageFont

WATERMARK_TEXT = "WAIC"
LOGO_PATH = os.path.join(settings.BASE_DIR, "static", "images", "waic-logo-original.png")

# Image extensions that get watermarked
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'}
PDF_EXT = '.pdf'


def _find_font(size=24):
    """Find a suitable TrueType font, falling back to default."""
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def _add_watermark_to_image(img_bytes: bytes, ext: str) -> bytes:
    """Add WAIC white watermark to an image, return watermarked bytes."""
    img = Image.open(io.BytesIO(img_bytes))

    # Handle RGBA/P mode
    if img.mode in ('RGBA', 'P', 'LA'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background

    if img.mode != 'RGB':
        img = img.convert('RGB')

    w, h = img.size
    today = date.today().strftime('%Y-%m-%d')

    # --- Prepare WAIC logo as white semi-transparent ---
    logo = None
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert('RGBA')
            logo_w = min(int(w * 0.18), 220)
            logo_h = int(logo.height * (logo_w / logo.width))
            logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
            # Convert colored logo to white: use alpha as mask, fill white
            r, g, b, a = logo.split()
            white_logo = Image.new('RGBA', logo.size, (255, 255, 255, 0))
            white_logo.putalpha(a)  # Keep original alpha shape
            # Reduce overall opacity
            data = list(white_logo.getdata())
            data = [(255, 255, 255, min(p[3], 140)) for p in data]
            white_logo.putdata(data)
            logo = white_logo
        except Exception:
            logo = None

    # --- Draw white text ---
    font = _find_font(size=max(14, min(40, w // 40)))
    text = f"{WATERMARK_TEXT} · {today}"
    tmp_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    bbox = tmp_draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    margin = max(24, w // 50)
    gap = 12

    # Layout: logo (if available) on top, text below
    if logo:
        total_w = max(logo.width, tw)
        total_h = logo.height + gap + th
    else:
        total_w = tw
        total_h = th

    x = w - total_w - margin
    y = h - total_h - margin

    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))

    # Logo
    if logo:
        logo_x = x + (total_w - logo.width) // 2
        overlay.paste(logo, (logo_x, y), logo)
        text_y = y + logo.height + gap
    else:
        text_y = y

    # Text — white, semi-transparent
    overlay_draw = ImageDraw.Draw(overlay)
    text_x = x + (total_w - tw) // 2
    overlay_draw.text((text_x, text_y - 1), text, fill=(255, 255, 255, 160), font=font)

    # Composite
    img = Image.alpha_composite(img.convert('RGBA'), overlay)
    img = img.convert('RGB')

    # Save to bytes
    out = io.BytesIO()
    fmt = 'JPEG' if ext.lower() in ('.jpg', '.jpeg') else 'PNG'
    img.save(out, format=fmt, quality=92)
    return out.getvalue()


def _add_watermark_to_pdf(pdf_bytes: bytes) -> bytes:
    """Add WAIC watermark text to every page of a PDF."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    today = date.today().strftime('%Y-%m-%d')
    text = f"WAIC · {today}"

    for page in doc:
        rect = page.rect
        # Bottom-right corner
        fontsize = max(10, min(24, rect.width / 40))
        tw = fitz.get_text_length(text, fontname='helv', fontsize=fontsize)
        margin = 30

        x = rect.width - tw - margin - 10
        y = rect.height - margin - 5

        # Background rectangle
        shape = page.new_shape()
        shape.draw_rect(
            fitz.Rect(x - 8, y - fontsize - 4, x + tw + 8, y + 6)
        )
        shape.finish(fill=(0, 0, 0, 0.55), color=None)

        # Text
        page.insert_text(
            fitz.Point(x, y),
            text,
            fontname='helv',
            fontsize=fontsize,
            color=(1, 1, 1),
        )

    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def watermark_download(request, path):
    """
    Serve media file. With ?dl=1, adds WAIC watermark to images and PDFs.
    Without ?dl=1, serves the original file unchanged (passthrough).
    """
    ext = os.path.splitext(path)[1].lower()
    file_path = os.path.join(settings.MEDIA_ROOT, path)

    if not os.path.exists(file_path):
        raise Http404("File not found")

    # Passthrough: no watermark for normal browsing
    if request.GET.get('dl') != '1':
        from django.views.static import serve
        return serve(request, path, document_root=settings.MEDIA_ROOT)

    with open(file_path, 'rb') as f:
        raw = f.read()

    if ext in IMAGE_EXTS:
        try:
            watermarked = _add_watermark_to_image(raw, ext)
        except Exception:
            # Fallback: return original if watermarking fails
            watermarked = raw
        content_type = f'image/{ext[1:] if ext != ".jpg" else "jpeg"}'
    elif ext == PDF_EXT:
        try:
            watermarked = _add_watermark_to_pdf(raw)
        except Exception:
            watermarked = raw
        content_type = 'application/pdf'
    else:
        # Non-image/PDF: return original
        watermarked = raw
        # Guess content type
        from mimetypes import guess_type
        content_type = guess_type(path)[0] or 'application/octet-stream'

    filename = os.path.basename(path)
    response = HttpResponse(watermarked, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Content-Length'] = len(watermarked)
    return response

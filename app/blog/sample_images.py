from io import BytesIO

from django.core.files.base import ContentFile

from PIL import Image, ImageDraw


IMAGE_PALETTES = (
    ("#dce9e1", "#356b52", "#202321"),
    ("#e7e0d5", "#8a5a35", "#202321"),
    ("#dce4ed", "#3f6385", "#202321"),
    ("#eadfe7", "#80536f", "#202321"),
    ("#e8e6cf", "#77713b", "#202321"),
)


def build_seed_png(key, title, palette_index):
    background, accent, ink = IMAGE_PALETTES[
        palette_index % len(IMAGE_PALETTES)
    ]
    image = Image.new("RGB", (1200, 720), background)
    draw = ImageDraw.Draw(image)
    offset = sum(key.encode("utf-8")) % 180
    draw.ellipse((90 + offset, 90, 450 + offset, 450), fill=accent)
    draw.rectangle(
        (560, 180 + offset // 3, 1080, 540 + offset // 3),
        outline=ink,
        width=18,
    )
    draw.line((120, 610, 1080, 610), fill=ink, width=10)
    draw.text((120, 640), title[:72], fill=ink)
    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    return ContentFile(
        output.getvalue(),
        name=f"blog-seed-{key}.png",
    )

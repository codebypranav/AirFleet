from functools import lru_cache
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from . import airports

SIZE = WIDTH, HEIGHT = 1080, 1350
MARGIN = 88
FONT = Path(__file__).parent / 'data' / 'Geist-Regular.ttf'
INK, BONE, STONE, FERN = '#11120f', '#ebe7da', '#b7b3a5', '#a8bb82'


def render(flight):
    card = _background(flight.photo) or Image.new('RGB', SIZE, INK)
    draw = ImageDraw.Draw(card)
    width = WIDTH - 2 * MARGIN

    draw.text((MARGIN, MARGIN), 'AirFleet', font=_font(44), fill=BONE, anchor='lt', stroke_width=1, stroke_fill=BONE)

    y = HEIGHT - MARGIN
    draw.text((MARGIN, y), f'@{flight.user.username}', font=_font(40), fill=BONE, anchor='ls')
    draw.text((WIDTH - MARGIN, y), urlparse(settings.FRONTEND_URL).netloc, font=_font(30), fill=STONE, anchor='rs')

    hours, minutes = divmod(int(flight.total_time.total_seconds()) // 60, 60)
    aircraft = ' · '.join(filter(None, [flight.registration_number, flight.aircraft.type_code if flight.aircraft else '']))
    details = f'{flight.departure_time.day} {flight.departure_time:%b %Y}  ·  {aircraft}  ·  {hours}h {minutes:02d}m'
    y -= 110
    draw.text((MARGIN, y), _fit(draw, details, _font(34), width), font=_font(34), fill=STONE, anchor='ls')

    y -= 16
    names = [getattr(airports.get(code), 'name', code) for code in (flight.departure_airport, flight.arrival_airport)]
    for name in reversed(names if names[0] != names[1] else names[:1]):
        y -= 56
        draw.text((MARGIN, y), _fit(draw, name, _font(34), width), font=_font(34), fill=BONE, anchor='ls')

    y -= 80
    route = f'{flight.departure_airport} → {flight.arrival_airport}'
    size = next(s for s in range(140, 40, -10) if draw.textlength(route, font=_font(s)) + 4 <= width)
    draw.text((MARGIN, y), route, font=_font(size), fill=BONE, anchor='ls', stroke_width=2, stroke_fill=BONE)

    if flight.milestone:
        y -= 170
        for line in reversed(_wrap(draw, flight.get_milestone_display(), _font(80), width)):
            draw.text((MARGIN, y), line, font=_font(80), fill=FERN, anchor='ls', stroke_width=1, stroke_fill=FERN)
            y -= 96

    out = BytesIO()
    card.save(out, 'PNG')
    return out.getvalue()


def _background(photo):
    if not photo:
        return None
    try:
        with photo.open('rb') as f:
            image = Image.open(f)
            image.draft('RGB', SIZE)
            image = ImageOps.exif_transpose(image).convert('RGB')
    except Exception:
        return None
    return ImageEnhance.Brightness(ImageOps.fit(image, SIZE, Image.Resampling.LANCZOS)).enhance(0.4)


@lru_cache
def _font(size):
    return ImageFont.truetype(FONT, size)


def _fit(draw, text, font, width):
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + '…', font=font) > width:
        text = text[:-1]
    return text.rstrip() + '…'


def _wrap(draw, text, font, width):
    lines = ['']
    for word in text.split():
        candidate = f'{lines[-1]} {word}'.strip()
        if draw.textlength(candidate, font=font) <= width or not lines[-1]:
            lines[-1] = candidate
        else:
            lines.append(word)
    return lines

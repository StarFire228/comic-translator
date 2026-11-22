"""Рисует нейтральную демо-страницу комикса на английском (для README и постов)."""
import math
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = str(ROOT / 'mit' / 'fonts' / 'anime_ace_3.ttf')
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'app' / 'demo_en.png'

W, H = 1200, 1700
M, G = 40, 24                       # поля страницы и промежуток между панелями
INK = (25, 25, 35)
page = Image.new('RGB', (W, H), (250, 248, 242))


def gradient(size, top, bottom):
    w, h = size
    img = Image.new('RGB', size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        d.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return img


def cloud(d, x, y, s):
    for dx, dy, r in [(0, 0, 1.0), (0.9, -0.3, 1.2), (1.9, 0, 0.95), (1, 0.35, 1.0)]:
        rr = r * s
        d.ellipse((x + dx * s - rr, y + dy * s - rr, x + dx * s + rr, y + dy * s + rr), fill=(255, 255, 255))


def robot(d, cx, base, s=1.0, arm_up=False, holding=None):
    """Круглый дружелюбный робот; base — линия ног."""
    body = (cx - 70 * s, base - 190 * s, cx + 70 * s, base - 60 * s)
    head = (cx - 60 * s, base - 300 * s, cx + 60 * s, base - 195 * s)
    # ноги
    for lx in (-35, 35):
        d.rounded_rectangle((cx + (lx - 15) * s, base - 65 * s, cx + (lx + 15) * s, base), 8, fill=(120, 130, 150), outline=INK, width=4)
    # руки
    left = [(cx - 70 * s, base - 160 * s), (cx - 120 * s, base - 110 * s)]
    right = [(cx + 70 * s, base - 160 * s), (cx + 125 * s, base - (230 if arm_up else 110) * s)]
    for a in (left, right):
        d.line(a, fill=INK, width=int(18 * s))
        d.line(a, fill=(160, 170, 190), width=int(10 * s))
        x, y = a[1]
        d.ellipse((x - 14 * s, y - 14 * s, x + 14 * s, y + 14 * s), fill=(160, 170, 190), outline=INK, width=4)
    d.rounded_rectangle(body, int(30 * s), fill=(90, 160, 230), outline=INK, width=5)
    d.ellipse((cx - 22 * s, base - 140 * s, cx + 22 * s, base - 96 * s), fill=(255, 210, 80), outline=INK, width=4)
    d.rounded_rectangle(head, int(36 * s), fill=(200, 210, 225), outline=INK, width=5)
    d.rounded_rectangle((cx - 45 * s, base - 275 * s, cx + 45 * s, base - 220 * s), int(20 * s), fill=(40, 50, 70))
    for ex in (-20, 20):
        d.ellipse((cx + (ex - 9) * s, base - 258 * s, cx + (ex + 9) * s, base - 240 * s), fill=(110, 240, 255))
    d.line((cx, base - 300 * s, cx, base - 335 * s), fill=INK, width=5)
    d.ellipse((cx - 11 * s, base - 350 * s, cx + 11 * s, base - 328 * s), fill=(255, 90, 90), outline=INK, width=4)
    if holding == 'bottle':
        x, y = right[1]
        bottle(d, x + 10 * s, y - 10 * s, s)


def bottle(d, x, y, s=1.0):
    d.rounded_rectangle((x - 18 * s, y - 40 * s, x + 18 * s, y + 40 * s), int(14 * s), fill=(150, 220, 190), outline=INK, width=4)
    d.rectangle((x - 8 * s, y - 62 * s, x + 8 * s, y - 40 * s), fill=(150, 220, 190), outline=INK, width=4)
    d.rectangle((x - 9 * s, y - 72 * s, x + 9 * s, y - 60 * s), fill=(170, 120, 70), outline=INK, width=3)
    d.rounded_rectangle((x - 9 * s, y - 25 * s, x + 9 * s, y + 25 * s), 4, fill=(245, 235, 200), outline=INK, width=2)


def cat(d, cx, base, s=1.0, surprised=False):
    body = (cx - 75 * s, base - 120 * s, cx + 75 * s, base)
    d.ellipse(body, fill=(245, 160, 70), outline=INK, width=5)
    d.arc((cx + 40 * s, base - 120 * s, cx + 150 * s, base - 10 * s), 200, 330, fill=INK, width=int(16 * s))
    d.arc((cx + 40 * s, base - 120 * s, cx + 150 * s, base - 10 * s), 200, 330, fill=(245, 160, 70), width=int(8 * s))
    head = (cx - 70 * s, base - 235 * s, cx + 70 * s, base - 100 * s)
    for side in (-1, 1):
        d.polygon([(cx + side * 62 * s, base - 190 * s), (cx + side * 58 * s, base - 265 * s), (cx + side * 18 * s, base - 225 * s)],
                  fill=(245, 160, 70), outline=INK, width=5)
    d.ellipse(head, fill=(245, 160, 70), outline=INK, width=5)
    for ex in (-28, 28):
        if surprised:
            d.ellipse((cx + (ex - 14) * s, base - 190 * s, cx + (ex + 14) * s, base - 160 * s), fill='white', outline=INK, width=4)
            d.ellipse((cx + (ex - 6) * s, base - 181 * s, cx + (ex + 6) * s, base - 169 * s), fill=INK)
        else:
            d.ellipse((cx + (ex - 10) * s, base - 185 * s, cx + (ex + 10) * s, base - 163 * s), fill=INK)
            d.ellipse((cx + (ex - 3) * s, base - 182 * s, cx + (ex + 3) * s, base - 176 * s), fill='white')
    d.polygon([(cx - 8 * s, base - 150 * s), (cx + 8 * s, base - 150 * s), (cx, base - 141 * s)], fill=(230, 90, 110))
    if surprised:
        d.ellipse((cx - 9 * s, base - 136 * s, cx + 9 * s, base - 118 * s), fill=(120, 40, 50), outline=INK, width=3)
    else:
        d.arc((cx - 16 * s, base - 150 * s, cx, base - 130 * s), 0, 180, fill=INK, width=3)
        d.arc((cx, base - 150 * s, cx + 16 * s, base - 130 * s), 0, 180, fill=INK, width=3)
    for side in (-1, 1):
        for dy in (-6, 6):
            d.line((cx + side * 30 * s, base - 140 * s + dy * s, cx + side * 85 * s, base - 145 * s + dy * 2 * s), fill=INK, width=2)


def wrap(text, font, max_w, d):
    words, lines, cur = text.split(), [], ''
    for w_ in words:
        test = (cur + ' ' + w_).strip()
        if d.textlength(test, font=font) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w_
    lines.append(cur)
    return lines


def bubble(d, box, text, tail, size=24):
    x1, y1, x2, y2 = box
    font = ImageFont.truetype(FONT, size)
    lines = wrap(text, font, (x2 - x1) * 0.78, d)
    lh = int(size * 1.3)
    # хвостик
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    tx, ty = tail
    ang = math.atan2(ty - cy, tx - cx)
    px, py = -math.sin(ang) * 22, math.cos(ang) * 22
    base1 = (cx + math.cos(ang) * (x2 - x1) * 0.3 + px, cy + math.sin(ang) * (y2 - y1) * 0.3 + py)
    base2 = (cx + math.cos(ang) * (x2 - x1) * 0.3 - px, cy + math.sin(ang) * (y2 - y1) * 0.3 - py)
    # сначала хвостик с обводкой, сверху облачко: его заливка прячет основание хвостика
    d.polygon([base1, base2, tail], fill='white', outline=INK, width=5)
    d.ellipse(box, fill='white', outline=INK, width=5)
    y = cy - lh * len(lines) / 2 + 2
    for line in lines:
        d.text((cx, y), line, font=font, fill=INK, anchor='mt')
        y += lh


def caption(d, box, text, size=22):
    d.rectangle(box, fill=(255, 236, 150), outline=INK, width=4)
    font = ImageFont.truetype(FONT, size)
    lines = wrap(text, font, box[2] - box[0] - 30, d)
    y = box[1] + 14
    for line in lines:
        d.text((box[0] + 16, y), line, font=font, fill=INK)
        y += int(size * 1.3)


def panel(box, bg):
    x1, y1, x2, y2 = box
    page.paste(bg.resize((x2 - x1, y2 - y1)), (x1, y1))
    return ImageDraw.Draw(page)


def border(box):
    ImageDraw.Draw(page).rectangle(box, outline=INK, width=6)


# --- панель 1: пляж, робот нашёл бутылку ---
p1 = (M, M, W - M, 620)
d = panel(p1, gradient((10, 10), (120, 200, 255), (210, 240, 255)))
d.ellipse((900, 90, 1010, 200), fill=(255, 220, 90))
cloud(d, 180, 150, 40); cloud(d, 620, 110, 30)
d.rectangle((M, 430, W - M, 500), fill=(70, 150, 220))
d.rectangle((M, 500, W - M, 620), fill=(240, 215, 160))
for x in range(80, W - M, 140):
    d.arc((x, 420, x + 90, 450), 200, 340, fill=(230, 245, 255), width=4)
robot(d, 360, 600, 0.85, arm_up=True, holding='bottle')
cat(d, 880, 600, 0.9)
caption(d, (M + 20, M + 20, 560, 120), 'Meanwhile, at the edge of the city...')
bubble(d, (500, 170, 860, 340), 'Hey, Whiskers! Look what I found on the beach!', (420, 330))
border(p1)

# --- панель 2: кот удивлён ---
p2 = (M, 620 + G, 590, 1130)
d = panel(p2, gradient((10, 10), (255, 225, 190), (255, 245, 225)))
d.rectangle((M, 1030, 590, 1130), fill=(240, 215, 160))
cat(d, 330, 1110, 1.1, surprised=True)
bubble(d, (70, 670, 560, 860), 'Is that... a message in a bottle? Who still writes letters these days?', (300, 880), size=22)
border(p2)

# --- панель 3: робот читает записку ---
p3 = (590 + G, 620 + G, W - M, 1130)
d = panel(p3, gradient((10, 10), (40, 50, 110), (120, 90, 160)))
for sx, sy in [(660, 700), (760, 760), (1080, 690), (980, 820), (700, 880), (1110, 900)]:
    d.ellipse((sx - 3, sy - 3, sx + 3, sy + 3), fill='white')
robot(d, 860, 1110, 0.9)
d.rounded_rectangle((900, 880, 1060, 990), 6, fill=(245, 235, 200), outline=INK, width=4)
for ly in range(900, 980, 16):
    d.line((915, ly, 1045, ly), fill=(150, 130, 100), width=3)
bubble(d, (640, 670, 1130, 860), 'It says: "If you can read this, the treasure is under the old lighthouse."', (820, 870), size=21)
border(p3)

# --- панель 4: маяк, отправляются в путь ---
p4 = (M, 1130 + G, W - M, H - M)
d = panel(p4, gradient((10, 10), (255, 170, 120), (255, 225, 170)))
d.polygon([(900, 1600), (960, 1240), (1010, 1240), (1070, 1600)], fill=(245, 245, 245), outline=INK, width=5)
for yy in (1330, 1430, 1530):
    d.rectangle((900 + (1600 - yy) * 0.17, yy, 1070 - (1600 - yy) * 0.17, yy + 40), fill=(220, 70, 70))
d.rectangle((945, 1200, 1025, 1245), fill=(255, 230, 120), outline=INK, width=5)
d.rectangle((M, 1600, W - M, H - M), fill=(120, 170, 90))
robot(d, 260, 1640, 0.8, arm_up=True)
cat(d, 520, 1640, 0.85)
bubble(d, (420, 1190, 850, 1370), "Grab a shovel, buddy. We're going on an adventure!", (520, 1440), size=23)
sfx = ImageFont.truetype(FONT, 64)
d.text((80, 1190), 'WHOOSH!', font=sfx, fill=(255, 255, 255), stroke_width=6, stroke_fill=INK)
border(p4)

OUT.parent.mkdir(parents=True, exist_ok=True)
page.save(OUT)
print(OUT)

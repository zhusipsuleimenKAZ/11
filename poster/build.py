"""Сборка постера «Олимпиада по хирургии» (A3) в SVG/HTML.

    python3 build.py   -> poster.svg / poster.html (A3 в обрез),
                          poster_bleed.svg / poster_bleed.html (с вылетами 3 мм)
    node render.js     -> PDF и PNG 300 dpi

Макет в единицах 1000 x 1414 (A3, 1 ед. = 0.297 мм). Палитра — строго 4 цвета.
Весь текст переводится в кривые.
"""
import math
import os
import random

import hands
from geom import BORD, RED, WHITE, INK, f, catmull, poly_d, rot
from typeset import Font, text_path, inside

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1000, 1414
M = 50                      # поле
B = 3 / 0.297               # вылеты под обрез: 3 мм
random.seed(7)

FT = 'FiraSansExtraCondensed-Black.ttf'   # заголовок, дата, подписи
FC = 'FiraSansCondensed-Medium.ttf'      # подзаголовок
FX = 'FiraSansExtraCondensed-Bold.ttf'    # факты
CAP = Font(FT).cap


def text(x, y, s, font, size, fill=WHITE, anchor='start', ls=0.0, extra=''):
    d, w, _ = text_path(font, s, size, x, y, anchor, ls)
    return f'<path d="{d}" fill="{fill}" {extra}/>'


def tw(font, s, size, ls=0.0):
    return Font(font).width(s, size, ls)


def circle_d(x, y, r):
    return f'M{f(x - r)},{f(y)}a{f(r)},{f(r)} 0 1,0 {f(2 * r)},0a{f(r)},{f(r)} 0 1,0 {f(-2 * r)},0'


def halftone(fn, bbox, step, angle, color, rmax, extra=''):
    """Полутоновый растр: fn(x, y) -> 0..1 — доля радиуса точки."""
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    R = math.hypot(x1 - x0, y1 - y0) / 2 + step
    ds = []
    n = int(R / step) + 1
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = rot((cx + i * step, cy + j * step), angle, (cx, cy))
            if not (x0 - step <= x <= x1 + step and y0 - step <= y <= y1 + step):
                continue
            v = fn(x, y)
            if v <= 0.08:
                continue
            ds.append(circle_d(x, y, rmax * min(v, 1)))
    return f'<path d="{"".join(ds)}" fill="{color}" {extra}/>'


def recolor(svg, color=INK):
    """Фрагмент одним цветом — для жёсткой тени."""
    for c in (BORD, RED, WHITE):
        svg = svg.replace(f'"{c}"', f'"{color}"')
    return svg


# ------------------------------------------------------------------ сетка

LOGO_R = 56
LOGO_CY = M + LOGO_R
CIRCLE_C, CIRCLE_R = (500, 312), 224

TITLE_W = W - 2 * M
T1, T2 = 'ОЛИМПИАДА', 'ПО ХИРУРГИИ'
TITLE_TOP = 568
FS1 = TITLE_W / Font(FT).width(T1, 1)
FS2 = TITLE_W / Font(FT).width(T2, 1)
Y_T1 = TITLE_TOP + FS1 * CAP           # базовые линии строк заголовка
Y_T2 = Y_T1 + 20 + FS2 * CAP

SUB = 'Внутривузовская студенческая олимпиада имени профессора А.П. Кошеля'
SUB_FS = TITLE_W / Font(FC).width(SUB, 1)
Y_SUB = Y_T2 + 36 + SUB_FS * Font(FC).cap

DATE = '6–8 НОЯБРЯ 2026'
DATE_FS = 100
PLATE_PAD = 24
PLATE_Y, PLATE_H = Y_SUB + 30, 92
DATE_W = tw(FT, DATE, DATE_FS)

FACT_Y = PLATE_Y + PLATE_H + 34          # верх строки фактов
FACT_FS, FACT_LH = 25, 29
FACTS = [
    ['3 тура · 11 конкурсов'],
    ['Команда из 3 человек:', 'оператор, ассистент, медсестра'],
    ['Новоанатомический корпус', 'СибГМУ, Томск'],
]

BAND_Y = FACT_Y + 2 * FACT_LH + 28
QR = 160
QR_CX = [W / 2 - 300, W / 2, W / 2 + 300]
QR_Y = BAND_Y + 36
QR_LABELS = ['РЕГИСТРАЦИЯ', 'ГРУППА ВКОНТАКТЕ', 'ПРОГРАММА И РЕГЛАМЕНТ']
URL = 'vk.ru/surgery_olympiad_sibmed'

# положение рук: (x, y, угол, масштаб, зеркально)
HAND1 = (446, 352, -57, 1.32, False)    # скальпель, сверху справа
HAND2 = (606, 300, -22, 1.32, True)     # иглодержатель, снизу слева


def place(p, spec):
    x, y, ang, sc, mirror = spec
    px, py = p
    if mirror:
        px = -px
    q = rot((px * sc, py * sc), ang)
    return (x + q[0], y + q[1])


def tr(spec):
    x, y, ang, sc, mirror = spec
    m = ' scale(-1,1)' if mirror else ''
    return f'translate({f(x)},{f(y)}) rotate({f(ang)}){m} scale({f(sc)})'


# ------------------------------------------------------------------ слои

def background():
    s = f'<rect x="{f(-B)}" y="{f(-B)}" width="{f(W + 2 * B)}" height="{f(H + 2 * B)}" fill="{BORD}"/>'

    def edge(x, y):   # тёмный полутон, сгущающийся к краям листа
        d = min(x, W - x, y) / 250
        return 0.6 - d
    s += halftone(edge, (-B, -B, W + B, BAND_Y), 13, 45, INK, 4.4)
    return s


def lamp():
    """Алый круг-«операционная лампа» с полутоном и резцовыми штрихами."""
    cx, cy = CIRCLE_C
    R = CIRCLE_R
    s = f'<circle cx="{cx}" cy="{cy}" r="{R + 14}" fill="{INK}"/>'
    s += f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="{RED}"/>'
    s += f'<clipPath id="lampclip"><circle cx="{cx}" cy="{cy}" r="{R}"/></clipPath>'

    def shade(x, y):
        return (y - (cy + R * 0.05)) / (R * 0.95) * 1.05
    s += halftone(shade, (cx - R, cy - R, cx + R, cy + R), 11, 45, BORD, 5.6, 'clip-path="url(#lampclip)"')
    s += (f'<circle cx="{cx}" cy="{cy}" r="{R - 20}" fill="none" stroke="{WHITE}" stroke-width="3" '
          f'stroke-dasharray="46 14 8 14"/>')
    for k in range(44):
        a = math.radians(k * 360 / 44 + 3)
        r0 = R + 26 + (k % 3) * 4
        r1 = r0 + 18 + (k * 7 % 5) * 5
        s += (f'<line x1="{f(cx + r0 * math.cos(a))}" y1="{f(cy + r0 * math.sin(a))}" '
              f'x2="{f(cx + r1 * math.cos(a))}" y2="{f(cy + r1 * math.sin(a))}" stroke="{RED}" '
              f'stroke-width="4" stroke-linecap="round"/>')
    return s


def logos():
    return ''.join(f'<circle cx="{cx}" cy="{LOGO_CY}" r="{LOGO_R}" fill="{WHITE}"/>'
                   for cx in (M + LOGO_R, W - M - LOGO_R))


def illustration():
    s = ''
    for spec, h in ((HAND2, hands.hand_holder()), (HAND1, hands.hand_scalpel())):
        s += f'<g transform="translate(9,11)"><g transform="{tr(spec)}">{recolor(h)}</g></g>'
        s += f'<g transform="{tr(spec)}">{h}</g>'
    return s


# ------------------------------------------------------------------ заголовок и нить

def title_shapes():
    d1, _, _, p1 = text_path(FT, T1, 0, M, Y_T1, width=TITLE_W, glyph_polys=True)
    d2, _, _, p2 = text_path(FT, T2, 0, M, Y_T2, width=TITLE_W, glyph_polys=True)
    return d1 + d2, p1 + p2


def title(d):
    return (f'<path d="{d}" fill="{INK}" transform="translate(7,8)"/>'
            f'<path d="{d}" fill="{WHITE}"/>')


THREAD_X = 27                              # вертикальный шов по левому полю
STITCH = (QR_CX[0] - QR / 2 - 36, QR_Y + QR / 2)  # крестообразный стежок у первого QR
STITCH_A = 15


def thread_path():
    eye = place(hands.needle_pts()[0], HAND2)
    x0 = THREAD_X
    ctrl = [eye, (eye[0] + 18, eye[1] + 64), (740, 480), (800, 548),
            (640, 640), (400, 720), (170, 800), (60, 850), (x0, 910),
            (x0, 1000), (x0, BAND_Y + 10), (x0 + 2, STITCH[1] - 60),
            (STITCH[0] - STITCH_A - 16, STITCH[1] - STITCH_A - 10), (STITCH[0] - STITCH_A, STITCH[1] - STITCH_A)]
    pts, _ = catmull(ctrl, n=28)
    return pts


def thread_stroke(pts, w=7):
    d = poly_d(pts, False)
    return (f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="{f(w + 5)}" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="{d}" fill="none" stroke="{WHITE}" stroke-width="{f(w)}" stroke-linecap="round" stroke-linejoin="round"/>')


def thread_layers(polys):
    """Нить: слой под буквами, куски поверх букв (через одну) и кусок поверх тёмной полосы."""
    pts = thread_path()
    top = [p for p in pts if p[1] <= BAND_Y + 12]
    low = [p for p in pts if p[1] >= BAND_Y - 12]
    under = thread_stroke(top)
    owner = []
    for p in top:
        k = None
        for gi, contours in enumerate(polys):
            if inside(p, contours):
                k = gi
                break
        owner.append(k)
    crossed = []
    for k in owner:
        if k is not None and (not crossed or crossed[-1] != k):
            crossed.append(k)
    over_set = {k for i, k in enumerate(crossed) if i % 2 == 0}
    over, run = '', []
    for i, (p, k) in enumerate(zip(top, owner)):
        if k in over_set:
            if not run and i > 0:
                run.append(top[i - 1])
            run.append(p)
        else:
            if run:
                run.append(p)
                over += thread_stroke(run)
            run = []
    if run:
        over += thread_stroke(run)
    # на тёмной полосе контур нити не нужен — только белая линия (без засечки на стыке)
    low_d = poly_d(low, False)
    low_svg = (f'<path d="{low_d}" fill="none" stroke="{WHITE}" stroke-width="7" '
               f'stroke-linecap="round" stroke-linejoin="round"/>')
    return under, over, low_svg


def punctures():
    """Проколы: нить проходит сквозь плашку с датой."""
    s = ''
    for y in (PLATE_Y + 5, PLATE_Y + PLATE_H - 5):
        s += f'<ellipse cx="{THREAD_X}" cy="{f(y)}" rx="6" ry="4" fill="{INK}"/>'
    return s


def knot():
    """Финальный крестообразный стежок у первого QR: нить уходит в прокол и выходит крестом."""
    cx, cy = STITCH
    a = STITCH_A
    s = thread_stroke([(cx + a, cy - a), (cx - a, cy + a)])
    s += thread_stroke([(cx - a, cy - a), (cx + a, cy + a)])
    for dx, dy in ((-a, -a), (a, -a), (-a, a), (a, a)):
        s += f'<circle cx="{f(cx + dx * 1.15)}" cy="{f(cy + dy * 1.15)}" r="3.6" fill="{INK}"/>'
    return s


# ------------------------------------------------------------------ текстовые блоки

def subtitle():
    return text(M, Y_SUB, SUB, FC, SUB_FS)


def date_block():
    s = ''
    pr = M + DATE_W + PLATE_PAD           # правый край плашки; слева — под обрез
    s += f'<rect x="{f(-B)}" y="{f(PLATE_Y + 9)}" width="{f(pr + 8 + B)}" height="{PLATE_H}" fill="{INK}"/>'
    s += f'<rect x="{f(-B)}" y="{f(PLATE_Y)}" width="{f(pr + B)}" height="{PLATE_H}" fill="{RED}"/>'
    s += text(M, PLATE_Y + PLATE_H / 2 + DATE_FS * CAP / 2, DATE, FT, DATE_FS)
    # стикер «Регистрация открыта»
    bx0 = pr + 22
    bw = W - M - bx0 + 4
    bh = 108
    bcx, bcy = bx0 + bw / 2, PLATE_Y + PLATE_H / 2 - 6
    l1, l2 = 'РЕГИСТРАЦИЯ', 'ОТКРЫТА'
    fs = (bw - 34) / tw(FT, l1, 1)
    g = f'<rect x="{f(-bw / 2 + 7)}" y="{f(-bh / 2 + 8)}" width="{f(bw)}" height="{bh}" rx="14" fill="{INK}"/>'
    g += f'<rect x="{f(-bw / 2)}" y="{f(-bh / 2)}" width="{f(bw)}" height="{bh}" rx="14" fill="{WHITE}"/>'
    g += (f'<rect x="{f(-bw / 2 + 7)}" y="{f(-bh / 2 + 7)}" width="{f(bw - 14)}" height="{bh - 14}" rx="9" '
          f'fill="none" stroke="{RED}" stroke-width="2.5" stroke-dasharray="7 6"/>')
    lh = fs * 1.0
    g += text(0, -lh / 2 + fs * CAP / 2 - 2, l1, FT, fs, RED, 'middle')
    g += text(0, lh / 2 + fs * CAP / 2 - 2, l2, FT, fs, RED, 'middle')
    s += f'<g transform="translate({f(bcx)},{f(bcy)}) rotate(-7)">{g}</g>'
    return s


def facts():
    s = ''
    widths = [max(tw(FX, l, FACT_FS) for l in col) for col in FACTS]
    gap = ((W - 2 * M) - sum(widths)) / 4     # отступ по обе стороны от разделителя
    x = M
    cap = Font(FX).cap * FACT_FS
    for i, (col, w) in enumerate(zip(FACTS, widths)):
        y0 = FACT_Y + cap + (FACT_LH / 2 if len(col) == 1 else 0)
        for k, l in enumerate(col):
            s += text(x, y0 + k * FACT_LH, l, FX, FACT_FS)
        x += w
        if i < 2:
            x += gap
            s += (f'<line x1="{f(x)}" y1="{f(FACT_Y - 6)}" x2="{f(x)}" y2="{f(FACT_Y + FACT_LH + cap + 8)}" '
                  f'stroke="{WHITE}" stroke-width="1.6"/>')
            x += gap
    return s


def band():
    s = ''
    pts = [(-B, BAND_Y)]
    x = -B
    while x < W + B:   # рваный «вырезанный» край
        x += random.uniform(14, 34)
        pts.append((min(x, W + B), BAND_Y + random.uniform(-3.5, 3.5)))
    pts += [(W + B, H + B), (-B, H + B)]
    s += f'<path d="{poly_d(pts)}" fill="{INK}"/>'
    s += halftone(lambda x, y: 1 - (y - BAND_Y) / 34, (-B, BAND_Y - 4, W + B, BAND_Y + 40), 9, 45, BORD, 4.4)
    for cx, label in zip(QR_CX, QR_LABELS):
        s += f'<rect x="{f(cx - QR / 2)}" y="{f(QR_Y)}" width="{QR}" height="{QR}" rx="16" fill="{WHITE}"/>'
        s += text(cx, QR_Y + QR + 33, label, FT, 25, WHITE, 'middle', 0.02)
    s += text(W / 2, H - 22, URL, FC, 20, WHITE, 'middle', 0.02)
    return s


def build():
    tdat, polys = title_shapes()
    under, over, low = thread_layers(polys)
    body = ''.join([
        background(),
        lamp(),
        illustration(),
        under,
        title(tdat),
        over,
        subtitle(),
        date_block(),
        punctures(),
        facts(),
        band(),
        low,
        knot(),
        logos(),
    ])
    write('poster', body, 0)
    write('poster_bleed', body, B)


def write(name, body, bleed):
    """SVG и HTML-обёртка для печати; bleed — вылеты в единицах макета."""
    mm = lambda v: f'{v * 0.297:.2f}mm'
    vb = f'{f(-bleed)} {f(-bleed)} {f(W + 2 * bleed)} {f(H + 2 * bleed)}'
    w, h = mm(W + 2 * bleed), mm(H + 2 * bleed)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="{w}" height="{h}">'
           f'<title>Олимпиада по хирургии — постер A3</title>{body}</svg>')
    open(os.path.join(HERE, name + '.svg'), 'w').write(svg)
    html = ('<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Олимпиада по хирургии — постер A3</title>'
            f'<style>@page{{size:{w} {h};margin:0}}html,body{{margin:0;padding:0;background:{BORD}}}'
            f'svg{{display:block;width:{w};height:{h}}}</style></head><body>' + svg + '</body></html>')
    open(os.path.join(HERE, name + '.html'), 'w').write(html)


if __name__ == '__main__':
    build()
    print('FS1 %.1f FS2 %.1f  T1 %.0f T2 %.0f SUB %.0f PLATE %.0f FACT %.0f BAND %.0f QR %.0f' % (
        FS1, FS2, Y_T1, Y_T2, Y_SUB, PLATE_Y, FACT_Y, BAND_Y, QR_Y))

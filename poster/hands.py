"""Кисти в хирургических перчатках и инструменты (скальпель, иглодержатель).

Каждая функция возвращает SVG-фрагмент в локальных координатах; на макет
он ставится через transform. Стиль — линогравюра: толстый чёрный контур,
белые «прорезы»-блики, чёрная штриховка в тени.
"""
import math
import re
from geom import (BORD, WHITE, INK, f, tube_outline, offset_line, smooth_d,
                  poly_d, catmull, rot, ellipse_pts)

OW = 5.0  # толщина контура


_ids = [0]


def _bbox(d):
    nums = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', d)]
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def glove_halftone(ds, step=6.2, rmax=2.5):
    """Полутон в тени перчатки: точки растут к нижней (ладонной) стороне силуэта."""
    _ids[0] += 1
    cid = f'gl{_ids[0]}'
    x0, y0, x1, y1 = (min(v) if i < 2 else max(v) for i, v in enumerate(zip(*[_bbox(d) for d in ds])))
    h = y1 - y0
    dots = []
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    n = int(max(x1 - x0, h) / step) + 2
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = rot((cx + i * step, cy + j * step), 45, (cx, cy))
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                continue
            v = (y - (y0 + 0.42 * h)) / (0.58 * h)
            if v <= 0.1:
                continue
            r = rmax * min(v, 1)
            dots.append(f'M{f(x - r)},{f(y)}a{f(r)},{f(r)} 0 1,0 {f(2 * r)},0a{f(r)},{f(r)} 0 1,0 {f(-2 * r)},0')
    if not dots:
        return ''
    clip = ''.join(f'<path d="{d}"/>' for d in ds)
    return f'<clipPath id="{cid}">{clip}</clipPath><path d="{"".join(dots)}" fill="{INK}" clip-path="url(#{cid})"/>'


def merged(ds, fill=BORD, ow=OW):
    """Несколько фигур, слитых в один силуэт: сначала все контуры, затем заливки."""
    s = ''.join(f'<path d="{d}" fill="{INK}" stroke="{INK}" stroke-width="{f(2 * ow)}" stroke-linejoin="round"/>' for d in ds)
    s += ''.join(f'<path d="{d}" fill="{fill}"/>' for d in ds)
    if fill == BORD and ow == OW:
        s += glove_halftone(ds)
    return s


def line(points, color=WHITE, w=3.5, cap='round'):
    return (f'<path d="{poly_d(points, False)}" fill="none" stroke="{color}" stroke-width="{f(w)}" '
            f'stroke-linecap="{cap}" stroke-linejoin="round"/>')


def sline(points, color=WHITE, w=3.5, n=10):
    pts, _ = catmull(points, n=n)
    return line(pts, color, w)


class Finger:
    def __init__(self, pts, ws, light=None):
        self.pts, self.ws = pts, ws
        if light is None:  # освещена сторона, нормаль которой смотрит вверх (-y)
            from geom import normals
            p, _ = catmull(pts, n=10)
            ns = normals(p)
            light = 1 if sum(n[1] for n in ns) < 0 else -1
        self.light = light

    def d(self):
        return poly_d(tube_outline(self.pts, self.ws))

    def deco(self, t0=0.12, t1=0.86, hatch=True):
        s = ''
        # белый «прорез» вдоль освещённой стороны
        hl = offset_line(self.pts, self.ws, self.light, 6.5, t0, t1)
        s += line(hl, WHITE, 3.6)
        # штриховка в тени
        if hatch:
            sh = offset_line(self.pts, self.ws, -self.light, 0, 0.2, 0.9)
            inner = offset_line(self.pts, self.ws, -self.light, 9, 0.2, 0.9)
            step = max(1, len(sh) // 7)
            for i in range(0, len(sh), step):
                s += line([sh[i], inner[i]], INK, 2.6)
        return s


def crease(c, ang, length, color=INK, w=3):
    a = math.radians(ang)
    dx, dy = math.cos(a) * length / 2, math.sin(a) * length / 2
    return line([(c[0] - dx, c[1] - dy), (c[0] + dx, c[1] + dy)], color, w)


# ---------------------------------------------------------------- инструменты

def scalpel(length=330):
    """Скальпель вдоль +x: остриё в (0,0), рукоятка уходит вправо."""
    s = ''
    # рукоятка
    hx0, hx1 = 62, length
    handle = [(hx0, -6.5), (hx1 - 8, -8.5), (hx1, -4), (hx1, 4), (hx1 - 8, 8.5), (hx0, 6.5)]
    s += merged([poly_d(handle)], WHITE, 4)
    # насечки рукоятки
    for x in range(int(hx0) + 120, int(hx1) - 30, 9):
        s += line([(x, -5), (x + 4, 5)], INK, 2.4, 'butt')
    s += line([(hx0 + 8, -1.5), (hx0 + 100, -1.5)], INK, 2.2)
    # лезвие №10: брюшко снизу, обух сверху
    blade = [(0, 0), (16, -6), (40, -9.5), (64, -7.5), (64, 7.5), (44, 9), (24, 7), (8, 3.5)]
    s += merged([smooth_d(blade, closed=True, n=6)], WHITE, 4)
    s += line([(30, 2.5), (56, 2.5)], INK, 3.2)   # паз лезвия
    s += line([(10, 4.2), (38, 7.0)], INK, 1.8)   # заточка
    return s


def needle_holder(length=360):
    """Иглодержатель вдоль +x: кончик бранш в (0,0), кольца сзади (x>0)."""
    s = ''
    L = length
    lock = 78
    # бранши — обе половинки
    ring_c1, ring_c2 = (L - 24, -40), (L - 24, 40)
    shaft1 = [(lock, -3), (L - 70, -20), (ring_c1[0] - 14, ring_c1[1] + 16)]
    shaft2 = [(lock, 3), (L - 70, 20), (ring_c2[0] - 14, ring_c2[1] - 16)]
    ds = [poly_d(tube_outline(shaft1, [9, 8, 8])), poly_d(tube_outline(shaft2, [9, 8, 8]))]
    s += merged(ds, WHITE, 4)
    # кремальера
    for k in range(4):
        x = L - 92 + k * 7
        s += line([(x, -13), (x + 4, -9)], INK, 2)
    # кольца
    for c in (ring_c1, ring_c2):
        outer = ellipse_pts(c[0], c[1], 27, 21, 0)
        inner = ellipse_pts(c[0], c[1], 17, 12, 0)
        d = poly_d(outer) + poly_d(inner[::-1])
        s += f'<path d="{d}" fill="{WHITE}" stroke="{INK}" stroke-width="4" fill-rule="evenodd"/>'
    # губки
    jaw = [(0, -2.5), (lock - 8, -8), (lock + 6, -8), (lock + 6, 8), (lock - 8, 8), (0, 2.5)]
    s += merged([poly_d(jaw)], WHITE, 4)
    # насечка губок
    for x in range(6, lock - 12, 6):
        s += line([(x, -3), (x + 3, 3)], INK, 1.6)
    s += line([(4, 0), (lock - 6, 0)], INK, 1.6)
    # замок
    s += f'<rect x="{lock - 6}" y="-11" width="18" height="22" rx="3" fill="{WHITE}" stroke="{INK}" stroke-width="4"/>'
    s += f'<circle cx="{lock + 3}" cy="0" r="3.6" fill="{INK}"/>'
    return s


# ---------------------------------------------------------------- кисти

def sleeve(x0, top, bot, length=520, cuff_w=36):
    """Манжета перчатки и рукав халата, уходящие в +x от x0."""
    s = ''
    sl = [(x0 + cuff_w - 6, top - 8), (x0 + length, top - 34), (x0 + length, bot + 34), (x0 + cuff_w - 6, bot + 8)]
    s += merged([poly_d(sl)], INK, OW)
    # складки рукава — параллельные белые прорезы
    h = bot - top
    for k in range(5):
        xa = x0 + cuff_w + 26 + k * 46
        s += sline([(xa, top + h * 0.12 - k * 4), (xa + 22, top + h * 0.42), (xa + 8, top + h * 0.78 + k * 3)], WHITE, 3)
    cf = [(x0, top - 2), (x0 + cuff_w, top - 10), (x0 + cuff_w, bot + 10), (x0, bot + 2)]
    s += merged([poly_d(cf)], BORD, OW)
    s += line([(x0 + 10, top + 4), (x0 + 10, bot - 4)], WHITE, 3.4)
    s += line([(x0 + cuff_w - 10, top - 3), (x0 + cuff_w - 10, bot + 3)], INK, 2.6)
    return s


def curled(specs):
    """Согнутые пальцы (дальний план), каждый отдельным силуэтом."""
    s = ''
    for pts, ws in specs:
        fg = Finger(pts, ws)
        s += merged([fg.d()])
        s += fg.deco(0.25, 0.85, hatch=False)
    return s


def hand_scalpel():
    """Кисть держит скальпель писчим хватом; остриё в (0,0), кисть в +x."""
    s = ''
    s += curled([
        ([(262, 30), (236, 58), (238, 82), (258, 88)], [32, 28, 26, 24]),
        ([(248, 14), (214, 40), (208, 68), (230, 78)], [35, 31, 28, 26]),
        ([(236, -4), (196, 16), (180, 44), (200, 60)], [37, 33, 30, 27]),
    ])
    s += scalpel()
    back = smooth_d([(340, -56), (296, -66), (250, -66), (214, -54), (206, -30), (232, 0), (290, 26), (340, 44)], closed=True, n=8)
    index = Finger([(232, -50), (184, -64), (146, -42), (118, -14)], [40, 34, 30, 27])
    s += merged([back, index.d()])
    s += index.deco(0.1, 0.92)
    s += crease((185, -58), 30, 14) + crease((146, -38), 50, 12)
    s += sline([(318, -58), (282, -62), (246, -58)], WHITE, 3.6)
    # большой палец: толстое основание (тенар) и короткая дуга к рукоятке
    thumb = Finger([(320, 26), (268, 40), (214, 30), (178, 12), (160, 2)], [62, 48, 36, 31, 28])
    s += merged([thumb.d()])
    s += thumb.deco(0.3, 0.94)
    s += crease((214, 30), 100, 14)
    s += sleeve(332, -70, 56)
    return s


def hand_holder():
    """Кисть держит иглодержатель ладонным хватом; кончик бранш в (0,0), кисть в +x.

    Инструмент идёт по диагонали через ладонь, нижнее кольцо выглядывает из-под кисти.
    """
    s = ''
    # игла позади губок — выглядит зажатой
    s += needle_svg()
    s += needle_holder(410)
    hand = ''
    hand += curled([
        ([(296, 34), (268, 62), (272, 88), (294, 94)], [34, 30, 27, 25]),
        ([(284, 16), (248, 44), (244, 74), (268, 84)], [37, 33, 30, 27]),
        ([(272, -2), (232, 20), (218, 50), (240, 64)], [39, 35, 31, 28]),
    ])
    back = smooth_d([(380, -60), (330, -72), (282, -70), (250, -54), (246, -28), (270, 2), (326, 30), (380, 48)], closed=True, n=8)
    index = Finger([(270, -50), (228, -40), (192, -28), (160, -20)], [42, 36, 32, 28])
    hand += merged([back, index.d()])
    hand += index.deco(0.08, 0.9)
    hand += crease((228, -40), 80, 15) + crease((193, -28), 78, 12)
    hand += sline([(356, -62), (318, -68), (282, -62)], WHITE, 3.6)
    thumb = Finger([(356, 30), (302, 42), (252, 26), (222, 8)], [64, 48, 36, 30])
    hand += merged([thumb.d()])
    hand += thumb.deco(0.3, 0.94)
    hand += crease((254, 26), 105, 14)
    hand += sleeve(372, -74, 60)
    s += f'<g transform="rotate(-13 160 -6)">{hand}</g>'
    return s


NEEDLE_C, NEEDLE_R = (-24.5, -8.5), 30.7


def needle_pts():
    """Игла 3/8 окружности, захвачена губками у кончика (5,0) на трети от ушка.

    Первая точка — ушко (от него идёт нить), последняя — остриё.
    """
    c, r = NEEDLE_C, NEEDLE_R
    g = math.degrees(math.atan2(0 - c[1], 5 - c[0]))   # угол точки захвата
    return [(c[0] + r * math.cos(math.radians(t)), c[1] + r * math.sin(math.radians(t)))
            for t in [g + 45 - 135 * k / 30 for k in range(31)]]


def needle_svg():
    """Игла сужается от ушка к острию."""
    p = needle_pts()
    ctrl = p[::5]
    ws = [8.5 - 7 * k / (len(ctrl) - 1) for k in range(len(ctrl))]
    return merged([poly_d(tube_outline(ctrl, ws))], WHITE, 3.5)

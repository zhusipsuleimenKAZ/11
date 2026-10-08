"""Набор текста в кривые: HarfBuzz (кернинг) + контуры глифов fontTools.

Текст постера выводится контурами — типографии нужны «шрифты в кривых»,
а контуры букв заголовка нужны ещё и для переплетения нити.
"""
import os

import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from geom import f

HERE = os.path.dirname(os.path.abspath(__file__))


class FlattenPen(BasePen):
    """Аппроксимирует контуры ломаными — для проверки «точка внутри буквы»."""

    def __init__(self, glyphSet, steps=8):
        super().__init__(glyphSet)
        self.contours, self.cur, self.steps = [], [], steps

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for k in range(1, self.steps + 1):
            t = k / self.steps
            u = 1 - t
            self.cur.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                             u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for k in range(1, self.steps + 1):
            t = k / self.steps
            u = 1 - t
            self.cur.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                             u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))

    def _closePath(self):
        if self.cur:
            self.contours.append(self.cur)
        self.cur = []

    _endPath = _closePath


def inside(pt, contours):
    """Чётно-нечётное правило по всем контурам глифа (учитывает «дырки» в О, А…)."""
    x, y = pt
    c = False
    for poly in contours:
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
    return c


class Font:
    _cache = {}

    def __new__(cls, name):
        if name not in cls._cache:
            o = super().__new__(cls)
            path = os.path.join(HERE, 'fonts', name)
            data = open(path, 'rb').read()
            o.hb = hb.Font(hb.Face(data))
            o.tt = TTFont(path)
            o.gs = o.tt.getGlyphSet()
            o.order = o.tt.getGlyphOrder()
            o.upm = o.tt['head'].unitsPerEm
            o.cap = o.tt['OS/2'].sCapHeight / o.upm
            cls._cache[name] = o
        return cls._cache[name]

    def shape(self, s, ls=0.0):
        """Глифы с позициями (в единицах шрифта) и полная ширина; ls — трекинг в долях кегля."""
        buf = hb.Buffer()
        buf.add_str(s)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {'kern': True})
        x, out = 0, []
        extra = ls * self.upm
        for i, (info, pos) in enumerate(zip(buf.glyph_infos, buf.glyph_positions)):
            out.append((self.order[info.codepoint], x + pos.x_offset, pos.y_offset))
            x += pos.x_advance + (extra if i < len(buf.glyph_infos) - 1 else 0)
        return out, x

    def width(self, s, size, ls=0.0):
        return self.shape(s, ls)[1] / self.upm * size


def text_path(font, s, size, x, y, anchor='start', ls=0.0, width=None, glyph_polys=False):
    """SVG-путь строки. width — растянуть строку точно в эту ширину (подбором кегля).

    Возвращает (d, ширина, кегль[, полигоны глифов в координатах макета]).
    """
    F = Font(font)
    glyphs, adv = F.shape(s, ls)
    if width is not None:
        size = width / adv * F.upm
    sc = size / F.upm
    w = adv * sc
    x0 = x - (w / 2 if anchor == 'middle' else w if anchor == 'end' else 0)
    sp = SVGPathPen(F.gs, ntos=lambda v: f(v))
    polys = []
    for name, gx, gy in glyphs:
        t = (sc, 0, 0, -sc, x0 + gx * sc, y - gy * sc)
        F.gs[name].draw(TransformPen(sp, t))
        if glyph_polys:
            fp = FlattenPen(F.gs)
            F.gs[name].draw(TransformPen(fp, t))
            if fp.contours:
                polys.append(fp.contours)
    d = sp.getCommands()
    if glyph_polys:
        return d, w, size, polys
    return d, w, size

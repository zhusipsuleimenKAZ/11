"""Перевод карт рендера (глубина, нормали, группы) в векторную линогравюру.

Слои: заливки материалов → полутон по освещению → блики → линии перекрытий → силуэт.
Палитра — те же 4 цвета постера.
"""
import math

import numpy as np
from scipy import ndimage
from skimage import measure

from geom import BORD, WHITE, INK, f
from sdf import F, norm

LIGHT = norm((-0.42, 0.5, 0.76))      # свет сверху слева, как тени на постере


def to_page(maps, contour):
    r, c = contour[:, 0], contour[:, 1]
    return np.stack([maps.x0 + (c + 0.5) * maps.res, maps.y0 + (r + 0.5) * maps.res], axis=1)


def path_d(polys, closed=True, tol=0.18):
    out = []
    for p in polys:
        if len(p) < 3:
            continue
        p = measure.approximate_polygon(p, tol)
        s = 'M' + ' '.join(f'{f(x)},{f(y)}' for x, y in p)
        out.append(s + ('Z' if closed else ''))
    return ''.join(out)


def region(maps, mask, sigma=0.9, level=0.5, min_len=6):
    """Контуры бинарной маски (сглаженной) в координатах макета."""
    m = ndimage.gaussian_filter(mask.astype(F), sigma)
    m = np.pad(m, 1)
    cs = measure.find_contours(m, level)
    return [to_page(maps, c - 1) for c in cs if len(c) >= min_len]


def silhouette(maps):
    fld = np.where(maps.hit, -0.03, maps.mind).astype(F)
    fld = np.pad(fld, 1, constant_values=1.0)
    cs = measure.find_contours(fld, 0.004)
    return [to_page(maps, c - 1) for c in cs if len(c) >= 8]


def bilinear(img, rows, cols):
    if img.ndim == 2:
        return ndimage.map_coordinates(img, [rows, cols], order=1, mode='nearest')
    return np.stack([ndimage.map_coordinates(img[..., k], [rows, cols], order=1, mode='nearest')
                     for k in range(img.shape[2])], axis=-1)


def occluding_lines(maps, groups_mask_list, thr=0.1, min_pts=4):
    """Линии там, где одна часть перекрывает другую (скачок глубины), рисует передняя часть."""
    lines = []
    H, W = maps.shape
    for mask in groups_mask_list:
        if mask.sum() < 20:
            continue
        m = ndimage.gaussian_filter(mask.astype(F), 0.8)
        cs = measure.find_contours(np.pad(m, 1), 0.5)
        for c in cs:
            c = c - 1
            if len(c) < min_pts:
                continue
            # нормаль к контуру
            d = np.gradient(c, axis=0)
            nrm = np.stack([-d[:, 1], d[:, 0]], axis=1)
            nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
            # определяем, какая сторона внутри маски
            pi = c + nrm * 2.0
            po = c - nrm * 2.0
            mi = bilinear(m, pi[:, 0], pi[:, 1])
            mo = bilinear(m, po[:, 0], po[:, 1])
            flip = mi < mo
            pin = np.where(flip[:, None], po, pi)
            pout = np.where(flip[:, None], pi, po)
            ri, ci = np.clip(np.round(pin).astype(int), 0, [H - 1, W - 1]).T
            ro, co = np.clip(np.round(pout).astype(int), 0, [H - 1, W - 1]).T
            zin, zout = maps.depth[ri, ci], maps.depth[ro, co]
            hit_out = maps.hit[ro, co]
            keep = hit_out & (zin - zout > thr)
            # непрерывные участки
            run = []
            for k in range(len(c)):
                if keep[k]:
                    run.append(c[k])
                elif run:
                    if len(run) >= min_pts:
                        lines.append(to_page(maps, np.array(run)))
                    run = []
            if len(run) >= min_pts:
                lines.append(to_page(maps, np.array(run)))
    return lines


def halftone_dots(maps, mask, tone, step, angle, rmax, bbox_pad=0):
    """Точки растра: tone (H, W) 0..1 — доля площади ячейки."""
    H, W = maps.shape
    x0, y0 = maps.x0, maps.y0
    x1, y1 = x0 + W * maps.res, y0 + H * maps.res
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    R = math.hypot(x1 - x0, y1 - y0) / 2
    n = int(R / step) + 2
    ii, jj = np.meshgrid(np.arange(-n, n + 1), np.arange(-n, n + 1))
    a = math.radians(angle)
    gx = cx + (ii * math.cos(a) - jj * math.sin(a)) * step
    gy = cy + (ii * math.sin(a) + jj * math.cos(a)) * step
    cols = (gx - x0) / maps.res - 0.5
    rows = (gy - y0) / maps.res - 0.5
    ok = (cols >= 0) & (cols <= W - 1) & (rows >= 0) & (rows <= H - 1)
    gx, gy, rows, cols = gx[ok], gy[ok], rows[ok], cols[ok]
    mk = bilinear(mask.astype(F), rows, cols) > 0.5
    t = bilinear(tone.astype(F), rows, cols)
    r = rmax * np.sqrt(np.clip(t, 0, 1))
    sel = mk & (r > 0.35)
    ds = []
    for x, y, rr in zip(gx[sel], gy[sel], r[sel]):
        ds.append(f'M{f(x - rr)},{f(y)}a{f(rr)},{f(rr)} 0 1,0 {f(2 * rr)},0a{f(rr)},{f(rr)} 0 1,0 {f(-2 * rr)},0')
    return ''.join(ds)


def render_svg(scene, maps, uid, ow=4.6, iw=2.6, step=4.4, sleeve_dots=BORD):
    """SVG-фрагмент в координатах макета и путь силуэта (для тени)."""
    mats = np.array([g.material for g in scene.groups])
    names = [g.name for g in scene.groups]
    gid = maps.gid
    mat = np.where(maps.hit, mats[np.clip(gid, 0, len(mats) - 1)], '')
    nrm = maps.normal
    lam = np.clip(nrm @ LIGHT, 0, 1)
    ao = maps.ao
    hvec = norm(LIGHT + np.array([0, 0, 1], F))
    spec = np.clip(nrm @ hvec, 0, 1)

    sil = silhouette(maps)
    sil_d = path_d(sil)
    s = []
    # основа силуэта: чёрная заливка + обводка (внешний контур)
    s.append(f'<path d="{sil_d}" fill="{INK}" stroke="{INK}" stroke-width="{f(2 * ow)}" stroke-linejoin="round" fill-rule="evenodd"/>')
    clips = []
    for m, color in (('sleeve', INK), ('glove', BORD), ('steel', WHITE)):
        mask = mat == m
        if mask.sum() == 0:
            continue
        polys = region(maps, mask)
        d = path_d(polys)
        cid = f'{uid}-{m}'
        clips.append(f'<clipPath id="{cid}"><path d="{d}" fill-rule="evenodd"/></clipPath>')
        s.append(f'<path d="{d}" fill="{color}" fill-rule="evenodd"/>')
        if m == 'glove':
            tone = 1 - (0.12 + 0.88 * lam) * ao ** 1.4
            tone = np.clip((tone - 0.42) / 0.58, 0, 1)
            dots = halftone_dots(maps, mask, tone, step, 45, step * 0.62)
            s.append(f'<path d="{dots}" fill="{INK}" clip-path="url(#{cid})"/>')
            # блики латекса
            hl = (spec ** 46) * ao
            hmask = mask & (hl > 0.42)
            hp = region(maps, hmask, sigma=1.2)
            if hp:
                s.append(f'<path d="{path_d(hp)}" fill="{WHITE}" fill-rule="evenodd" clip-path="url(#{cid})"/>')
            # второй уровень блика — мелкий белый растр вокруг
            t2 = np.clip((spec ** 18 * ao - 0.25) / 0.5, 0, 1) * (hl <= 0.42)
            d2 = halftone_dots(maps, mask, t2, step, 45, step * 0.36)
            if d2:
                s.append(f'<path d="{d2}" fill="{WHITE}" clip-path="url(#{cid})"/>')
        elif m == 'steel':
            # хром: отражение «земли» (нижняя полусфера) — чёрные полосы
            rv = np.array([0, 0, -1], F) - 2 * (nrm @ np.array([0, 0, -1], F))[..., None] * nrm
            # хром: узкая тёмная полоса отражения горизонта + глубокие тени
            band = (rv[..., 1] < -0.05) & (rv[..., 1] > -0.55)
            dark = mask & (band | (lam * ao < 0.06))
            dp = region(maps, dark, sigma=0.8)
            if dp:
                s.append(f'<path d="{path_d(dp)}" fill="{INK}" fill-rule="evenodd" clip-path="url(#{cid})"/>')
        elif m == 'sleeve' and sleeve_dots:
            tone = np.clip((lam * ao - 0.35) / 0.65, 0, 1)
            dots = halftone_dots(maps, mask, tone, step * 1.1, 45, step * 0.5)
            s.append(f'<path d="{dots}" fill="{sleeve_dots}" clip-path="url(#{cid})"/>')
    # линии перекрытий
    gmasks = [maps.hit & (gid == k) for k in range(len(names))]
    lines = occluding_lines(maps, gmasks)
    if lines:
        s.append(f'<path d="{path_d(lines, closed=False)}" fill="none" stroke="{INK}" stroke-width="{f(iw)}" '
                 f'stroke-linecap="round" stroke-linejoin="round"/>')
    return ''.join(clips) + ''.join(s), sil_d

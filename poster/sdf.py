"""Минимальная библиотека SDF (signed distance functions) на numpy.

Все функции принимают массив точек P формы (N, 3) и возвращают расстояния (N,).
Формулы — по статьям Иниго Килеса (iquilezles.org/articles/distfunctions).
"""
import numpy as np

F = np.float32


def V(*a):
    return np.array(a, dtype=F)


def norm(v):
    v = np.asarray(v, dtype=F)
    return v / np.linalg.norm(v)


def frame(u, w_hint):
    """Ортонормированный базис: u — ось, w — ближайший к w_hint перпендикуляр, v = w x u."""
    u = norm(u)
    w = np.asarray(w_hint, dtype=F)
    w = norm(w - u * np.dot(w, u))
    v = np.cross(w, u)
    return u, v, w


def to_local(P, c, axes):
    """axes — (ex, ey, ez) в мировых координатах; возвращает координаты P в этом базисе."""
    M = np.stack(axes, axis=1).astype(F)
    return (P - c) @ M


def round_cone(P, a, b, r1, r2):
    a, b = np.asarray(a, F), np.asarray(b, F)
    ba = b - a
    l2 = float(np.dot(ba, ba))
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = P - a
    y = pa @ ba
    z = y - l2
    x2 = np.sum((pa * l2 - y[:, None] * ba) ** 2, axis=1)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - r1
    d1 = np.sqrt(x2 + z2) * il2 - r2
    d2 = np.sqrt(x2 + y2) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3)).astype(F)


def capsule(P, a, b, r):
    a, b = np.asarray(a, F), np.asarray(b, F)
    pa, ba = P - a, b - a
    h = np.clip((pa @ ba) / np.dot(ba, ba), 0, 1)
    return (np.linalg.norm(pa - h[:, None] * ba, axis=1) - r).astype(F)


def ellipsoid(P, c, r, axes=None):
    """Эллипсоид с полуосями r вдоль axes (по умолчанию — мировые оси). Приближённая SDF."""
    q = to_local(P, c, axes) if axes is not None else P - np.asarray(c, F)
    r = np.asarray(r, F)
    k0 = np.linalg.norm(q / r, axis=1)
    k1 = np.linalg.norm(q / (r * r), axis=1)
    return (k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)).astype(F)


def torus(P, c, axes, R, r):
    """Тор в плоскости (ex, ey) базиса axes; ось — ez."""
    q = to_local(P, c, axes)
    a = np.sqrt(q[:, 0] ** 2 + q[:, 1] ** 2) - R
    return (np.sqrt(a * a + q[:, 2] ** 2) - r).astype(F)


def round_box(P, c, axes, half, rad):
    q = np.abs(to_local(P, c, axes)) - (np.asarray(half, F) - rad)
    out = np.linalg.norm(np.maximum(q, 0), axis=1)
    inn = np.minimum(np.max(q, axis=1), 0)
    return (out + inn - rad).astype(F)


def polygon2d(px, py, poly):
    """SDF выпуклого/невыпуклого многоугольника в плоскости (по iq sdPolygon)."""
    poly = np.asarray(poly, F)
    d = (px - poly[0, 0]) ** 2 + (py - poly[0, 1]) ** 2
    s = np.ones_like(px)
    n = len(poly)
    j = n - 1
    for i in range(n):
        ex, ey = poly[j, 0] - poly[i, 0], poly[j, 1] - poly[i, 1]
        wx, wy = px - poly[i, 0], py - poly[i, 1]
        t = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey), 0, 1)
        bx, by = wx - ex * t, wy - ey * t
        d = np.minimum(d, bx * bx + by * by)
        c1 = py >= poly[i, 1]
        c2 = py < poly[j, 1]
        c3 = ex * wy > ey * wx
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
        j = i
    return (s * np.sqrt(d)).astype(F)


def extrude(P, c, axes, poly, half_th, rad=0.0):
    """Плоская фигура poly в плоскости (ex, ey), выдавленная на ±half_th по ez."""
    q = to_local(P, c, axes)
    d2 = polygon2d(q[:, 0], q[:, 1], poly)
    wx, wy = d2 + rad, np.abs(q[:, 2]) - half_th + rad
    return (np.minimum(np.maximum(wx, wy), 0) + np.sqrt(np.maximum(wx, 0) ** 2 + np.maximum(wy, 0) ** 2) - rad).astype(F)


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0) / k
    return (np.minimum(a, b) - h * h * k * 0.25).astype(F)


def smax(a, b, k):
    return -smin(-a, -b, k)

"""Геометрические помощники для векторной иллюстрации постера.

Все фигуры строятся как SVG-пути в координатах макета 1000 x 1414
(пропорции A3, 1 ед. = 0.297 мм).
"""
import math

BORD = '#76130D'   # глубокий бордовый — фон, перчатки
RED = '#E3261B'    # алый — акценты, плашки
WHITE = '#FFFFFF'  # белый — текст, инструменты, нить
INK = '#111111'    # угольно-чёрный — контуры, тени


def f(v):
    s = f'{v:.1f}'
    return s[:-2] if s.endswith('.0') else s


def catmull(points, n=12, closed=False):
    """Сглаживание ломаной сплайном Катмулла-Рома: возвращает точки и параметр t."""
    P = list(points)
    if closed:
        P = [P[-1]] + P + [P[0], P[1]]
    else:
        P = [P[0]] + P + [P[-1]]
    out, ts = [], []
    segs = len(P) - 3
    for i in range(segs):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
            ts.append(i + t)
    if not closed:
        out.append(P[-2])
        ts.append(segs)
    return out, ts


def poly_d(points, closed=True):
    d = 'M' + ' L'.join(f'{f(x)},{f(y)}' for x, y in points)
    return d + ('Z' if closed else '')


def normals(pts):
    ns = []
    for i in range(len(pts)):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1
        ns.append((-dy / L, dx / L))
    return ns


def tube_outline(points, widths, n=10, cap_start=True, cap_end=True):
    """Контур «трубки» переменной толщины вдоль сглаженной ломаной (палец, нить)."""
    pts, ts = catmull(points, n=n)
    ws = []
    for t in ts:
        i = min(int(t), len(widths) - 2)
        u = t - i
        ws.append(widths[i] * (1 - u) + widths[i + 1] * u)
    ns = normals(pts)
    left = [(p[0] + nx * w / 2, p[1] + ny * w / 2) for p, (nx, ny), w in zip(pts, ns, ws)]
    right = [(p[0] - nx * w / 2, p[1] - ny * w / 2) for p, (nx, ny), w in zip(pts, ns, ws)]
    out = list(left)
    # скругление на конце
    if cap_end:
        p, (nx, ny), w = pts[-1], ns[-1], ws[-1]
        a0 = math.atan2(ny, nx)
        for k in range(1, 12):
            a = a0 - math.pi * k / 12
            out.append((p[0] + math.cos(a) * w / 2, p[1] + math.sin(a) * w / 2))
    out += right[::-1]
    if cap_start:
        p, (nx, ny), w = pts[0], ns[0], ws[0]
        a0 = math.atan2(-ny, -nx)
        for k in range(1, 12):
            a = a0 - math.pi * k / 12
            out.append((p[0] + math.cos(a) * w / 2, p[1] + math.sin(a) * w / 2))
    return out


def rot(p, ang, c=(0, 0)):
    a = math.radians(ang)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * math.cos(a) - y * math.sin(a), c[1] + x * math.sin(a) + y * math.cos(a))

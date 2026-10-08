"""3D-модель кисти в хирургической перчатке и инструментов (SDF), рендер лучом.

Система координат кисти (см), правая рука:
  начало — середина лучезапястного сустава, x — к пальцам, y — к большому пальцу,
  z — тыльная сторона (ладонь смотрит в −z).
Пропорции — средние для взрослой кисти: длина кисти ≈19 см, ладони ≈10 см.
"""
import math

import numpy as np

from sdf import F, V, norm, frame, to_local, round_cone, ellipsoid, torus, round_box, extrude, smin

# ------------------------------------------------------------------ сцена


class Prim:
    def __init__(self, fn, center, radius):
        self.fn, self.c, self.r = fn, np.asarray(center, F), float(radius)

    def __call__(self, P, margin=1.6):
        bd = np.linalg.norm(P - self.c, axis=1) - self.r
        near = bd < margin
        if near.all():
            return self.fn(P)
        out = bd.astype(F)
        if near.any():
            out[near] = self.fn(P[near])
        return out


def prim_cone(a, b, r1, r2):
    a, b = np.asarray(a, F), np.asarray(b, F)
    return Prim(lambda P: round_cone(P, a, b, r1, r2), (a + b) / 2, np.linalg.norm(b - a) / 2 + max(r1, r2))


def prim_ell(c, r, axes=None):
    return Prim(lambda P: ellipsoid(P, c, r, axes), c, max(r))


class Group:
    def __init__(self, name, material, prims, k=0.0, blend=None, kb=0.0):
        self.name, self.material, self.prims, self.k = name, material, prims, k
        self.blend, self.kb = blend, kb        # имя группы, с которой сглаживаемся

    def sdf(self, P):
        d = None
        for p in self.prims:
            e = p(P)
            d = e if d is None else smin(d, e, self.k)
        return d


class Scene:
    def __init__(self, groups):
        self.groups = groups
        self.index = {g.name: i for i, g in enumerate(groups)}

    def eval(self, P, ids=False):
        raw = [g.sdf(P) for g in self.groups]
        eff = []
        for g, d in zip(self.groups, raw):
            if g.blend is not None:
                d = smin(raw[self.index[g.blend]], d, g.kb)
            eff.append(d)
        total = np.min(np.stack(eff), axis=0)
        if ids:
            return total, np.argmin(np.stack(raw), axis=0)
        return total


# ------------------------------------------------------------------ кисть

FINGERS = {
    #           MCP-сустав            разворот  длины фаланг         радиусы: основание, PIP, DIP, кончик
    'index': dict(mcp=(9.0, 2.3, 0.0), yaw=6, L=(4.1, 2.45, 1.65), r=(0.98, 0.88, 0.79, 0.73)),
    'middle': dict(mcp=(9.4, 0.62, 0.08), yaw=0, L=(4.5, 2.85, 1.75), r=(1.0, 0.91, 0.81, 0.75)),
    'ring': dict(mcp=(8.95, -1.05, 0.0), yaw=-5, L=(4.2, 2.7, 1.7), r=(0.96, 0.87, 0.77, 0.71)),
    'little': dict(mcp=(8.0, -2.6, -0.18), yaw=-11, L=(3.4, 2.05, 1.5), r=(0.85, 0.77, 0.69, 0.63)),
}
THUMB = dict(cmc=(1.5, 1.85, -0.85), L=(4.2, 3.1, 2.05), r=(1.2, 1.1, 1.02, 0.9))


def flex(d, n, deg):
    """Сгибание: d поворачивается к ладонной стороне (−n)."""
    t = math.radians(deg)
    return norm(math.cos(t) * d - math.sin(t) * n), norm(math.sin(t) * d + math.cos(t) * n)


def abduct(d, n, deg):
    """Отведение: поворот d вокруг n (положительно — к большому пальцу для правой руки)."""
    t = math.radians(deg)
    return norm(math.cos(t) * d + math.sin(t) * np.cross(n, d)), n


def finger_chain(spec, pose):
    """pose = (отведение, MCP, PIP, DIP) в градусах. Возвращает суставы и векторы."""
    ab, a1, a2, a3 = pose
    y = math.radians(spec['yaw'])
    d, n = V(math.cos(y), math.sin(y), 0), V(0, 0, 1)
    d, n = abduct(d, n, ab)
    J = [np.asarray(spec['mcp'], F)]
    frames = []
    for L, a in zip(spec['L'], (a1, a2, a3)):
        d, n = flex(d, n, a)
        J.append(J[-1] + L * d)
        frames.append((d, n))
    return J, frames


def thumb_chain(pose):
    """pose = (отведение к ладони, наклон вниз, ротация-оппозиция, MCP, IP)."""
    yaw, pitch, roll, a1, a2 = pose
    y = math.radians(yaw)
    d, n = V(math.cos(y), math.sin(y), 0), V(0, 0, 1)
    d, n = flex(d, n, pitch)
    r = math.radians(roll)        # поворот подушечки вокруг оси пальца
    n = norm(math.cos(r) * n + math.sin(r) * np.cross(d, n))
    J = [np.asarray(THUMB['cmc'], F)]
    frames = []
    J.append(J[-1] + THUMB['L'][0] * d)
    frames.append((d, n))
    for L, a in zip(THUMB['L'][1:], (a1, a2)):
        d, n = flex(d, n, a)
        J.append(J[-1] + L * d)
        frames.append((d, n))
    return J, frames


class Hand:
    def __init__(self, pose, thumb_pose, sleeve=True, wrist=(0.0, 0.0)):
        self.pose, self.thumb_pose = pose, thumb_pose
        # запястье: локтевое отведение и разгибание (град.) — поворачивают предплечье
        dev, ext = (math.radians(a) for a in wrist)
        a = V(-math.cos(dev) * math.cos(ext), -math.sin(dev) * math.cos(ext), -math.sin(ext))
        self.forearm = frame(-a, V(0, 0, 1))     # (ось к кисти, поперёк, тыл)
        self.chains = {k: finger_chain(FINGERS[k], pose[k]) for k in FINGERS}
        self.thumb = thumb_chain(thumb_pose)
        self.sleeve = sleeve

    def tip(self, name):
        J, fr = self.thumb if name == 'thumb' else self.chains[name]
        return J[-1], fr[-1]

    def pad(self, name, frac=0.0):
        """Точка подушечки дистальной фаланги (ладонная сторона)."""
        J, fr = self.thumb if name == 'thumb' else self.chains[name]
        spec_r = THUMB['r'] if name == 'thumb' else FINGERS[name]['r']
        p = J[-1] - frac * (J[-1] - J[-2])
        d, n = fr[-1]
        return p - n * spec_r[-1]

    def groups(self):
        gs = []
        # ладонь: пястные кости, тело ладони, тенар, гипотенар, запястье, манжета
        palm = []
        for k, sp in FINGERS.items():
            m = np.asarray(sp['mcp'], F)
            base = V(1.2, m[1] * 0.55, -0.05)
            palm.append(prim_cone(base, m, 1.0, sp['r'][0] * 1.08))
        palm.append(prim_ell(V(4.9, -0.05, -0.2), V(4.5, 3.25, 1.2)))
        palm.append(prim_ell(V(8.1, -0.1, -0.45), V(1.5, 3.55, 1.0)))
        tdir = norm(np.asarray(self.thumb[0][1]) - np.asarray(self.thumb[0][0]))
        u, v, w = frame(tdir, V(0, 0, 1))
        palm.append(prim_ell(V(3.4, 2.15, -0.85), V(3.0, 1.45, 1.3), (u, v, w)))
        palm.append(prim_ell(V(4.3, -2.55, -0.55), V(3.7, 1.05, 1.15)))
        palm.append(prim_ell(V(-1.2, 0, -0.1), V(3.4, 2.65, 1.75)))
        gs.append(Group('palm', 'glove', palm, k=1.1))
        # пальцы
        for k, (J, fr) in self.chains.items():
            r = FINGERS[k]['r']
            prims = [prim_cone(J[i], J[i + 1], r[i], r[i + 1]) for i in range(3)]
            gs.append(Group(k, 'glove', prims, k=0.25, blend='palm', kb=0.7))
        J, fr = self.thumb
        r = THUMB['r']
        prims = [prim_cone(J[i], J[i + 1], r[i], r[i + 1]) for i in range(3)]
        gs.append(Group('thumb', 'glove', prims, k=0.3, blend='palm', kb=1.2))
        # манжета перчатки и рукав
        gs.append(Group('cuff', 'glove', [cuff_prim(self.forearm)], blend='palm', kb=0.8))
        if self.sleeve:
            gs.append(Group('sleeve', 'sleeve', [sleeve_prim(self.forearm)], k=0))
        return gs


def ell_cyl(P, x0, x1, ry, rz, round_=0.6):
    """Эллиптический цилиндр вдоль x от x0 до x1 (скруглённые торцы). Нижняя оценка SDF."""
    s = ry / rz
    q = P.copy()
    q[:, 1] = q[:, 1] / s
    a = np.sqrt(q[:, 1] ** 2 + q[:, 2] ** 2) - (rz - round_)
    b = np.abs(q[:, 0] - (x0 + x1) / 2) - ((x1 - x0) / 2 - round_)
    out = np.sqrt(np.maximum(a, 0) ** 2 + np.maximum(b, 0) ** 2) + np.minimum(np.maximum(a, b), 0) - round_
    return out.astype(F)


def _fa(P, axes):
    """Точки в системе предплечья (x — к кисти); центр — запястье."""
    return to_local(P, V(0, 0, 0), axes)


def cuff_prim(axes):
    def fn(P):
        q = _fa(P, axes)
        d = ell_cyl(q, -9.0, -0.5, 2.85, 2.05, 0.5)
        lip = ell_cyl(q, -9.4, -8.2, 3.05, 2.25, 0.55)   # валик на краю манжеты
        return np.minimum(d, lip)
    c = -4.8 * axes[0]
    return Prim(fn, c, 5.5)


def sleeve_prim(axes):
    def fn(P):
        q = _fa(P, axes)
        x = q[:, 0]
        # складки халата: волна вдоль рукава
        ang = np.arctan2(q[:, 2], q[:, 1])
        bump = 0.22 * np.sin(x * 0.9 + 2.0 * ang) * np.clip((-x - 9.5) / 3, 0, 1)
        d = ell_cyl(q, -60.0, -8.6, 3.55, 2.85, 0.9)
        return (d - bump).astype(F)
    return Prim(fn, -34 * axes[0], 27)


# ------------------------------------------------------------------ инструменты


class Instrument:
    """Инструмент в собственной системе (u — ось, v — «вверх»/поперёк, w = u x v)."""

    def __init__(self, origin, u, v):
        self.o = np.asarray(origin, F)
        self.u = norm(u)
        v = np.asarray(v, F)
        self.v = norm(v - self.u * np.dot(v, self.u))
        self.w = np.cross(self.u, self.v)

    def at(self, a, b=0.0, c=0.0):
        return self.o + a * self.u + b * self.v + c * self.w

    @property
    def axes(self):
        return (self.u, self.v, self.w)


class Scalpel(Instrument):
    """Рукоятка №3 (12.5 см) и лезвие №10. u=0 — торец рукоятки; v — обух (вверх)."""
    HL = 12.4
    BLADE = [(12.15, 0.36), (15.2, 0.4), (16.05, 0.3), (16.75, 0.02), (16.5, -0.3),
             (15.8, -0.56), (14.7, -0.64), (13.5, -0.58), (12.15, -0.42)]

    def groups(self):
        ax = self.axes
        c = self.at(self.HL / 2)
        handle = Prim(lambda P: round_box(P, c, ax, (self.HL / 2, 0.42, 0.18), 0.13), c, self.HL / 2 + 0.5)
        o = self.o
        blade = Prim(lambda P: extrude(P, o, ax, self.BLADE, 0.035, 0.01), self.at(14.4), 2.6)
        # выступ-посадка под лезвие
        cn = self.at(self.HL + 0.6)
        lug = Prim(lambda P: round_box(P, cn, ax, (0.75, 0.2, 0.09), 0.05), cn, 1.0)
        return [Group('scalpel', 'steel', [handle, lug], k=0.05), Group('blade', 'steel', [blade])]

    def segments(self):
        """Грубая капсульная модель для проверки столкновений: (a, b, r)."""
        return [(self.at(0.2), self.at(self.HL - 0.2), 0.42)]


class NeedleHolder(Instrument):
    """Иглодержатель Майо-Гегара 16 см. u=0 — центры колец; v — поперёк, кольцо A при v>0."""
    RING_R, RING_r, RING_V = 1.36, 0.2, 1.85
    LOCK = 10.6
    TIP = 14.6

    def ring(self, sign):
        return self.at(0, sign * self.RING_V)

    def groups(self):
        ax = self.axes
        prims = []
        for s in (1, -1):
            c = self.ring(s)
            prims.append(Prim(lambda P, c=c: torus(P, c, ax, self.RING_R, self.RING_r), c, self.RING_R + 0.3))
            a = self.at(1.05, s * (self.RING_V - 0.55))
            b = self.at(self.LOCK - 0.3, s * 0.2)
            prims.append(prim_cone(a, b, 0.26, 0.22))
            # зубцы кремальеры
            t = self.at(2.6, s * 0.95, 0)
            prims.append(Prim(lambda P, t=t: round_box(P, t, ax, (0.45, 0.28, 0.16), 0.06), t, 0.7))
        cl = self.at(self.LOCK + 0.25)
        prims.append(Prim(lambda P: round_box(P, cl, ax, (0.6, 0.44, 0.3), 0.1), cl, 1.0))
        prims.append(prim_cone(self.at(self.LOCK + 0.8), self.at(self.TIP), 0.33, 0.16))
        return [Group('holder', 'steel', prims, k=0.12)]

    def segments(self):
        segs = []
        for s in (1, -1):
            segs.append((self.at(1.05, s * (self.RING_V - 0.55)), self.at(self.LOCK - 0.3, s * 0.2), 0.26))
        segs.append((self.at(self.LOCK), self.at(self.TIP), 0.33))
        return segs

    def needle(self, R=1.2, n=40):
        """Изогнутая игла 3/8 окружности в плоскости (v, w), захвачена у кончика губок."""
        g = self.at(self.TIP - 0.45)
        # центр окружности смещён от точки захвата по направлению −w·cos − v·sin
        phi = math.radians(200)
        cdir = math.cos(phi) * self.w + math.sin(phi) * self.v
        c = g - R * cdir
        pts = []
        for k in range(n):
            a = phi + math.radians(-45 + 135 * k / (n - 1))   # от ушка (−45°) до острия
            pts.append(c + R * (math.cos(a) * self.w + math.sin(a) * self.v))
        return np.array(pts, F)

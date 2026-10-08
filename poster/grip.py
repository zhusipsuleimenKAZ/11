"""Подбор хвата: углы суставов и положение инструмента (оптимизация).

Хваты — по учебникам оперативной хирургии:
  скальпель — «столовый нож»: указательный палец на обухе рукоятки, большой и
  средний сжимают рукоятку с боков, безымянный и мизинец прижимают её конец к ладони;
  иглодержатель — большой и безымянный пальцы в кольцах (дистальными фалангами),
  указательный вытянут вдоль бранши к замку, средний лежит на бранше.
"""
import json
import os

import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation

from hand3d import Hand, Scene, FINGERS, THUMB, Scalpel, NeedleHolder
from sdf import F, V, norm

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = ['index', 'middle', 'ring', 'little']
FB = [(-20, 20), (-10, 90), (0, 105), (0, 80)]
TB = [(-10, 80), (-5, 75), (-40, 150), (-10, 65), (-15, 80)]


def unpack(x):
    pose = {n: tuple(x[4 * i:4 * i + 4]) for i, n in enumerate(NAMES)}
    thumb = tuple(x[16:21])
    pos = np.asarray(x[21:24], F)
    rv = np.asarray(x[24:27])
    return pose, thumb, pos, rv


def inst_from(cls, pos, rv, u0=(1, 0, 0), v0=(0, 0, 1)):
    R = Rotation.from_rotvec(rv).as_matrix().astype(F)
    return cls(pos, R @ V(*u0), R @ V(*v0))


def seg_samples(hand):
    """Точки вдоль фаланг (с радиусами) для проверки столкновений."""
    pts, rads, owner = [], [], []
    for name in NAMES + ['thumb']:
        J, _ = hand.thumb if name == 'thumb' else hand.chains[name]
        r = THUMB['r'] if name == 'thumb' else FINGERS[name]['r']
        start = 1 if name == 'thumb' else 0     # пястную кость большого пальца прячет тенар
        for i in range(start, 3):
            for t in np.linspace(0, 1, 6):
                pts.append(J[i] * (1 - t) + J[i + 1] * t)
                rads.append(r[i] * (1 - t) + r[i + 1] * t)
                owner.append((name, i))
    return np.array(pts, F), np.array(rads, F), owner


def palm_scene(hand):
    gs = [g for g in hand.groups() if g.name in ('palm',)]
    return Scene(gs)


def penalties_common(hand, inst, w_pen=40.0, skip=()):
    pts, rads, owner = seg_samples(hand)
    isc = Scene(inst.groups())
    d = isc.eval(pts)
    mask = np.array([o not in skip for o in owner])
    pen = np.sum(np.maximum(0, rads[mask] - d[mask] + 0.02) ** 2)
    # инструмент не входит в ладонь
    ps = palm_scene(hand)
    ip = []
    for a, b, r in inst.segments():
        for t in np.linspace(0, 1, 14):
            ip.append((a * (1 - t) + b * t, r))
    P = np.array([p for p, _ in ip], F)
    R = np.array([r for _, r in ip], F)
    pd = ps.eval(P)
    pen += np.sum(np.maximum(0, R - pd + 0.02) ** 2)
    # пальцы не проходят друг сквозь друга (соседние)
    return w_pen * pen


def _acc(T, key, e, v):
    if T is not None:
        T[key] = T.get(key, 0) + float(v)
    return e + v


def prior(x, natural):
    return 0.0004 * float(np.sum((np.asarray(x[:21]) - natural) ** 2))


def coupling(pose):
    """DIP ≈ 0.7·PIP — естественная связь суставов."""
    return sum(0.002 * (p[3] - 0.7 * p[2]) ** 2 for p in pose.values())


def seg_dist(p, a, b):
    ab = b - a
    t = float(np.clip(np.dot(p - a, ab) / np.dot(ab, ab), 0, 1))
    return float(np.linalg.norm(p - (a + t * ab)))


def touch(hand, name, inst, ua, ub, off_v, off_w, extra_r=0.0):
    """Кончик пальца лежит на линии вдоль инструмента (u от ua до ub) со смещением (v, w)."""
    r = (THUMB if name == 'thumb' else FINGERS[name])['r'][-1] * 0.9 + extra_r
    sv = np.sign(off_v) * r if off_v else 0.0
    sw = np.sign(off_w) * r if off_w else 0.0
    a = inst.at(ua, off_v + sv, off_w + sw)
    b = inst.at(ub, off_v + sv, off_w + sw)
    return seg_dist(hand.tip(name)[0], a, b) ** 2


# ------------------------------------------------------------------ скальпель

def scalpel_objective(x, T=None):
    pose, thumb, pos, rv = unpack(x)
    hand = Hand(pose, thumb, sleeve=False)
    sc = inst_from(Scalpel, pos, rv)
    sg = 1.0 if np.dot(sc.w, V(0, 1, 0)) > 0 else -1.0     # сторона большого пальца
    e = 0.0
    e = _acc(T, 'index', e, 4.0 * touch(hand, 'index', sc, 9.6, 11.6, 0.42, 0))
    e = _acc(T, 'thumb', e, 3.0 * touch(hand, 'thumb', sc, 5.0, 9.0, 0.0, sg * 0.18))
    e = _acc(T, 'middle', e, 3.0 * touch(hand, 'middle', sc, 5.0, 9.0, -0.1, -sg * 0.18))
    e = _acc(T, 'ring', e, 2.0 * touch(hand, 'ring', sc, 3.0, 6.5, -0.42, -sg * 0.1))
    e = _acc(T, 'little', e, 2.0 * touch(hand, 'little', sc, 1.0, 4.5, -0.42, -sg * 0.1))
    # указательный лежит вдоль рукоятки
    d_idx = hand.tip('index')[1][0]
    e = _acc(T, 'idx_dir', e, 6.0 * max(0.0, 0.9 - float(np.dot(d_idx, sc.u))) ** 2)
    # торец рукоятки упирается в возвышение мизинца
    ps = palm_scene(hand)
    dend = float(ps.eval(sc.at(0.5, -0.1)[None])[0])
    e = _acc(T, 'end', e, 4.0 * (dend - 0.45) ** 2)
    # ориентация: лезвие вперёд и вниз, обух к тыльной стороне
    e = _acc(T, 'orient', e, 8.0 * max(0.0, 0.6 - float(sc.u[0])) ** 2
             + 4.0 * (float(sc.u[2]) + 0.38) ** 2 + 4.0 * max(0.0, 0.75 - float(sc.v[2])) ** 2)
    e = _acc(T, 'pen', e, penalties_common(hand, sc))
    e = _acc(T, 'coupl', e, coupling(pose))
    e = _acc(T, 'prior', e, prior(x, SC_NAT))
    return e


SC_NAT = np.array([0, 22, 12, 8, 0, 40, 50, 30, 0, 60, 70, 45, 0, 65, 75, 50, 40, 30, 70, 15, 15], float)


# ------------------------------------------------------------------ иглодержатель

def through_ring(hand, name, ring_c, ring_n):
    """Дистальная фаланга проходит через кольцо: центр кольца на оси фаланги, ось ≈ нормаль кольца."""
    J, fr = hand.thumb if name == 'thumb' else hand.chains[name]
    d = fr[-1][0]
    a = J[-2] + 0.25 * (J[-1] - J[-2])
    e = 4.0 * seg_dist(ring_c, a, J[-1]) ** 2
    e += 3.0 * max(0.0, 0.5 - abs(float(np.dot(d, ring_n)))) ** 2
    return e


def holder_objective(x, T=None):
    pose, thumb, pos, rv = unpack(x)
    hand = Hand(pose, thumb, sleeve=False)
    nh = inst_from(NeedleHolder, pos, rv, (1, 0, 0), (0, 1, 0))
    hs = 1.0 if np.dot(nh.w, V(0, 0, 1)) > 0 else -1.0     # сторона кисти
    e = 0.0
    e = _acc(T, 'thumb', e, through_ring(hand, 'thumb', nh.ring(1), nh.w))
    e = _acc(T, 'ring', e, through_ring(hand, 'ring', nh.ring(-1), nh.w))
    # указательный — на бранше у замка, средний — на бранше кольца безымянного
    e = _acc(T, 'index', e, 3.0 * touch(hand, 'index', nh, 7.0, 10.0, 0.3, hs * 0.26))
    d_idx = hand.tip('index')[1][0]
    e = _acc(T, 'idx_dir', e, 4.0 * max(0.0, 0.85 - float(np.dot(d_idx, nh.u))) ** 2)
    e = _acc(T, 'middle', e, 2.0 * touch(hand, 'middle', nh, 1.5, 5.0, -0.9, hs * 0.26))
    e = _acc(T, 'orient', e, 4.0 * max(0.0, 0.8 - float(nh.u[0])) ** 2)
    # средний, безымянный и мизинец согнуты в пястно-фаланговых суставах (не «крючком»)
    e = _acc(T, 'mcp', e, sum(0.01 * max(0.0, lim - pose[n][1]) ** 2
                              for n, lim in (('middle', 35), ('ring', 30), ('little', 35))))
    e = _acc(T, 'pen', e, penalties_common(hand, nh))
    e = _acc(T, 'coupl', e, coupling(pose))
    e = _acc(T, 'prior', e, prior(x, NH_NAT))
    return e


NH_NAT = np.array([-6, 22, 10, 6, 0, 50, 45, 25, 0, 60, 60, 35, 0, 65, 70, 45, 35, 40, 80, 10, 10], float)


def staged(objective, x0, bounds, fix_inst_first=True):
    """Сначала пальцы при закреплённом инструменте, затем всё вместе."""
    x0 = np.asarray(x0, float)
    opts = {'maxiter': 800, 'maxfun': 80000, 'eps': 0.01}
    if fix_inst_first:
        inst = x0[21:].copy()
        f = lambda xf: objective(np.r_[xf, inst])
        r = minimize(f, x0[:21], method='L-BFGS-B', bounds=bounds[:21], options=opts)
        x0 = np.r_[r.x, inst]
    r = minimize(objective, x0, method='L-BFGS-B', bounds=bounds, options=opts)
    return r


def rotvec_for(u, v):
    """Вектор поворота, переводящий (x, z) в (u, v) — для начального положения скальпеля."""
    u = norm(u)
    v = norm(v - u * np.dot(v, u))
    M = np.stack([u, np.cross(v, u), v], axis=1)   # столбцы — образы осей x, y, z
    return Rotation.from_matrix(M).as_rotvec()


def init_scalpel():
    pose = {'index': (0, 22, 12, 8), 'middle': (0, 40, 50, 30), 'ring': (0, 60, 70, 45), 'little': (0, 65, 75, 50)}
    thumb = (40, 30, 70, 15, 15)
    hand = Hand(pose, thumb, sleeve=False)
    pad = hand.pad('index', 0.25)
    n = hand.tip('index')[1][1]
    E = V(4.0, -2.3, -2.4)
    A = pad - n * 0.42
    u = norm(A - E)
    v = norm(n - u * np.dot(n, u))
    origin = A - u * 10.4
    x = [*sum((list(pose[k]) for k in NAMES), []), *thumb, *origin, *rotvec_for(u, v)]
    return np.array(x, float)


def init_holder():
    pose = {'index': (-6, 22, 10, 6), 'middle': (0, 50, 45, 25), 'ring': (0, 60, 60, 35), 'little': (0, 65, 70, 45)}
    thumb = (35, 40, 80, 10, 10)
    u = V(1, 0, 0)
    w = norm(V(0, 0.45, 0.9))           # плоскость колец наклонена к большому пальцу
    v = np.cross(w, u)
    M = np.stack([u, v, w], axis=1)
    rv = Rotation.from_matrix(M).as_rotvec()
    x = [*sum((list(pose[k]) for k in NAMES), []), *thumb, 8.4, 0.3, -4.2, *rv]
    return np.array(x, float)


if __name__ == '__main__':
    out = {}
    SB = FB * 4 + TB + [(-5, 14), (-6, 6), (-8, 3)] + [(-3.2, 3.2)] * 3
    HB = FB * 4 + TB + [(-2, 14), (-6, 6), (-9, 2)] + [(-3.2, 3.2)] * 3
    for name, init, obj, bnd in (('scalpel', init_scalpel, scalpel_objective, SB),
                                 ('holder', init_holder, holder_objective, HB)):
        x0 = init()
        print(name, 'init', round(obj(x0), 3))
        r = staged(obj, x0, bnd)
        print(name, 'final', round(float(r.fun), 4))
        out[name] = [float(v) for v in r.x]
    json.dump(out, open(os.path.join(HERE, 'grips.json'), 'w'), indent=1)


def load(which, wrist=(0.0, 0.0), sleeve=True):
    """Кисть и инструмент из сохранённого решения grips.json."""
    X = np.array(json.load(open(os.path.join(HERE, 'grips.json')))[which])
    pose, thumb, pos, rv = unpack(X)
    hand = Hand(pose, thumb, sleeve=sleeve, wrist=wrist)
    if which == 'scalpel':
        inst = inst_from(Scalpel, pos, rv)
    else:
        inst = inst_from(NeedleHolder, pos, rv, (1, 0, 0), (0, 1, 0))
    return hand, inst

"""Рендер двух кистей для постера: 3D-модель → векторный SVG-фрагмент.

    python3 hands_render.py [res]   -> hands_render.json (фрагменты, силуэты, игла)

res — шаг пикселя рендера в единицах макета (меньше — точнее и дольше).
"""
import json
import os
import sys
import time

import numpy as np

import grip
from hand3d import Scene
from render3d import Camera, march
from sdf import V, norm
from vectorize import render_svg

HERE = os.path.dirname(os.path.abspath(__file__))

# Камеры: направление взгляда, «верх», точка кисти → точка макета, масштаб (ед. макета на см), поворот
SHOTS = {
    # кисть со скальпелем — сверху справа, лезвие к центру; вид с лучевой стороны, чуть снизу
    'scalpel': dict(wrist=(12, 14), view=(0.15, -1, 0.3), up=(0, 0, 1), anchor='tip',
                    origin=(522, 206), scale=19.5, spin=16),
    # кисть с иглодержателем — снизу слева; вид с локтевой стороны и снизу: видны пальцы в кольцах
    # кисть с иглодержателем — снизу слева; вид сверху со стороны большого пальца:
    # большой палец в кольце, указательный вытянут вдоль бранши
    'holder': dict(wrist=(10, 8), view=(0.15, -0.6, -0.8), up='x', anchor='tip',
                   origin=(606, 264), scale=20.0, spin=-6),
}


def anchor_point(inst, which):
    if which == 'scalpel':
        return inst.at(16.75, 0.02)
    return inst.at(inst.TIP - 0.45)


def camera(shot, center):
    view = norm(V(*shot['view']))
    # up='x' — ось кисти x (к пальцам) идёт по горизонтали вправо
    up = np.cross(-view, V(1, 0, 0)) if shot['up'] == 'x' else V(*shot['up'])
    return Camera(view, up, center, shot['scale'], shot['origin'], shot['spin'])


def auto_bbox(hand, inst, cam, pad=45, page=(-12, -12, 1012, 1426)):
    """Рамка рендера по ключевым точкам кисти, инструмента и рукава, обрезанная листом."""
    pts = []
    for J, _ in list(hand.chains.values()) + [hand.thumb]:
        pts += list(J)
    for a, b, r in inst.segments():
        pts += [a, b]
    pts.append(inst.at(17.0))
    fa = hand.forearm[0]
    pts += [-t * fa for t in (0, 10, 20, 30, 45)]
    P = cam.project_many(np.array(pts))
    x0, y0 = P[:, 0].min() - pad, P[:, 1].min() - pad
    x1, y1 = P[:, 0].max() + pad, P[:, 1].max() + pad
    return (max(x0, page[0]), max(y0, page[1]), min(x1, page[2]), min(y1, page[3]))


def render(which, res=0.6):
    shot = SHOTS[which]
    hand, inst = grip.load(which, shot['wrist'])
    scene = Scene(hand.groups() + inst.groups())
    cam = camera(shot, anchor_point(inst, which))
    bbox = auto_bbox(hand, inst, cam)
    t = time.time()
    maps = march(scene, cam, bbox, res)
    svg, sil = render_svg(scene, maps, which)
    out = {'svg': svg, 'sil': sil, 'time': round(time.time() - t, 1)}
    if which == 'holder':
        nd = cam.project_many(inst.needle())
        out['needle'] = nd[:, :2].tolist()
        out['needle_z'] = nd[:, 2].tolist()
    return out


if __name__ == '__main__':
    res = float(sys.argv[1]) if len(sys.argv) > 1 else 0.6
    only = sys.argv[2:] or list(SHOTS)
    path = os.path.join(HERE, 'hands_render.json')
    data = json.load(open(path)) if os.path.exists(path) else {}
    for k in only:
        data[k] = render(k, res)
        print(k, data[k]['time'], 's', len(data[k]['svg']) // 1024, 'KB')
    json.dump(data, open(path, 'w'))

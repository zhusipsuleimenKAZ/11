"""Ортографический рендер SDF-сцены лучом (sphere tracing) в карты глубины/нормалей/групп."""
import math

import numpy as np

from sdf import F, norm


class Camera:
    """Ортографическая камера: page = origin + scale * (x_cam, −y_cam)."""

    def __init__(self, view, up, center, scale, origin, spin=0.0):
        z = -norm(view)                       # к зрителю
        x = norm(np.cross(up, z))
        y = np.cross(z, x)
        if spin:
            a = math.radians(spin)
            x, y = math.cos(a) * x + math.sin(a) * y, -math.sin(a) * x + math.cos(a) * y
        self.R = np.stack([x, y, z]).astype(F)   # строки — оси камеры в мире
        self.c = np.asarray(center, F)
        self.s = float(scale)
        self.o = np.asarray(origin, F)

    def project(self, p):
        q = self.R @ (np.asarray(p, F) - self.c)
        return (float(self.o[0] + self.s * q[0]), float(self.o[1] - self.s * q[1]), float(q[2]))

    def project_many(self, P):
        Q = (np.asarray(P, F) - self.c) @ self.R.T
        return np.stack([self.o[0] + self.s * Q[:, 0], self.o[1] - self.s * Q[:, 1], Q[:, 2]], axis=1)


class Maps:
    pass


def march(scene, cam, bbox, res, zmax=40.0, steps=160, eps=0.003):
    """bbox — (x0, y0, x1, y1) в единицах макета; res — шаг пикселя в тех же единицах."""
    x0, y0, x1, y1 = bbox
    xs = np.arange(x0, x1, res, dtype=F) + res / 2
    ys = np.arange(y0, y1, res, dtype=F) + res / 2
    PX, PY = np.meshgrid(xs, ys)
    H, W = PX.shape
    cx = ((PX - cam.o[0]) / cam.s).ravel()
    cy = (-(PY - cam.o[1]) / cam.s).ravel()
    N = cx.size
    cz = np.full(N, zmax, F)
    hit = np.zeros(N, bool)
    mind = np.full(N, 1e9, F)
    alive = np.ones(N, bool)
    Rt = cam.R
    for _ in range(steps):
        idx = np.nonzero(alive)[0]
        if idx.size == 0:
            break
        C = np.stack([cx[idx], cy[idx], cz[idx]], axis=1)
        Pw = C @ Rt + cam.c
        d = scene.eval(Pw)
        mind[idx] = np.minimum(mind[idx], d)
        h = d < eps
        hit[idx[h]] = True
        alive[idx[h]] = False
        cz[idx] -= np.maximum(d, eps) * 0.85
        out = cz[idx] < -zmax
        alive[idx[out]] = False
    m = Maps()
    m.shape, m.res, m.x0, m.y0 = (H, W), res, x0, y0
    m.hit = hit.reshape(H, W)
    m.depth = np.where(hit, cz, -1e3).reshape(H, W)
    m.mind = mind.reshape(H, W)
    # нормали, группы, затенение
    idx = np.nonzero(hit)[0]
    C = np.stack([cx[idx], cy[idx], cz[idx]], axis=1)
    Pw = C @ Rt + cam.c
    _, gid = scene.eval(Pw, ids=True)
    e = 0.004
    ks = np.array([[1, -1, -1], [-1, -1, 1], [-1, 1, -1], [1, 1, 1]], F)
    nrm = np.zeros_like(Pw)
    for k in ks:
        nrm += k * scene.eval(Pw + k * e)[:, None]
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
    ncam = nrm @ Rt.T
    # ambient occlusion
    occ = np.zeros(len(idx), F)
    sca = 1.0
    for i in range(1, 6):
        hh = 0.12 * i
        dd = scene.eval(Pw + nrm * hh)
        occ += (hh - dd) * sca
        sca *= 0.75
    ao = np.clip(1 - 1.6 * occ, 0, 1)
    m.gid = np.full(N, -1, np.int32)
    m.gid[idx] = gid
    m.gid = m.gid.reshape(H, W)
    m.normal = np.zeros((N, 3), F)
    m.normal[idx] = ncam
    m.normal = m.normal.reshape(H, W, 3)
    m.ao = np.ones(N, F)
    m.ao[idx] = ao
    m.ao = m.ao.reshape(H, W)
    m.world = np.zeros((N, 3), F)
    m.world[idx] = Pw
    m.world = m.world.reshape(H, W, 3)
    return m


def preview(scene, maps, path, light=(-0.45, 0.6, 0.66)):
    """Быстрый полутоновый превью-рендер для подбора позы."""
    from PIL import Image
    L = norm(light)
    lam = np.clip(maps.normal @ L, 0, 1)
    shade = (0.25 + 0.75 * lam) * maps.ao
    img = np.zeros(maps.shape + (3,), F)
    base = {'glove': (0.62, 0.16, 0.12), 'steel': (0.92, 0.92, 0.95), 'sleeve': (0.2, 0.2, 0.22)}
    for gi, g in enumerate(scene.groups):
        msk = maps.gid == gi
        img[msk] = np.array(base[g.material], F) * shade[msk][:, None]
    img[~maps.hit] = (0.95, 0.93, 0.85)
    # линии между группами и силуэт
    gid = maps.gid
    edge = np.zeros(maps.shape, bool)
    edge[:-1] |= gid[:-1] != gid[1:]
    edge[:, :-1] |= gid[:, :-1] != gid[:, 1:]
    dz = np.zeros(maps.shape, F)
    dz[:-1] = np.maximum(dz[:-1], np.abs(maps.depth[:-1] - maps.depth[1:]))
    dz[:, :-1] = np.maximum(dz[:, :-1], np.abs(maps.depth[:, :-1] - maps.depth[:, 1:]))
    edge &= dz > 0.35
    img[edge] = 0
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(path)

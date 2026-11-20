#!/usr/bin/env python3
"""Extrait les seules surfaces visibles, à partir des photos Pixel orientées EXIF.

Coordonnées repérées sur les images réduites à 768 × 1020, puis multipliées
par quatre : ordre PIL QUAD haut-gauche, bas-gauche, bas-droit, haut-droit.
Aucune reconstitution de zone manquante, ni correction colorimétrique.
"""
from pathlib import Path
from PIL import Image, ImageOps
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'sources/releve-2026-11-19'
DEST = ROOT / 'assets/oeuvres-releve-2026-11-19'
ITEMS = [
    ('PXL_20261119_071022056.jpg', 'tapisserie_escalier_avec_bordure.png',
     [(235, 374), (233, 570), (524, 577), (528, 378)], (1168, 784)),
    ('PXL_20261119_071022056.jpg', 'tapisserie_escalier_toile.png',
     [(255, 397), (254, 553), (505, 557), (507, 400)], (1008, 624)),
    ('PXL_20261119_071116601.jpg', 'tableau_marche_chambre_3_toile.png',
     [(112, 220), (111, 656), (635, 655), (635, 240)], (2096, 1704)),
    ('PXL_20261118_172814147.jpg', 'tableau_marine_couloir_toile.png',
     [(460, 350), (460, 540), (590, 589), (590, 270)], (760, 760)),
]

def coefficients(corners, size):
    # PIL attend une homographie sortie -> entrée.
    w, h = size
    destinations = [(0, 0), (0, h), (w, h), (w, 0)]
    a, b = [], []
    for (x, y), (u, v) in zip(destinations, corners):
        u, v = u * 4, v * 4
        a.extend([[x, y, 1, 0, 0, 0, -u*x, -u*y],
                  [0, 0, 0, x, y, 1, -v*x, -v*y]])
        b.extend([u, v])
    return tuple(np.linalg.solve(np.asarray(a, dtype=float), b))

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for source, name, corners, size in ITEMS:
        with Image.open(SOURCE / source) as raw:
            im = ImageOps.exif_transpose(raw).convert('RGB')
            coeff = coefficients(corners, size)
            im.transform(size, Image.Transform.PERSPECTIVE, coeff,
                         resample=Image.Resampling.BICUBIC).save(DEST / name, optimize=True)
        print(name, size)

if __name__ == '__main__':
    main()

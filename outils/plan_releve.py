#!/usr/bin/env python3
"""Plans métriques inspectables, calculés depuis les photos redressées d'évacuation."""
import html, json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
D=R/'travail/releve-2026-11-19'
data=json.loads((D/'mesures-plans.json').read_text())
for niveau, plan in data['plans'].items():
    poly=plan['emprise_brute']['polygone_m']
    xmin=min(p[0] for p in poly); xmax=max(p[0] for p in poly)
    ymin=min(p[1] for p in poly); ymax=max(p[1] for p in poly)
    scale=min(1000/(xmax-xmin),650/(ymax-ymin))
    def point(p):return (65+(p[0]-xmin)*scale,125+(p[1]-ymin)*scale)
    def points(pp):return ' '.join('%.2f,%.2f'%point(p) for p in pp)
    height=220+(ymax-ymin)*scale
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1130" height="{height:.0f}" viewBox="0 0 1130 {height:.0f}">',
           '<rect width="100%" height="100%" fill="#f5f2e9"/>',
           '<g font-family="sans-serif" fill="#20352e">',
           f'<text x="65" y="45" font-size="25">Château Saint-Victor — {html.escape(niveau)}</text>',
           '<text x="65" y="74" font-size="14">Relevé des plans photographiés les 18–19 novembre 2026 · nord en haut</text>',
           f'<text x="65" y="97" font-size="13">Emprise brute ≈ {plan["emprise_brute"]["surface_m2"]:.1f} m² · pièces au nu intérieur · numéros du plan conservés</text>',
           f'<polygon points="{points(poly)}" fill="#d1c9ba" stroke="#263b32" stroke-width="2"/>']
    for ident,room in plan['pieces'].items():
        pp=room['polygone_m'];desc=html.escape(room['description']);area=room['surface_m2']
        cx=sum(p[0] for p in pp)/len(pp);cy=sum(p[1] for p in pp)/len(pp);x,y=point((cx,cy))
        parts += [f'<polygon points="{points(pp)}" fill="#e7eee1" stroke="#627866" stroke-width="1"><title>{html.escape(ident)} — {desc} — environ {area:.1f} m²</title></polygon>',
                  f'<text x="{x:.1f}" y="{y-4:.1f}" text-anchor="middle" font-size="14">{html.escape(ident)}</text>',
                  f'<text x="{x:.1f}" y="{y+13:.1f}" text-anchor="middle" font-size="12">≈ {area:.1f} m²</text>']
    by=height-58
    parts += [f'<path d="M65 {by} h{scale*5:.1f}" stroke="#20352e" stroke-width="5"/>',
              f'<text x="65" y="{by-10}" font-size="12">0</text><text x="{65+scale*5:.1f}" y="{by-10}" font-size="12">5 m</text>',
              f'<text x="65" y="{height-23:.1f}" font-size="12">Mesures indicatives : écarts de 3–5 % entre plans. Les zones ouvertes ne constituent pas toutes des pièces closes.</text>',
              '</g></svg>']
    (D/f'plan-{niveau}-mesure.svg').write_text('\n'.join(parts))
    print(niveau,plan['emprise_brute']['surface_m2'],len(plan['pieces']))

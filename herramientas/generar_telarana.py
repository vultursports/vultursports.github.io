"""Genera la telaraña de la Vitrina (estaticos/img/telarana.svg).

Dibuja una telaraña de rincón: hilos que salen del rincón en abanico y vueltas de espiral que
cuelgan un poco entre hilo e hilo (como las de verdad), con algunos tramos cortados y un par de
hilos sueltos. Usa azar con semilla fija para que salga siempre igual.

Uso:  python herramientas/generar_telarana.py
"""
import math
import random
from pathlib import Path

random.seed(27)
TAM = 220                       # el rincón está en (0, 0)
RADIALES = 5
VUELTAS = 4
salida = []

# Hilos radiales (de 2° a 88°), con largo y ángulo un poco irregulares
angulos = [math.radians(2 + i * (86 / (RADIALES - 1)) + random.uniform(-3, 3)) for i in range(RADIALES)]
largos = [TAM * random.uniform(.82, 1.0) for _ in angulos]
for a, l in zip(angulos, largos):
    x, y = math.cos(a) * l, math.sin(a) * l
    salida.append(f'<path d="M0 0L{x:.1f} {y:.1f}" stroke-width=".9" opacity=".75"/>')

# Vueltas: radios que se separan hacia afuera; cada tramo entre dos hilos cuelga hacia el rincón
radio = 26
for v in range(VUELTAS):
    radio *= 1.0 + random.uniform(.38, .46) if v else 1
    puntos = []
    for a, l in zip(angulos, largos):
        r = min(radio * random.uniform(.94, 1.06), l - 2)
        puntos.append((math.cos(a) * r, math.sin(a) * r))
    for (x1, y1), (x2, y2) in zip(puntos, puntos[1:]):
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        caida = .16 + random.uniform(0, .08)   # cuánto cuelga hacia el rincón
        cx, cy = mx * (1 - caida), my * (1 - caida)
        op = .55 + .4 * (1 - v / VUELTAS)       # más tenue hacia afuera
        salida.append(f'<path d="M{x1:.1f} {y1:.1f}Q{cx:.1f} {cy:.1f} {x2:.1f} {y2:.1f}" stroke-width=".7" opacity="{op:.2f}"/>')

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {TAM} {TAM}" fill="none" stroke="#e8e6e1" '
       f'stroke-linecap="round">{"".join(salida)}</svg>\n')
destino = Path(__file__).resolve().parent.parent / "estaticos" / "img" / "telarana.svg"
destino.write_text(svg, encoding="utf-8")
print(f"telaraña generada: {destino} ({len(salida)} hilos)")

#!/usr/bin/env python3
"""Comprobación local sin red: valida calendario.json y que existan los medios."""
import json, os, sys, datetime as dt
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cal = json.load(open(os.path.join(raiz, "calendario.json"), encoding="utf-8"))
ids, mal = set(), 0
for p in cal["piezas"]:
    if p["id"] in ids: print("ID repetido", p["id"]); mal += 1
    ids.add(p["id"])
    dt.datetime.fromisoformat(p["fecha"])
    if p["tipo"] not in ("carrusel", "imagen", "reel", "story"): print("tipo raro", p); mal += 1
    if p["tipo"] == "carrusel" and not 2 <= len(p["medios"]) <= 10: print("carrusel con nº de imágenes inválido", p["id"]); mal += 1
    for m in p["medios"]:
        if not os.path.exists(os.path.join(raiz, m)): print("falta", m); mal += 1
print("OK" if not mal else f"{mal} problemas"); sys.exit(1 if mal else 0)

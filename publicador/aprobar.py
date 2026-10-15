#!/usr/bin/env python3
"""Aprueba una semana preparada: mueve borrador/semana-N/ a medios/semana-N/ y anade sus piezas a calendario.json.
Uso: python3 publicador/aprobar.py semana-3
El borrador es borrador/semana-N/propuesta.json (formato igual que calendario.json, con medios relativos a esa carpeta)
mas los archivos de medios. Despues de aprobar, hay que hacer commit y push: el publicador hace el resto."""
import json, os, shutil, sys, datetime as dt
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if len(sys.argv) != 2:
    sys.exit(__doc__)
semana = sys.argv[1]
origen = os.path.join(raiz, "borrador", semana)
destino = os.path.join(raiz, "medios", semana)
prop = json.load(open(os.path.join(origen, "propuesta.json"), encoding="utf-8"))
ruta_cal = os.path.join(raiz, "calendario.json")
cal = json.load(open(ruta_cal, encoding="utf-8"))
ids = {p["id"] for p in cal["piezas"]}
os.makedirs(destino, exist_ok=True)
for p in prop["piezas"]:
    if p["id"] in ids:
        sys.exit(f"ID ya existente: {p['id']}")
    dt.datetime.fromisoformat(p["fecha"])
    nuevos = []
    for m in p["medios"]:
        shutil.copy2(os.path.join(origen, m), os.path.join(destino, os.path.basename(m)))
        nuevos.append(f"medios/{semana}/{os.path.basename(m)}")
    p["medios"] = nuevos
    cal["piezas"].append(p)
cal["piezas"].sort(key=lambda p: p["fecha"])
json.dump(cal, open(ruta_cal, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
shutil.rmtree(origen)
print(f"{len(prop['piezas'])} piezas anadidas desde {semana}")

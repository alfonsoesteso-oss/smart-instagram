#!/usr/bin/env python3
"""Publica en Instagram las piezas de calendario.json cuya hora ya ha llegado.

Variables de entorno (secretos de GitHub):
  IG_USER_ID      ID de la cuenta profesional de Instagram
  IG_TOKEN        token de acceso de página (larga duración)
Opcionales:
  GRAPH_HOST      por defecto https://graph.facebook.com/v21.0
  DRY_RUN=1       no publica, solo muestra lo que haría
"""
import json, os, sys, time, datetime as dt
import urllib.request, urllib.parse, urllib.error
from zoneinfo import ZoneInfo

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAL = os.path.join(RAIZ, "calendario.json")
EST = os.path.join(RAIZ, "estado.json")
HOST = os.environ.get("GRAPH_HOST", "https://graph.facebook.com/v21.0")
UID = os.environ.get("IG_USER_ID", "")
TOK = os.environ.get("IG_TOKEN", "")
DRY = os.environ.get("DRY_RUN") == "1"
REPO = os.environ.get("GITHUB_REPOSITORY", "alfonsoesteso-oss/smart-instagram")
MADRID = ZoneInfo("Europe/Madrid")
MARGEN_MAX_H = 12  # no publica piezas que se pasaron de hora más de 12 h


def url_medio(ruta):
    # Los medios se sirven con GitHub Pages (tipos de contenido correctos para vídeo)
    usuario, repo = REPO.split("/")
    base = os.environ.get("MEDIOS_BASE", f"https://{usuario}.github.io/{repo}")
    return f"{base}/{urllib.parse.quote(ruta)}"


def api(metodo, ruta, datos=None):
    datos = dict(datos or {})
    datos["access_token"] = TOK
    url = f"{HOST}/{ruta}"
    if metodo == "GET":
        url += "?" + urllib.parse.urlencode(datos)
        req = urllib.request.Request(url)
    else:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(datos).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode(errors="replace")
        # no imprimir nunca el token
        raise RuntimeError(f"HTTP {e.code} en {ruta}: {cuerpo.replace(TOK, '***')}")


def esperar(contenedor, intentos=60, pausa=10):
    for _ in range(intentos):
        r = api("GET", contenedor, {"fields": "status_code,status"})
        if r.get("status_code") == "FINISHED":
            return
        if r.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Contenedor {contenedor} en estado {r}")
        time.sleep(pausa)
    raise RuntimeError(f"Tiempo agotado esperando {contenedor}")


def crear(pieza):
    tipo = pieza["tipo"]
    pie = pieza.get("texto", "")
    if tipo == "carrusel":
        hijos = []
        for ruta in pieza["medios"]:
            r = api("POST", f"{UID}/media", {"image_url": url_medio(ruta), "is_carousel_item": "true"})
            hijos.append(r["id"])
        for h in hijos:
            esperar(h)
        r = api("POST", f"{UID}/media", {"media_type": "CAROUSEL", "children": ",".join(hijos), "caption": pie})
    elif tipo == "imagen":
        r = api("POST", f"{UID}/media", {"image_url": url_medio(pieza["medios"][0]), "caption": pie})
    elif tipo == "reel":
        r = api("POST", f"{UID}/media", {"media_type": "REELS", "video_url": url_medio(pieza["medios"][0]),
                                          "caption": pie, "share_to_feed": "true"})
    elif tipo == "story":
        r = api("POST", f"{UID}/media", {"media_type": "STORIES", "image_url": url_medio(pieza["medios"][0])})
    else:
        raise RuntimeError(f"Tipo desconocido: {tipo}")
    esperar(r["id"])
    return api("POST", f"{UID}/media_publish", {"creation_id": r["id"]})["id"]


def main():
    cal = json.load(open(CAL, encoding="utf-8"))
    estado = json.load(open(EST, encoding="utf-8")) if os.path.exists(EST) else {}
    ahora = dt.datetime.now(MADRID)
    cambios = False
    for p in cal["piezas"]:
        pid = p["id"]
        if estado.get(pid, {}).get("estado") in ("publicada", "omitida"):
            continue
        cuando = dt.datetime.fromisoformat(p["fecha"]).replace(tzinfo=MADRID)
        if cuando > ahora:
            continue
        if (ahora - cuando).total_seconds() > MARGEN_MAX_H * 3600:
            estado[pid] = {"estado": "omitida", "motivo": "pasada de hora", "en": ahora.isoformat()}
            cambios = True
            print(f"[{pid}] omitida: se pasó de hora")
            continue
        print(f"[{pid}] toca publicar ({p['tipo']}, {p['fecha']})")
        if DRY:
            continue
        try:
            media_id = crear(p)
            estado[pid] = {"estado": "publicada", "media_id": media_id, "en": ahora.isoformat()}
            print(f"[{pid}] publicada: {media_id}")
        except Exception as e:  # noqa: BLE001
            intentos = estado.get(pid, {}).get("intentos", 0) + 1
            estado[pid] = {"estado": "error" if intentos < 3 else "omitida", "intentos": intentos,
                           "error": str(e)[:500], "en": ahora.isoformat()}
            print(f"[{pid}] ERROR: {e}", file=sys.stderr)
        cambios = True
    if cambios:
        json.dump(estado, open(EST, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    if any(v.get("estado") in ("error", "omitida") and v.get("error") for v in estado.values()):
        # marca el workflow en rojo para que GitHub avise por correo
        sys.exit(1)


if __name__ == "__main__":
    main()

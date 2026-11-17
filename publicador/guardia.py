#!/usr/bin/env python3
"""Guardia de publicación: espera dentro de la propia ejecución hasta la hora de la siguiente pieza.

Motivo: GitHub Actions no lanza el flujo cada 10 minutos como pide el cron. Desde el 15 nov 2026
solo lo lanza unas 4 veces al día (hacia las 01, 07, 15 y 21 h), así que las piezas de las 19:00
se quedaban sin publicar hasta la noche. Con esta guardia, la ejecución que llega antes de la hora
se queda esperando y publica a la hora exacta.

Funcionamiento:
  - Mira la siguiente pieza pendiente de calendario.json (no publicada ni omitida).
  - Si sale dentro del tiempo que le queda a esta ejecución (PRESUPUESTO), espera hasta su hora,
    ejecuta publicar.py y guarda estado.json en el repositorio en ese momento (así nunca se
    publica dos veces). Si falla, reintenta a los 10 minutos (publicar.py omite la pieza al 3.er fallo).
  - Si sale más tarde, pero antes de 3 x PRESUPUESTO (~16 h), espera lo que puede y lanza una
    ejecución nueva del flujo (relevo) que seguirá esperando. Así basta con que GitHub lance el
    flujo una vez por la mañana (hacia las 07 h) para que la pieza de las 19:00 salga a su hora.
  - Si sale más tarde aún, termina: alguna de las ejecuciones de GitHub de las siguientes horas
    la recogerá.

Variables: las mismas que publicar.py (IG_USER_ID, IG_TOKEN) y GH_TOKEN para el relevo.
GUARDIA_PRESUPUESTO_MIN cambia el presupuesto (por defecto 320 min; el job tiene 350 de límite).
"""
import json, os, subprocess, sys, time, datetime as dt
from zoneinfo import ZoneInfo

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAL = os.path.join(RAIZ, "calendario.json")
EST = os.path.join(RAIZ, "estado.json")
MADRID = ZoneInfo("Europe/Madrid")
PRESUPUESTO = dt.timedelta(minutes=int(os.environ.get("GUARDIA_PRESUPUESTO_MIN", "320")))
REINTENTO = dt.timedelta(minutes=10)
INICIO = dt.datetime.now(MADRID)
LIMITE = INICIO + PRESUPUESTO


def log(msg):
    print(f"{dt.datetime.now(MADRID):%H:%M:%S} guardia: {msg}", flush=True)


def git(*args, comprobar=True):
    return subprocess.run(["git", *args], cwd=RAIZ, check=comprobar, capture_output=True, text=True)


def actualizar_repo():
    # recoge un pack aprobado mientras esperábamos y el estado que hayan guardado otras ejecuciones
    r = git("pull", "--rebase", "--autostash", comprobar=False)
    if r.returncode != 0:
        log(f"aviso: git pull falló ({r.stderr.strip()[:200]})")


def guardar_estado():
    git("config", "user.name", "publicador")
    git("config", "user.email", "publicador@users.noreply.github.com")
    git("add", "estado.json")
    if git("diff", "--cached", "--quiet", comprobar=False).returncode == 0:
        return
    git("commit", "-m", "Actualizar estado de publicaciones")
    for intento in range(5):
        git("pull", "--rebase", comprobar=False)
        if git("push", comprobar=False).returncode == 0:
            log("estado.json guardado en el repositorio")
            return
        time.sleep(15 * (intento + 1))
    log("AVISO: no se pudo guardar estado.json (lo intentará el paso final)")


def cargar():
    cal = json.load(open(CAL, encoding="utf-8"))
    est = json.load(open(EST, encoding="utf-8")) if os.path.exists(EST) else {}
    return cal["piezas"], est


def fecha(p):
    return dt.datetime.fromisoformat(p["fecha"]).replace(tzinfo=MADRID)


def pendientes(piezas, est):
    return sorted((p for p in piezas if est.get(p["id"], {}).get("estado") not in ("publicada", "omitida")),
                  key=fecha)


def dormir_hasta(momento):
    while True:
        falta = (momento - dt.datetime.now(MADRID)).total_seconds()
        if falta <= 0:
            return
        time.sleep(min(falta, 300))


def publicar():
    r = subprocess.run([sys.executable, os.path.join(RAIZ, "publicador", "publicar.py")], cwd=RAIZ)
    guardar_estado()
    return r.returncode


def relevo():
    r = subprocess.run(["gh", "workflow", "run", "publicar.yml", "--ref", "main"], cwd=RAIZ,
                       capture_output=True, text=True)
    if r.returncode == 0:
        log("relevo lanzado: una ejecución nueva sigue esperando")
    else:
        log(f"AVISO: no se pudo lanzar el relevo ({r.stderr.strip()[:300]})")


def main():
    guardar_estado()  # lo que acabe de publicar el paso anterior
    llamadas = {}
    while True:
        actualizar_repo()
        piezas, est = cargar()
        cola = pendientes(piezas, est)
        ahora = dt.datetime.now(MADRID)
        if not cola:
            log("no hay piezas pendientes en calendario.json")
            return
        p = cola[0]
        cuando = fecha(p)
        if llamadas.get(p["id"], 0) >= 3:
            log(f"{p['id']} sigue pendiente tras 3 intentos en esta ejecución; termino")
            return
        if cuando <= ahora:
            # pendiente con la hora pasada (error anterior): reintento espaciado
            if est.get(p["id"], {}).get("estado") == "error" or llamadas.get(p["id"]):
                siguiente = ahora + REINTENTO
                if siguiente > LIMITE:
                    log(f"{p['id']} con error; no queda tiempo para reintentar en esta ejecución")
                    relevo()
                    return
                log(f"{p['id']} falló antes; reintento a las {siguiente:%H:%M}")
                dormir_hasta(siguiente)
            log(f"publicando {p['id']}")
            llamadas[p["id"]] = llamadas.get(p["id"], 0) + 1
            publicar()
            continue
        if cuando <= LIMITE:
            log(f"siguiente pieza {p['id']} a las {cuando:%d/%m %H:%M}: espero aquí")
            dormir_hasta(cuando + dt.timedelta(seconds=20))
            log(f"publicando {p['id']}")
            llamadas[p["id"]] = llamadas.get(p["id"], 0) + 1
            publicar()
            continue
        if cuando <= LIMITE + 2 * PRESUPUESTO:
            log(f"siguiente pieza {p['id']} a las {cuando:%d/%m %H:%M}: espero hasta {LIMITE:%H:%M} y lanzo relevo")
            dormir_hasta(LIMITE)
            relevo()
            return
        log(f"siguiente pieza {p['id']} a las {cuando:%d/%m %H:%M}: demasiado lejos, termino")
        return


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Anuncia en Instagram cada entrada nueva del blog de smart-informatica.es.

Uso:
  python publicador/blog.py preparar   # detecta entradas nuevas y genera su imagen (medios/blog/)
  python publicador/blog.py programar  # cuando la imagen ya está en GitHub Pages, la añade a calendario.json
  python publicador/blog.py muestra "Título de prueba"   # solo genera una imagen de prueba

El estado se guarda en blog.json:
  desde       solo se anuncian entradas publicadas a partir de esta fecha (hora de Madrid)
  vistos      ids de entradas ya anunciadas
  pendientes  entradas con imagen generada que aún no están en el calendario
La publicación la hace publicar.py como cualquier otra pieza del calendario (tipo "imagen").
"""
import html, json, os, re, sys, time, datetime as dt
import urllib.request, urllib.error
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTADO = os.path.join(RAIZ, "blog.json")
CAL = os.path.join(RAIZ, "calendario.json")
FUENTES = os.path.join(RAIZ, "publicador", "fuentes")
API = os.environ.get("BLOG_API", "https://www.smart-informatica.es/wp-json/wp/v2/posts")
REPO = os.environ.get("GITHUB_REPOSITORY", "alfonsoesteso-oss/smart-instagram")
MADRID = ZoneInfo("Europe/Madrid")
UA = "smart-instagram-publicador (+https://github.com/alfonsoesteso-oss/smart-instagram)"

NAVY, AZUL, NARANJA, BORDE = "#14213D", "#0095EB", "#FFB03A", "#cfe6f8"
HASHTAGS = "#smartinformatica #madrid #blog #informatica #ciberseguridad #tecnologia #pymes #consejostech"


# ---------------------------------------------------------------- utilidades
def leer_json(ruta, defecto):
    return json.load(open(ruta, encoding="utf-8")) if os.path.exists(ruta) else defecto


def guardar_json(ruta, datos):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
        f.write("\n")


def limpiar(texto_html):
    t = re.sub(r"<[^>]+>", " ", texto_html or "")
    t = html.unescape(t)
    t = re.sub(r"\s*\[(?:…|\.\.\.)\]", "…", t)
    return re.sub(r"\s+", " ", t).strip()


def recortar(texto, maximo):
    if len(texto) <= maximo:
        return texto
    corte = texto[:maximo].rsplit(" ", 1)[0].rstrip(",;:.")
    return corte + "…"


def entradas():
    url = API + "?per_page=10&status=publish&_fields=id,date,link,title,excerpt"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        datos = json.load(r)
    res = []
    for e in datos:
        res.append({
            "id": e["id"],
            "fecha": e["date"],
            "link": e["link"],
            "titulo": limpiar(e["title"]["rendered"]),
            "extracto": limpiar(e.get("excerpt", {}).get("rendered", "")),
        })
    return sorted(res, key=lambda x: x["fecha"])


def slug(link):
    s = link.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"[^a-z0-9-]", "", s.lower())[:60] or "entrada"


def url_pages(ruta):
    usuario, repo = REPO.split("/")
    return f"https://{usuario}.github.io/{repo}/{ruta}"


def existe(url):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- imagen
def fuente(peso, tam):
    return ImageFont.truetype(os.path.join(FUENTES, f"Poppins-{peso}.ttf"), tam)


def nube(draw, x, y, s, color):
    """Nube de marca: base redondeada + tres círculos. (x, y) = esquina sup. izq.; s = ancho."""
    h = s * 0.62
    draw.rounded_rectangle([x, y + h * 0.45, x + s, y + h], radius=int(h * 0.28), fill=color)
    draw.ellipse([x + s * 0.08, y + h * 0.30, x + s * 0.48, y + h * 0.95], fill=color)
    draw.ellipse([x + s * 0.28, y, x + s * 0.80, y + h * 0.80], fill=color)
    draw.ellipse([x + s * 0.58, y + h * 0.36, x + s * 0.96, y + h * 0.98], fill=color)


def icono(s):
    """Icono de marca (nube azul con insignia naranja y check), lado s, fondo transparente."""
    k = 4
    im = Image.new("RGBA", (s * k, s * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    S = s * k
    nube(d, 0, S * 0.30, S * 0.92, AZUL)
    cx, cy, r = S * 0.74, S * 0.30, S * 0.25
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="white")
    r2 = r * 0.80
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=NARANJA)
    w = int(S * 0.045)
    d.line([(cx - r2 * 0.45, cy + r2 * 0.02), (cx - r2 * 0.10, cy + r2 * 0.36), (cx + r2 * 0.48, cy - r2 * 0.32)],
           fill="white", width=w, joint="curve")
    return im.resize((s, s), Image.LANCZOS)


def fondo(w, h):
    """Degradado 160deg #ffffff -> #eaf5fe -> #d3ebfd con nubes decorativas."""
    base = Image.new("RGB", (w, h))
    px = base.load()
    stops = [(0.0, (255, 255, 255)), (0.5, (234, 245, 254)), (1.0, (211, 235, 253))]
    for yy in range(h):
        for xx in range(0, w, 4):
            t = min(1.0, max(0.0, (yy / h) * 0.85 + (xx / w) * 0.15))
            for (a, ca), (b, cb) in zip(stops, stops[1:]):
                if a <= t <= b:
                    f = (t - a) / (b - a)
                    c = tuple(int(ca[i] + (cb[i] - ca[i]) * f) for i in range(3))
                    break
            for k in range(4):
                if xx + k < w:
                    px[xx + k, yy] = c
    capa = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    azul10 = (0, 149, 235, 26)
    nube(d, w * 0.66, -h * 0.02, w * 0.48, azul10)
    nube(d, -w * 0.20, h * 0.86, w * 0.42, azul10)
    return Image.alpha_composite(base.convert("RGBA"), capa)


def envolver(draw, texto, f, ancho):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = (actual + " " + palabra).strip()
        if draw.textlength(prueba, font=f) <= ancho:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def imagen(titulo, salida):
    W, H = 1080, 1350
    im = fondo(W, H)
    d = ImageDraw.Draw(im)

    # Marca arriba
    ic = icono(72)
    im.alpha_composite(ic, (72, 66))
    f_marca = fuente("Bold", 34)
    d.text((158, 104), "Smart", font=f_marca, fill=NAVY, anchor="lm")
    d.text((158 + d.textlength("Smart ", font=f_marca) + 6, 104), "Informática", font=f_marca, fill=AZUL, anchor="lm")

    # Etiqueta naranja
    f_tag = fuente("Bold", 34)
    etiqueta = "NUEVA ENTRADA EN EL BLOG"
    tw = d.textlength(etiqueta, font=f_tag)
    x0, y0 = 90, 250
    d.rounded_rectangle([x0, y0, x0 + tw + 64, y0 + 74], radius=37, fill=NARANJA)
    d.text((x0 + 32, y0 + 37), etiqueta, font=f_tag, fill=NAVY, anchor="lm")

    # Tarjeta blanca con el título
    cx0, cy0, cx1, cy1 = 72, 370, W - 72, 980
    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle([cx0, cy0 + 14, cx1, cy1 + 14], radius=40, fill=(20, 33, 61, 40))
    im.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(18)))
    d.rounded_rectangle([cx0, cy0, cx1, cy1], radius=40, fill="white", outline=BORDE, width=3)

    ancho = (cx1 - cx0) - 2 * 64
    alto_max = (cy1 - cy0) - 2 * 60
    for tam in range(92, 47, -4):
        f_tit = fuente("Bold", tam)
        lineas = envolver(d, titulo, f_tit, ancho)
        interlinea = int(tam * 1.18)
        if len(lineas) * interlinea <= alto_max and len(lineas) <= 6:
            break
    total = len(lineas) * interlinea
    y = cy0 + ((cy1 - cy0) - total) / 2 + interlinea / 2
    for ln in lineas:
        d.text((cx0 + 64, y), ln, font=f_tit, fill=NAVY, anchor="lm")
        y += interlinea

    # Dónde leerla
    f_sub = fuente("Regular", 40)
    f_web = fuente("Bold", 44)
    d.text((W / 2, 1052), "Léela completa en", font=f_sub, fill=NAVY, anchor="mm")
    d.text((W / 2, 1106), "smart-informatica.es", font=f_web, fill=AZUL, anchor="mm")

    # Botón
    f_bot = fuente("Bold", 40)
    texto = "Enlace en la bio"
    bw = d.textlength(texto, font=f_bot) + 120
    bx0, by0 = (W - bw) / 2, 1170
    d.rounded_rectangle([bx0, by0, bx0 + bw, by0 + 96], radius=48, fill=NARANJA)
    d.text((W / 2, by0 + 48), texto, font=f_bot, fill=NAVY, anchor="mm")

    d.text((W / 2, 1306), "La informática, una solución. Nunca un problema.", font=fuente("Medium", 26),
           fill="#5a6b8c", anchor="mm")

    os.makedirs(os.path.dirname(salida), exist_ok=True)
    im.convert("RGB").save(salida, "JPEG", quality=92, optimize=True, progressive=False)


def pie(e):
    partes = [f"📝 Nueva entrada en nuestro blog: «{e['titulo']}»"]
    if e.get("extracto"):
        partes.append(recortar(e["extracto"], 260))
    partes.append(f"👉 Léela completa en el enlace de nuestra bio o aquí:\n{e['link']}")
    partes.append(HASHTAGS)
    return "\n\n".join(partes)


# ---------------------------------------------------------------- comandos
def preparar():
    estado = leer_json(ESTADO, {"vistos": [], "pendientes": []})
    vistos = set(estado["vistos"]) | {p["id"] for p in estado["pendientes"]}
    desde = estado.get("desde", "")  # solo se anuncian entradas publicadas a partir de esta fecha
    nuevas = [e for e in entradas() if e["id"] not in vistos and e["fecha"] >= desde]
    for e in nuevas:
        dia = e["fecha"][:10]
        ruta = f"medios/blog/{dia}-{slug(e['link'])}.jpg"
        imagen(e["titulo"], os.path.join(RAIZ, ruta))
        estado["pendientes"].append({**e, "medio": ruta, "detectada": dt.datetime.now(MADRID).isoformat(timespec="seconds")})
        print(f"Nueva entrada: {e['titulo']} -> {ruta}")
    if nuevas:
        guardar_json(ESTADO, estado)
    else:
        print("Sin entradas nuevas en el blog")
    return bool(nuevas)


def programar(espera_max=0):
    estado = leer_json(ESTADO, {"vistos": [], "pendientes": []})
    if not estado["pendientes"]:
        print("Nada pendiente")
        return False
    cal = leer_json(CAL, {"piezas": []})
    ids = {p["id"] for p in cal["piezas"]}
    limite = time.time() + espera_max
    quedan, cambios = [], False
    for e in estado["pendientes"]:
        url = url_pages(e["medio"])
        while not existe(url) and time.time() < limite:
            time.sleep(20)
        if not existe(url):
            print(f"La imagen aún no está publicada en GitHub Pages: {url} (se reintentará)")
            quedan.append(e)
            continue
        ahora = dt.datetime.now(MADRID).replace(second=0, microsecond=0, tzinfo=None)
        pid = f"{e['fecha'][:10]}-blog-{e['id']}"
        if pid not in ids:
            cal["piezas"].append({"id": pid, "tipo": "imagen", "fecha": ahora.isoformat(),
                                  "medios": [e["medio"]], "texto": pie(e), "origen": e["link"]})
            print(f"Programada {pid} para {ahora.isoformat()}")
        estado["vistos"].append(e["id"])
        cambios = True
    estado["pendientes"] = quedan
    if cambios:
        guardar_json(CAL, cal)
    guardar_json(ESTADO, estado)
    return cambios


if __name__ == "__main__":
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden == "preparar":
        hay = preparar()
    elif orden == "programar":
        hay = programar(int(os.environ.get("ESPERA_PAGES", "0")))
    elif orden == "muestra":
        titulo = sys.argv[2] if len(sys.argv) > 2 else "Título de prueba de una entrada del blog"
        salida = sys.argv[3] if len(sys.argv) > 3 else os.path.join(RAIZ, "muestra-blog.jpg")
        imagen(titulo, salida)
        print(salida)
        sys.exit(0)
    else:
        print(__doc__)
        sys.exit(2)
    salida_gh = os.environ.get("GITHUB_OUTPUT")
    if salida_gh:
        with open(salida_gh, "a") as f:
            f.write(f"hay={'si' if hay else 'no'}\n")

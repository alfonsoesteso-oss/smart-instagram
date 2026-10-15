# smart-instagram
Contenido de Instagram de Smart Informática y publicador automático.

## Flujo semanal
1. El domingo se prepara el pack de la semana siguiente.
2. Los reels se mezclan con música original: `python3 publicador/mezclar_musica.py reel.mp4 salida.mp4 N` (pistas en `publicador/musica/`, N = 1, 2 o 3).
3. El pack se deja como borrador en `borrador/semana-N/` (medios + `propuesta.json` con el mismo formato que `calendario.json`). No se publica nada.
4. Cuando el responsable dice "ok": `python3 publicador/aprobar.py semana-N`, luego `python3 publicador/probar.py`, commit y push a `main`.
5. GitHub Actions ("Publicar en Instagram", cada 10 min) publica cada pieza a su hora con la Instagram Graph API.

Piezas: `carrusel` (2-10 imágenes), `imagen`, `reel`, `story` (sin stickers: las stories con encuesta/pregunta se suben a mano).
Secretos necesarios en GitHub: `IG_TOKEN`, `IG_USER_ID`.

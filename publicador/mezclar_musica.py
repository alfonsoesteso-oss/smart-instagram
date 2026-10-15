#!/usr/bin/env python3
"""Mezcla una pista de musica original (publicador/musica/pista-N.m4a) con un reel sin audio.
Uso: python3 publicador/mezclar_musica.py reel.mp4 salida.mp4 [N]
Repite la pista si hace falta, la corta a la duracion del video y hace fundido final de 1,5 s."""
import os, subprocess, sys
raiz = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) < 3:
    sys.exit(__doc__)
video, salida = sys.argv[1], sys.argv[2]
n = sys.argv[3] if len(sys.argv) > 3 else "1"
pista = os.path.join(raiz, "musica", f"pista-{n}.m4a")
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video]).strip())
subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-stream_loop", "-1", "-i", pista,
    "-filter_complex", f"[1:a]atrim=0:{dur:.3f},afade=t=out:st={max(dur-1.5,0):.3f}:d=1.5[a]",
    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", salida])
print("OK", salida, round(dur, 2), "s")

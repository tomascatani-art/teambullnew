#!/usr/bin/env bash
# Spot ESTILO VINOS — genera efectos, banda sonora, imagen y arma los dos MP4 finales.
#   estilo-vinos-spot.mp4      música original + efectos de sonido
#   estilo-vinos-spot-sfx.mp4  solo efectos (para sumar un tema de la biblioteca de Instagram)
# Variables opcionales: EV_SRC (carpeta con los .mov), EV_LOGO (logo .jpg)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$HERE/.."
WORK="$OUT/.work-spot"
mkdir -p "$WORK"
cd "$HERE"

[[ -d "$OUT/.work-fx/cork_rain" ]] || python3 ../fx.py "$OUT/.work-fx"
python3 audio.py "$WORK"
[[ -f "$WORK/video.mp4" && "${SKIP_RENDER:-0}" == 1 ]] || python3 render.py "$WORK/video.mp4"

for kind in mix sfx; do
  name=estilo-vinos-spot; [[ $kind == sfx ]] && name=estilo-vinos-spot-sfx
  ffmpeg -v error -y -i "$WORK/video.mp4" -i "$WORK/$kind.wav" -map 0:v -map 1:a -c:v copy \
    -c:a aac -b:a 256k -shortest -movflags +faststart "$OUT/$name.mp4"
  echo "Listo: $OUT/$name.mp4"
done

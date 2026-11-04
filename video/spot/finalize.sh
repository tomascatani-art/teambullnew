#!/usr/bin/env bash
# Une los tramos renderizados (render.py --chunks), comprime para Instagram y agrega el audio.
# Uso: ./finalize.sh
set -euo pipefail
cd "$(dirname "$0")/.."
W=.work-spot
ls $W/chunks/chunk_*.mp4 | sort | sed "s|^$W/chunks/|file '|; s|$|'|" > $W/chunks/list.txt
ffmpeg -v error -y -f concat -safe 0 -i $W/chunks/list.txt -c copy $W/video.mp4
ffmpeg -v error -y -i $W/video.mp4 -c:v libx264 -crf 20 -preset slow -profile:v high -pix_fmt yuv420p $W/video_final.mp4
for kind in mix sfx; do
  name=estilo-vinos-spot; [[ $kind == sfx ]] && name=estilo-vinos-spot-sfx
  ffmpeg -v error -y -i $W/video_final.mp4 -i $W/$kind.wav -map 0:v -map 1:a -c:v copy \
    -c:a aac -b:a 256k -shortest -movflags +faststart $name.mp4
done
ffmpeg -v error -y -ss 34.5 -i estilo-vinos-spot.mp4 -frames:v 1 -q:v 2 estilo-vinos-spot-portada.jpg
echo "FINALIZADO"

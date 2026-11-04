#!/usr/bin/env bash
# Une el render principal con un final re-renderizado (desde el cuadro SPLICE), comprime para
# Instagram y agrega el audio. Uso: ./finalize.sh [SPLICE]
set -euo pipefail
cd "$(dirname "$0")/.."
W=.work-spot
SPLICE=${1:-912}
if [[ -f $W/tail.mp4 ]]; then
  ffmpeg -v error -y -i $W/video.mp4 -i $W/tail.mp4 -filter_complex \
    "[0:v]trim=end_frame=$SPLICE,setpts=PTS-STARTPTS[a];[1:v]setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1[v]" \
    -map "[v]" -c:v libx264 -crf 20 -preset slow -profile:v high -pix_fmt yuv420p $W/video_final.mp4
else
  ffmpeg -v error -y -i $W/video.mp4 -c:v libx264 -crf 20 -preset slow -profile:v high -pix_fmt yuv420p $W/video_final.mp4
fi
for kind in mix sfx; do
  name=estilo-vinos-spot; [[ $kind == sfx ]] && name=estilo-vinos-spot-sfx
  ffmpeg -v error -y -i $W/video_final.mp4 -i $W/$kind.wav -map 0:v -map 1:a -c:v copy \
    -c:a aac -b:a 256k -shortest -movflags +faststart $name.mp4
done
ffmpeg -v error -y -ss 34.5 -i estilo-vinos-spot.mp4 -frames:v 1 -q:v 2 estilo-vinos-spot-portada.jpg
echo "FINALIZADO"

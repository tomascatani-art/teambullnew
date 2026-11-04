#!/usr/bin/env bash
# Estilo Vinos — borrador de video vertical (1080x1920, 30 fps) hecho con ffmpeg.
# Uso: ./build.sh <carpeta-con-los-videos> <logo.jpg>
set -euo pipefail

SRC=${1:?carpeta con los .mov}
LOGO=${2:?logo jpg}
HERE=$(cd "$(dirname "$0")" && pwd)
WORK="$HERE/.work"
OUT="$HERE/estilo-vinos-borrador.mp4"
mkdir -p "$WORK"

CLIP_LEN=2.4   # segundos por toma
FADE=0.4       # duración de cada fundido
INTRO=3.0
OUTRO=4.0

# Orden de tomas: nombre|segundo de inicio|duración
SHOTS=(
  "IMG_1375|0.6|$CLIP_LEN"
  "IMG_1370|0.6|$CLIP_LEN"
  "IMG_1353|0.6|$CLIP_LEN"
  "IMG_1374|0.6|$CLIP_LEN"
  "IMG_1360|0.6|$CLIP_LEN"
  "IMG_1355|0.6|$CLIP_LEN"
  "IMG_1364|0.6|$CLIP_LEN"
  "IMG_1366|0.6|$CLIP_LEN"
  "IMG_1357|0.6|$CLIP_LEN"
  "IMG_1367|0.6|$CLIP_LEN"
  "IMG_1368|0.6|$CLIP_LEN"
  "IMG_1376|0.6|$CLIP_LEN"
  "IMG_1380|1.0|3.6"
)

NORM="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1,eq=contrast=1.05:saturation=1.08,format=yuv420p"

# 1) Logo en negro, 1080x1920, con fundido de entrada (intro) y de salida (outro)
logo_card() { # $1=salida $2=duración
  ffmpeg -v error -y -loop 1 -t "$2" -i "$LOGO" -f lavfi -t "$2" -i "color=black:s=1080x1920:r=30" \
    -filter_complex "[0]scale=820:-1:flags=lanczos,format=yuv420p[l];[1][l]overlay=(W-w)/2:(H-h)/2-80,fade=in:st=0:d=0.8,setsar=1,format=yuv420p" \
    -r 30 -c:v libx264 -crf 16 -preset medium -an "$1"
}
logo_card "$WORK/00_intro.mp4" "$INTRO"
logo_card "$WORK/99_outro.mp4" "$OUTRO"

# 2) Recortar y normalizar cada toma (ffmpeg aplica la rotación vertical del iPhone)
i=1
for s in "${SHOTS[@]}"; do
  IFS='|' read -r name ss dur <<<"$s"
  f=$(ls "$SRC"/*"$name".mov | head -1)
  printf -v n "%02d" "$i"
  ffmpeg -v error -y -ss "$ss" -t "$dur" -i "$f" -vf "$NORM" -an -c:v libx264 -crf 16 -preset medium "$WORK/${n}_${name}.mp4"
  echo "toma $n: $name"
  i=$((i+1))
done

# 3) Unir todo con fundidos cruzados
mapfile -t PARTS < <(ls "$WORK"/*.mp4 | sort)
inputs=(); for p in "${PARTS[@]}"; do inputs+=(-i "$p"); done
filter=""; prev="[0:v]"; offset=0
for ((k=1; k<${#PARTS[@]}; k++)); do
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "${PARTS[$((k-1))]}")
  offset=$(echo "$offset + $d - $FADE" | bc -l)
  out="[v$k]"
  filter+="${prev}[${k}:v]xfade=transition=fade:duration=$FADE:offset=$offset${out};"
  prev=$out
done
filter+="${prev}fade=out:st=$(echo "$offset + $OUTRO - 0.8" | bc -l):d=0.8,format=yuv420p[vout]"

ffmpeg -v error -y "${inputs[@]}" -filter_complex "$filter" -map "[vout]" \
  -c:v libx264 -crf 18 -preset slow -movflags +faststart -an "$OUT"
echo "Listo: $OUT ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT") s)"

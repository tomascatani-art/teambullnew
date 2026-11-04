#!/usr/bin/env bash
# Estilo Vinos — Reel de Instagram (1080x1920, 30 fps, sin música) hecho con ffmpeg.
# Uso: ./build.sh <carpeta-con-los-videos> <logo.jpg>
set -euo pipefail

SRC=${1:?carpeta con los .mov}
LOGO=${2:?logo jpg}
HERE=$(cd "$(dirname "$0")" && pwd)
WORK="$HERE/.work"
OUT="$HERE/estilo-vinos-reel.mp4"
COVER="$HERE/estilo-vinos-portada.jpg"
SERIF=/usr/share/fonts/truetype/freefont/FreeSerif.ttf
SERIF_IT=/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf
rm -rf "$WORK"; mkdir -p "$WORK"

FADE=0.3    # fundido entre tomas
OPEN=3.4    # primera toma, con el logo encima
ENDCARD=4.0 # cierre con logo y texto

# Orden de tomas: nombre|segundo de inicio|duración
SHOTS=(
  "IMG_1370|0.6|2.0"
  "IMG_1353|0.6|2.0"
  "IMG_1374|0.6|2.0"
  "IMG_1360|0.6|2.0"
  "IMG_1355|0.6|2.0"
  "IMG_1364|0.6|2.0"
  "IMG_1366|0.6|2.0"
  "IMG_1357|0.6|2.0"
  "IMG_1367|0.6|2.0"
  "IMG_1368|0.6|2.0"
  "IMG_1376|0.6|2.0"
  "IMG_1380|1.0|3.4"
)

src() { ls "$SRC"/*"$1".mov | head -1; }

# Encuadre vertical + color + zoom lento hacia adentro (se trabaja en 4K para que el zoom sea suave)
look() { # $1 = duración
  local frames; frames=$(echo "$1*30" | bc -l | cut -d. -f1)
  echo "scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,fps=30,eq=contrast=1.05:saturation=1.08,zoompan=z='1+0.05*on/$frames':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,setsar=1,format=yuv420p"
}
enc=(-c:v libx264 -crf 16 -preset medium -an)

# Logo con transparencia (blanco sobre negro -> blanco con alfa)
ffmpeg -v error -y -i "$LOGO" -vf "scale=760:-1:flags=lanczos,format=gray,split[c][a];[a]lut=y='if(lt(val\,30)\,0\,val)'[a2];[c]format=rgba[c2];[c2][a2]alphamerge" "$WORK/logo.png"

# 1) Apertura: vista general de la tienda, oscurecida, con el logo apareciendo
ffmpeg -v error -y -ss 0.6 -t "$OPEN" -i "$(src IMG_1375)" -loop 1 -t "$OPEN" -i "$WORK/logo.png" \
  -f lavfi -t "$OPEN" -i "color=c=black:s=1080x1920:r=30" -filter_complex "
  [0]$(look "$OPEN")[v];
  [2]format=rgba,colorchannelmixer=aa=0.55,fade=out:st=2.4:d=0.7:alpha=1[dim];
  [1]fade=in:st=0.2:d=0.7:alpha=1,fade=out:st=2.3:d=0.7:alpha=1[l];
  [v][dim]overlay[v2];[v2][l]overlay=(W-w)/2:(H-h)/2-120:format=auto,format=yuv420p" \
  -t "$OPEN" "${enc[@]}" "$WORK/00_open.mp4"
echo "apertura lista"

# 2) Tomas de la tienda
i=1
for s in "${SHOTS[@]}"; do
  IFS='|' read -r name ss dur <<<"$s"
  printf -v n "%02d" "$i"
  ffmpeg -v error -y -ss "$ss" -t "$dur" -i "$(src "$name")" -vf "$(look "$dur")" "${enc[@]}" "$WORK/${n}_${name}.mp4"
  echo "toma $n: $name"
  i=$((i+1))
done

# 3) Cierre: logo + texto
ffmpeg -v error -y -f lavfi -t "$ENDCARD" -i "color=c=black:s=1080x1920:r=30" -loop 1 -t "$ENDCARD" -i "$WORK/logo.png" -filter_complex "
  [1]fade=in:st=0:d=0.6:alpha=1[l];
  [0][l]overlay=(W-w)/2:560:format=auto,
  drawtext=fontfile=$SERIF:text='VINOS   ·   DESTILADOS   ·   REGALOS':fontcolor=white@0.85:fontsize=38:x=(w-text_w)/2:y=1240:alpha='min(1,max(0,(t-0.8)/0.6))',
  drawtext=fontfile=$SERIF_IT:text='Te esperamos':fontcolor=white:fontsize=64:x=(w-text_w)/2:y=1330:alpha='min(1,max(0,(t-1.3)/0.6))',
  format=yuv420p" "${enc[@]}" "$WORK/99_end.mp4"
ffmpeg -v error -y -ss 3.0 -i "$WORK/99_end.mp4" -frames:v 1 -q:v 2 "$COVER"
echo "cierre listo"

# 4) Unir todo con fundidos cruzados y fundido final a negro
mapfile -t PARTS < <(ls "$WORK"/*.mp4 | sort)
inputs=(); for p in "${PARTS[@]}"; do inputs+=(-i "$p"); done
filter=""; prev="[0:v]"; offset=0
for ((k=1; k<${#PARTS[@]}; k++)); do
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "${PARTS[$((k-1))]}")
  offset=$(echo "$offset + $d - $FADE" | bc -l)
  filter+="${prev}[${k}:v]xfade=transition=fade:duration=$FADE:offset=$offset[v$k];"
  prev="[v$k]"
done
filter+="${prev}fade=out:st=$(echo "$offset + $ENDCARD - 0.7" | bc -l):d=0.7,format=yuv420p[vout]"

ffmpeg -v error -y "${inputs[@]}" -filter_complex "$filter" -map "[vout]" \
  -c:v libx264 -crf 18 -preset slow -profile:v high -movflags +faststart -an "$OUT"
echo "Listo: $OUT ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT") s)"

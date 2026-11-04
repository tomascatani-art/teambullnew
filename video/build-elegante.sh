#!/usr/bin/env bash
# Estilo Vinos — versión elegante con corchos cayendo y transiciones de vino.
# Requiere los efectos de fx.py:  python3 fx.py .work-fx
# Uso: ./build-elegante.sh <carpeta-con-los-videos> <logo.jpg>
set -euo pipefail

SRC=${1:?carpeta con los .mov}
LOGO=${2:?logo jpg}
HERE=$(cd "$(dirname "$0")" && pwd)
FX="$HERE/.work-fx"
WORK="$HERE/.work-elegante"
OUT="$HERE/estilo-vinos-elegante.mp4"
COVER="$HERE/estilo-vinos-elegante-portada.jpg"
SERIF=/usr/share/fonts/truetype/freefont/FreeSerif.ttf
SERIF_IT=/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf
BG=0x0D0608
rm -rf "$WORK"; mkdir -p "$WORK"
[[ -d "$FX/wine_a" ]] || { echo "Faltan efectos: python3 fx.py $FX"; exit 1; }

INTRO=4.0
ENDCARD=4.5

# nombre|inicio|duración|texto
SHOTS=(
  "IMG_1375|0.6|2.4|Vinos seleccionados"
  "IMG_1370|0.6|2.2|"
  "IMG_1364|0.6|2.2|"
  "IMG_1353|0.6|2.4|Regalos que sorprenden"
  "IMG_1374|0.6|2.2|"
  "IMG_1368|0.6|2.4|Destilados"
  "IMG_1366|0.6|2.2|"
  "IMG_1355|0.6|2.4|Envíos a domicilio"
  "IMG_1376|0.6|2.2|"
  "IMG_1380|1.0|3.0|Independencia 1001"
)
# Transición que entra en cada parte (índice 0 = intro, no usa)
TRANS=(none wine_a fade cork_rain fade wine_b fade cork_rain fade fade fade wine_a)

src() { ls "$SRC"/*"$1".mov | head -1; }
enc=(-c:v libx264 -crf 16 -preset medium -an)

# Logo con transparencia + degradado oscuro inferior para que el texto se lea
ffmpeg -v error -y -i "$LOGO" -vf "scale=760:-1:flags=lanczos,format=gray,split[c][a];[a]lut=y='if(lt(val\,30)\,0\,val)'[a2];[c]format=rgba[c2];[c2][a2]alphamerge" "$WORK/logo.png"
python3 - "$WORK/grad.png" <<'EOF'
import sys, numpy as np
from PIL import Image
y = np.linspace(0, 1, 1920)[:, None]
a = np.clip((y - 0.58) / 0.42, 0, 1) ** 1.4 * 0.72 * 255
img = np.zeros((1920, 1080, 4), np.uint8); img[..., 3] = np.broadcast_to(a, (1920, 1080)).astype(np.uint8)
Image.fromarray(img, "RGBA").save(sys.argv[1])
EOF

fadein() { echo "alpha='min(1\,max(0\,(t-$1)/0.6))*min(1\,max(0\,($2-t)/0.4))'"; }

# 1) Intro: fondo oscuro, el logo aparece mientras caen los corchos
ffmpeg -v error -y -f lavfi -t "$INTRO" -i "color=c=$BG:s=1080x1920:r=30" -loop 1 -t "$INTRO" -i "$WORK/logo.png" -filter_complex "
  [0]vignette=PI/4[bg];[1]fade=in:st=1.4:d=0.9:alpha=1[l];
  [bg][l]overlay=(W-w)/2:(H-h)/2-100:format=auto,format=yuv420p" "${enc[@]}" "$WORK/00_intro.mp4"

# 2) Tomas: encuadre vertical, color cálido, zoom lento y texto en serif
i=1
for s in "${SHOTS[@]}"; do
  IFS='|' read -r name ss dur text <<<"$s"
  frames=$(echo "$dur*30" | bc -l | cut -d. -f1)
  vf="[0]scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,fps=30,eq=contrast=1.06:saturation=1.1,colorbalance=rs=0.03:bs=-0.03:rm=0.02:bm=-0.02,zoompan=z='1+0.05*on/$frames':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,setsar=1"
  if [[ -n "$text" ]]; then
    vf+="[v];[v][1]overlay=0:0:format=auto,drawtext=fontfile=$SERIF_IT:text='$text':fontsize=76:fontcolor=white:x=(w-text_w)/2:y=1420:shadowcolor=black@0.6:shadowy=3:$(fadein 0.35 "$dur")"
  fi
  vf+=",format=yuv420p"
  printf -v n "%02d" "$i"
  ffmpeg -v error -y -ss "$ss" -t "$dur" -i "$(src "$name")" -loop 1 -t "$dur" -i "$WORK/grad.png" \
    -filter_complex "$vf" -t "$dur" "${enc[@]}" "$WORK/${n}_${name}.mp4"
  echo "toma $n: $name ${text:+— $text}"
  i=$((i+1))
done

# 3) Cierre: logo, Instagram, dirección y envíos
ffmpeg -v error -y -f lavfi -t "$ENDCARD" -i "color=c=$BG:s=1080x1920:r=30" -loop 1 -t "$ENDCARD" -i "$WORK/logo.png" -filter_complex "
  [0]vignette=PI/4[bg];[1]fade=in:st=0.3:d=0.8:alpha=1[l];
  [bg][l]overlay=(W-w)/2:400:format=auto,
  drawbox=x=(iw-300)/2:y=1080:w=300:h=2:color=white@0.45:t=fill:enable='gte(t,0.9)',
  drawtext=fontfile=$SERIF:text='@estilovinos':fontsize=66:fontcolor=white:x=(w-text_w)/2:y=1140:$(fadein 0.9 99),
  drawtext=fontfile=$SERIF:text='Independencia 1001':fontsize=50:fontcolor=white@0.9:x=(w-text_w)/2:y=1250:$(fadein 1.3 99),
  drawtext=fontfile=$SERIF_IT:text='Envíos a domicilio':fontsize=50:fontcolor=0xE8C9A0:x=(w-text_w)/2:y=1330:$(fadein 1.7 99),
  format=yuv420p" "${enc[@]}" "$WORK/99_end.mp4"
ffmpeg -v error -y -ss 3.5 -i "$WORK/99_end.mp4" -frames:v 1 -q:v 2 "$COVER"
echo "intro y cierre listos"

# 4) Unir: fundidos de base + efectos (vino / corchos) encima de cada corte
mapfile -t PARTS < <(ls "$WORK"/*.mp4 | sort)
inputs=(); for p in "${PARTS[@]}"; do inputs+=(-i "$p"); done
np=${#PARTS[@]}
filter=""; prev="[0:v]"; offset=0
fxin=(-framerate 30 -start_number 18 -i "$FX/intro_corks/%04d.png"); fxs="[$np:v]setpts=PTS-STARTPTS[fx0];"; fxchain=("fx0|0")
nx=$((np+1))
for ((k=1; k<np; k++)); do
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "${PARTS[$((k-1))]}")
  t=${TRANS[$k]}
  case $t in wine_*) td=0.04 ;; cork_rain) td=0.35 ;; *) td=0.4 ;; esac
  offset=$(echo "$offset + $d - $td" | bc -l)
  filter+="${prev}[${k}:v]xfade=transition=fade:duration=$td:offset=$offset[v$k];"
  prev="[v$k]"
  if [[ $t != fade ]]; then
    lead=0.5; [[ $t == cork_rain ]] && lead=0.55
    start=$(echo "$offset + $td/2 - $lead" | bc -l)
    fxin+=(-framerate 30 -i "$FX/$t/%04d.png")
    fxs+="[$nx:v]setpts=PTS-STARTPTS+$start/TB[fx$nx];"
    fxchain+=("fx$nx|$start")
    nx=$((nx+1))
  fi
done
total=$(echo "$offset + $ENDCARD" | bc -l)
filter+="${prev}format=yuv420p[base];$fxs"
cur="[base]"; j=0
for e in "${fxchain[@]}"; do
  IFS='|' read -r lbl st <<<"$e"
  filter+="${cur}[$lbl]overlay=eof_action=pass:format=auto[o$j];"
  cur="[o$j]"; j=$((j+1))
done
filter+="${cur}fade=out:st=$(echo "$total - 0.8" | bc -l):d=0.8,format=yuv420p[vout]"

ffmpeg -v error -y "${inputs[@]}" "${fxin[@]}" -filter_complex "$filter" -map "[vout]" -t "$total" \
  -c:v libx264 -crf 18 -preset slow -profile:v high -movflags +faststart -an "$OUT"
echo "Listo: $OUT ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT") s)"

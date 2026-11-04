#!/usr/bin/env bash
# Estilo Vinos — versión "propaganda": cortes rápidos, textos de venta, transiciones dinámicas.
# Uso: ./build-propaganda.sh <carpeta-con-los-videos> <logo.jpg>
set -euo pipefail

SRC=${1:?carpeta con los .mov}
LOGO=${2:?logo jpg}
HERE=$(cd "$(dirname "$0")" && pwd)
WORK="$HERE/.work-propaganda"
OUT="$HERE/estilo-vinos-propaganda.mp4"
BOLD=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
WINE=0x7B1E3A
rm -rf "$WORK"; mkdir -p "$WORK"

ENDCARD=3.6

# nombre|inicio|duración|texto (vacío = sin texto)
SHOTS=(
  "IMG_1375|0.6|1.8|¿BUSCÁS EL VINO IDEAL?"
  "IMG_1370|0.6|1.1|"
  "IMG_1364|0.6|1.4|VINOS PARA CADA OCASIÓN"
  "IMG_1360|0.6|1.0|"
  "IMG_1368|0.6|1.4|DESTILADOS"
  "IMG_1357|0.6|1.4|CERVEZAS"
  "IMG_1353|0.6|1.5|CAJAS PARA REGALAR"
  "IMG_1355|0.6|1.0|"
  "IMG_1374|0.6|1.5|COPAS Y ACCESORIOS"
  "IMG_1376|0.6|1.1|"
  "IMG_1366|0.6|1.0|"
  "IMG_1380|1.0|2.4|TE ESPERAMOS"
)
# Transición que entra en cada toma (la primera no usa)
TRANS=(none slideleft zoomin slideup wipeleft smoothleft slideleft zoomin slideup smoothleft wipeleft zoomin fadeblack)

src() { ls "$SRC"/*"$1".mov | head -1; }

# Logos con transparencia: grande (cierre) y chico (marca de agua)
mklogo() { ffmpeg -v error -y -i "$LOGO" -vf "scale=$1:-1:flags=lanczos,format=gray,split[c][a];[a]lut=y='if(lt(val\,30)\,0\,val)'[a2];[c]format=rgba[c2];[c2][a2]alphamerge" "$2"; }
mklogo 760 "$WORK/logo.png"
mklogo 170 "$WORK/logo-small.png"

banner() { # $1=texto  $2=tamaño  $3=y  $4=segundo en que aparece
  printf "drawtext=fontfile=%s:text='%s':fontsize=%s:fontcolor=white:box=1:boxcolor=%s@0.92:boxborderw=26:x='(w-text_w)/2-max(0\,(%s+0.18-t))*4000':y=%s:alpha='min(1\,max(0\,(t-%s)/0.12))'" \
    "$BOLD" "$1" "$2" "$WINE" "$4" "$3" "$4"
}

# 1) Tomas: encuadre vertical, color con más contraste, zoom rápido, marca de agua y texto
i=1
for s in "${SHOTS[@]}"; do
  IFS='|' read -r name ss dur text <<<"$s"
  frames=$(echo "$dur*30" | bc -l | cut -d. -f1)
  vf="[0]scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,fps=30,eq=contrast=1.12:saturation=1.22:brightness=0.01,vignette=PI/5,zoompan=z='1+0.09*on/$frames':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,setsar=1[v];[v][1]overlay=W-w-60:230"
  [[ -n "$text" ]] && vf+=",$(banner "$text" 62 1240 0.2)"
  vf+=",format=yuv420p"
  printf -v n "%02d" "$i"
  ffmpeg -v error -y -ss "$ss" -t "$dur" -i "$(src "$name")" -loop 1 -t "$dur" -i "$WORK/logo-small.png" \
    -filter_complex "$vf" -t "$dur" -c:v libx264 -crf 16 -preset medium -an "$WORK/${n}_${name}.mp4"
  echo "toma $n: $name ${text:+— $text}"
  i=$((i+1))
done

# 2) Cierre: fondo bordó oscuro, logo y llamado a la acción
ffmpeg -v error -y -f lavfi -t "$ENDCARD" -i "color=c=0x14070B:s=1080x1920:r=30" -loop 1 -t "$ENDCARD" -i "$WORK/logo.png" -filter_complex "
  [0]vignette=PI/4[bg];
  [1]fade=in:st=0:d=0.4:alpha=1[l];
  [bg][l]overlay=(W-w)/2:'520+max(0\,(0.4-t))*300':format=auto,
  $(banner 'VENÍ A CONOCERNOS' 66 1250 0.6),
  format=yuv420p" -c:v libx264 -crf 16 -preset medium -an "$WORK/99_end.mp4"
echo "cierre listo"

# 3) Unir con transiciones rápidas
mapfile -t PARTS < <(ls "$WORK"/*.mp4 | sort)
inputs=(); for p in "${PARTS[@]}"; do inputs+=(-i "$p"); done
filter=""; prev="[0:v]"; offset=0
for ((k=1; k<${#PARTS[@]}; k++)); do
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "${PARTS[$((k-1))]}")
  t=${TRANS[$k]}; td=0.2; [[ $t == fadeblack ]] && td=0.4
  offset=$(echo "$offset + $d - $td" | bc -l)
  filter+="${prev}[${k}:v]xfade=transition=$t:duration=$td:offset=$offset[v$k];"
  prev="[v$k]"
done
filter+="${prev}format=yuv420p[vout]"

ffmpeg -v error -y "${inputs[@]}" -filter_complex "$filter" -map "[vout]" \
  -c:v libx264 -crf 18 -preset slow -profile:v high -movflags +faststart -an "$OUT"
echo "Listo: $OUT ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT") s)"

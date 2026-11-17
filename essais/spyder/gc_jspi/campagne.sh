#!/bin/sh
# W576 : campagne gcnu.mjs, n répétitions par cas ; une trace par essai dans traces/, une ligne de bilan par essai.
# Usage : sh campagne.sh [n]   (bilan dans traces/bilan.txt)
cd "$(dirname "$0")"
n=${1:-3}
mkdir -p traces
: > "traces/${BILAN:-bilan}.txt"
while read -r gc susp var fils tours; do
  [ -z "$gc" ] && continue
  i=1
  while [ $i -le $n ]; do
    f="traces/${var}_${fils}x${tours}_gc${gc}_susp${susp}_$i.txt"
    GC=$gc SUSP=$susp timeout 180 node gcnu.mjs "$var" "$fils" "$tours" > "$f" 2>&1
    rc=$?
    sig=$(grep -m1 -oE 'RuntimeError: [a-z ]+|Cannot enter a promising task|handback_tstate|Fatal Python error: [A-Za-z_ ]+|OK fini' "$f")
    echo "$var $fils x $tours GC=$gc SUSP=$susp #$i rc=$rc ${sig:-timeout/aucune}" >> "traces/${BILAN:-bilan}.txt"
    i=$((i + 1))
  done
done <<EOF
${CAS:-1 1 seul 4 200
1 0 entrelace 4 200
0 1 entrelace 4 200
off 1 entrelace 4 200
1 1 entrelace 1 200
1 1 entrelace 4 200
1 1 imbrique 8 200}
EOF
cat "traces/${BILAN:-bilan}.txt"

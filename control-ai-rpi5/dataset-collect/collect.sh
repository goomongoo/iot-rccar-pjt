#!/bin/bash
# collect.sh
# usage: ./collect.sh <scenario> <throttle> <steer> <repeat>

SCENARIO=$1
THROTTLE=$2
STEER=$3
REPEAT=$4

DURATION=2.0
BASE_DIR="data/train"
OUT_CSV="${BASE_DIR}/${SCENARIO}.csv"

if [ -z "$REPEAT" ]; then
  echo "Usage: ./collect.sh <scenario> <throttle> <steer> <repeat>"
  exit 1
fi

mkdir -p "$BASE_DIR"

echo "======================================"
echo " Scenario : $SCENARIO"
echo " Command  : throttle=$THROTTLE steer=$STEER"
echo " Duration : ${DURATION}s per run"
echo " Repeat   : $REPEAT times"
echo " Output   : $OUT_CSV"
echo "======================================"
echo "ENTER → collect once | Ctrl+C → stop"
echo ""

COUNT=1

trap_ctrlc() {
  echo ""
  echo "[STOP] interrupted at ${COUNT}/${REPEAT}"
  exit 0
}
trap trap_ctrlc SIGINT

while [ $COUNT -le $REPEAT ]
do
  echo "--------------------------------------"
  echo "Run ${COUNT}/${REPEAT}"
  echo "→ 차량 위치 잡고 ENTER"
  read

  python3 collect.py "$THROTTLE" "$STEER" "$DURATION" "$OUT_CSV"

  COUNT=$((COUNT + 1))
done

echo ""
echo "[DONE] all ${REPEAT} runs completed"


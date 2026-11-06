#!/usr/bin/env bash
cd "$(dirname "$0")/.."
for n in api web; do
  [ -f .run/$n.pid ] && kill "$(cat .run/$n.pid)" 2>/dev/null && echo "stopped $n"; rm -f .run/$n.pid
done

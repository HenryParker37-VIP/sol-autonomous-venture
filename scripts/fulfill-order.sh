#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
printf "Paid order ID: "; read -r order_id
cd "$ROOT"
python3 fulfillment.py "$order_id"

#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
today=$(date +%F)
printf "Buyer name: "; read -r buyer_name
printf "Profile link: "; read -r profile_link
printf "Buyer email or DM platform: "; read -r contact
printf "Payment confirmed yes/no: "; read -r payment_confirmed
case "$payment_confirmed" in yes|no) ;; *) echo "Use yes or no." >&2; exit 2;; esac
slug=$(printf '%s' "$buyer_name" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-*//;s/-*$//')
dir="$ROOT/buyers/$today-$slug"
mkdir -p "$dir"
cat > "$dir/intake.md" <<EOF
# Buyer intake

- Buyer: $buyer_name
- Profile: $profile_link
- Contact: $contact
- Payment confirmed: $payment_confirmed
- Created: $today

Ask for target audience, preferred tone, desired call to action, and PayPal receipt/order email before drafting.
EOF
cp "$ROOT/product/delivery-template.md" "$dir/delivery.md"
cat > "$dir/notes.md" <<EOF
# Notes

- Payment status: $payment_confirmed
- Delivery target: within 24 hours after owner confirmation
- Revision allowance: one small revision
EOF
echo "Created $dir"

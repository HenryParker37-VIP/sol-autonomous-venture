#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
: "${HP_OS_HOSTED_OWNER_TOKEN:?Set HP_OS_HOSTED_OWNER_TOKEN from the private Netlify owner secret}"
printf "Hosted order ID: "; read -r order_id
HOSTED_API_URL=${HP_OS_HOSTED_API_URL:-https://hp-os-bio-fix.netlify.app/api/orders}
payload=$(curl -fsS -H "x-hp-owner-token: $HP_OS_HOSTED_OWNER_TOKEN" "$HOSTED_API_URL/$order_id")
PAYLOAD="$payload" PYTHONPATH="$ROOT" python3 - <<'PY'
import json, os
import venture_db as db
payload=json.loads(os.environ['PAYLOAD'])
if not payload.get('ok'): raise SystemExit(payload.get('error','hosted order lookup failed'))
o=payload['order']; db.init_db()
with db.connect() as c: existing=c.execute('SELECT id FROM orders WHERE id=?',(o['id'],)).fetchone()
if not existing:
    db.create_order(o['product_id'],'customer_'+o['id'][-10:],o['quoted_amount_usd'],o['profile_url'],'hosted-intake',os.environ.get('HP_OS_HOSTED_SANDBOX') == '1',o['customer_email'],o['target_audience'],o['preferred_tone'],o['additional_context'],o['consent_scope'],'1.0.0',o.get('referral_source','direct'),o['id'])
print(json.dumps({'ok':True,'order_id':o['id'],'payment_status':o['payment_status'],'order_status':o['order_status'],'referral_source':o.get('referral_source','direct'),'sandbox':os.environ.get('HP_OS_HOSTED_SANDBOX') == '1'}))
PY

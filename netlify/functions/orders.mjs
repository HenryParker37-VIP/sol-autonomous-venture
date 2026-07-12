import { getStore } from "@netlify/blobs";

const store = getStore({ name: "hp-os-orders", consistency: "strong" });
const PAYPAL_URL = "https://www.paypal.me/PARKERHENRY304/5USD";
const PRICE_USD = 5;
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
function validEmail(value) { return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(value || "")); }
function validUrl(value) { return /^https?:\/\//.test(String(value || "")); }

export default async (request, context) => {
  const id = context.params?.id;
  if (request.method === "GET" && id) {
    const supplied = request.headers.get("x-hp-owner-token") || "";
    const expected = globalThis.Netlify?.env?.get("HOSTED_OWNER_TOKEN") || process.env.HOSTED_OWNER_TOKEN || "";
    if (!expected || supplied !== expected) return json({ ok: false, error: "owner authentication required" }, 401);
    const order = await store.get(id, { type: "json" });
    return order ? json({ ok: true, order }) : json({ ok: false, error: "order not found" }, 404);
  }
  if (request.method !== "POST" || id) return json({ ok: false, error: "method not allowed" }, 405);
  let body;
  try { body = await request.json(); } catch { return json({ ok: false, error: "valid JSON is required" }, 400); }
  const required = ["customer_email", "profile_url", "target_audience", "preferred_tone", "consent_scope"];
  const missing = required.filter((key) => !String(body[key] || "").trim());
  if (missing.length) return json({ ok: false, error: `missing required fields: ${missing.join(", ")}` }, 400);
  if (!validEmail(body.customer_email)) return json({ ok: false, error: "invalid customer email" }, 400);
  if (!validUrl(body.profile_url)) return json({ ok: false, error: "profile URL must be public http(s)" }, 400);
  const now = new Date().toISOString();
  const order = { id: `ord_live_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`, product_id: "prod-bio-profile-fix", quoted_amount_usd: PRICE_USD, payment_status: "UNVERIFIED", order_status: "AWAITING_PAYMENT", delivery_status: "NOT_STARTED", customer_email: String(body.customer_email).trim(), profile_url: String(body.profile_url).trim(), target_audience: String(body.target_audience).trim(), preferred_tone: String(body.preferred_tone).trim(), additional_context: String(body.additional_context || "").trim(), consent_scope: String(body.consent_scope).trim(), referral_source: String(body.referral_source || "direct").trim(), created_at: now, updated_at: now, source: "netlify-hosted-intake" };
  await store.setJSON(order.id, order);
  return json({ ok: true, order_id: order.id, price_usd: PRICE_USD, payment_state: order.payment_status, payment_url: PAYPAL_URL, confirmation_url: `/order-confirmation.html?order_id=${encodeURIComponent(order.id)}`, payment_instruction: `Pay via PayPal and include order ID ${order.id} in the PayPal note/reference. The owner maps that reference before work starts.` }, 201);
};

export const config = { path: ["/api/orders", "/api/orders/:id"], method: ["GET", "POST"] };

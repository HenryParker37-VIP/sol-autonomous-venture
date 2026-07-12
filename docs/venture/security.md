# Security and compliance

- No secrets, cookies, passwords, API keys, or private payment records are stored by the app.
- The PayPal value in `config/venture.json` is a public payment URL only.
- Publishing and outreach are disabled by default and must be enabled deliberately.
- The server binds to `127.0.0.1`, not all interfaces.
- The database does not store full customer names by default; orders use anonymous identifiers.
- Payment confirmation is an owner-only operation and is never inferred from a screenshot, a browser tab, or a sandbox event.
- Sandbox events are labelled and excluded from live revenue.
- No paid tools, advertisements, subscriptions, or purchases are part of the default flow.
- Public posts, comments, and DMs remain manually reviewed and submitted.
- Emergency stop sets a persisted control and blocks guarded payment/publishing operations.

# Free deployment

The current public landing page is available through the automatically configured GitHub Pages channel at:

`https://henryparker37-vip.github.io/sol-autonomous-venture/`

## Manual GitHub Pages

1. Create or open a GitHub repository.
2. Put the static landing page at `docs/index.html`.
3. In repository Settings, open Pages, choose the `main` branch and `/docs` folder.
4. Wait for the Pages build, then copy the URL shown by GitHub.

## CLI when already logged in

```bash
gh repo create hp-os-sol-venture --public --source . --remote origin --push
```

For a Pages site, keep a copy at `docs/index.html`, then enable Pages in repository settings. Do not put the SQLite database, buyer workspaces, logs with personal data, or local dashboard on a public static host.

## Test after deploy

- Open the URL in a private window.
- Confirm the $5 price and PayPal button are visible.
- Click the button and confirm it opens the expected public PayPal page.
- Confirm the after-payment instructions request the profile link, context, and receipt/order email.
- Check the page at a narrow mobile width.
- Confirm no `PAYPAL_LINK_HERE`, secrets, local paths, or fake claims appear.

## Persistent public intake option

The live deployment is `https://hp-os-bio-fix.netlify.app`. It serves `docs/` plus `netlify/functions/orders.mjs`. The function creates server-side order IDs and stores order JSON in the site-scoped Netlify Blobs store `hp-os-orders`. The public endpoint is `https://hp-os-bio-fix.netlify.app/api/orders`; the public intake is `https://hp-os-bio-fix.netlify.app/intake.html`. Owner lookup requires the private `HOSTED_OWNER_TOKEN`; use `scripts/sync-hosted-order.sh` to mirror a confirmed order into the local SQLite database. GitHub Pages remains the discovery/landing channel, while Netlify is the transaction backend.

Replace local links in `marketing/final-ready-to-post.md` and `marketing/live-links.md` with the copied live URL. Review every draft manually before posting.

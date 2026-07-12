# HP OS SOL Autonomous Venture Engine

This repository is a local, inspectable venture control center for a seven-day experiment to earn at least USD 5 in verified external revenue with a small, honest digital service.

## Current offer

**$5 Bio Fix + Pinned Hook Pack** for creators, freelancers, students, coaches, and small businesses.

The buyer sends one public profile link and a little context. Delivery within 24 hours includes:

- 3 rewritten bios
- 3 pinned-post hooks
- 5 improvement notes
- 1 small revision

Payment is owner-confirmed manually. Public posting, comments, DMs, and payment confirmation remain human-approved actions.

## Run it

```bash
./scripts/start-venture.sh
```

Then open `http://127.0.0.1:7100/venture`.

Run the real persistence and recovery test with:

```bash
./scripts/run-sandbox.sh
```

Create a real unpaid order with `./scripts/create-order.sh`; after checking PayPal manually, record the owner-only decision with `./scripts/confirm-payment.sh`. Run internal queued work with `./scripts/run-worker.sh --once`.

Run the fast checks with:

```bash
./scripts/check-all.sh
```

The app uses only Python's standard library and SQLite. Local operation stops if this Mac sleeps, shuts down, loses network access, or the worker process stops; it is not labelled 24/7 unless moved to an always-on runtime.

## Safety boundary

The engine can prepare drafts, record actions, run free local publishing checks, and simulate the full order flow. It does not auto-send DMs, auto-submit public posts, expose credentials, confirm payments, spend money, or count sandbox revenue as real revenue.

Read [docs/venture/current-state.md](docs/venture/current-state.md) for the latest evidence-backed status.

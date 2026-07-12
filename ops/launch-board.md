# Launch board

- [ ] Start local control center: `./scripts/start-venture.sh`
- [ ] Open `landing-page/index.html` and test the PayPal button
- [ ] Confirm the public URL is reachable
- [ ] Review `ops/posting-targets.md`
- [ ] Manually approve one post and up to ten relevant conversations
- [ ] Log each action in `ops/tracking.md`
- [ ] Ask the owner to confirm PayPal payment before delivery
- [ ] Run `scripts/new-buyer.sh` after confirmation

Guardrails: no spam, no mass-DM, no auto-submit, no unverified payment, and no invented results.

## Seven-day commercial thresholds

- Minimum relevant impressions: 100
- Minimum landing visits: 30
- Minimum CTA clicks: 10
- Minimum form starts: 10
- Minimum completed forms: 3
- Maximum time without a qualified lead: 48 hours
- Maximum operating cost: $3
- Pivot condition: 100 relevant impressions with fewer than 3 visits, or 30 visits with no form start, or 10 form starts with no completed order.
- Termination condition: seven days complete, budget ceiling reached, emergency stop, or a confirmed payment objective reached.

These are decision thresholds, not claimed results. Record only observed numbers in `ops/tracking.md` and the dashboard. On each scheduled pass, compare channels, headline clarity, sample choice, price, and intake friction; continue the experiment when no buyer exists.

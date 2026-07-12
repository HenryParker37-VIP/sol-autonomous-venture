# LinkedIn acquisition schedule

The default acquisition timezone is `America/New_York`.

## Posting rules

- Publish 3-5 LinkedIn posts per week.
- Never publish more than one post in any rolling 24-hour period.
- Prefer Tuesday through Thursday, 09:00-12:00 Eastern.
- Use 13:00-15:00 Eastern only when recorded analytics support the test.
- Do not publish immediately because a post performs well.
- After every post, wait approximately five hours before reading analytics.

## Five-hour review

Record observed values separately for impressions, reactions, comments, reposts, profile views, referral visits, CTA clicks, form starts, orders, verified payments, and sales. Unknown values remain unknown; they are never inferred from reactions or impressions.

Then identify the bottleneck:

- Impressions without visits: discovery or targeting.
- Visits without CTA clicks: message or CTA clarity.
- CTA clicks without form starts: intake friction.
- Form starts without orders: payment or trust friction.
- Orders without verified payment: payment mapping or confirmation friction.

Between scheduled posts, use only relevant, personalized public replies. Do not mass-comment, repeat identical text, send DMs without separate approval, or force the paid offer into a conversation.

The current schedule and next eligible window are persisted in `config/acquisition.json` and exposed through the dashboard acquisition snapshot.

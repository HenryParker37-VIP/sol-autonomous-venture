# Venture architecture

The engine is a local Python standard-library service backed by SQLite. `venture_db.py` owns persistence, guarded transitions, event logging, cost records, and the order/payment boundary. `venture_server.py` exposes a read-heavy dashboard API on `127.0.0.1:7100`.

The registry contains 12 named agents, but they are permission-scoped records and task owners, not claims of independent model processes. A worker can be added later without changing the schema. This keeps the current system honest and restartable.

Core entities: venture state, milestones, agents, tasks, opportunities, products, leads, orders, publications, events, costs, and controls log. Every meaningful transition records UTC time, actor, result, risk, and structured details.

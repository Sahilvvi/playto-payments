# EXPLAINER.md — Playto Payout Engine

---

## 1. The Ledger

### Balance calculation query

```python
# merchants/models.py — Merchant.get_balance()

ledger = LedgerEntry.objects.filter(merchant=self).aggregate(
    credits=Coalesce(
        Sum("amount_paise", filter=Q(entry_type=LedgerEntry.CREDIT)),
        Value(0),
        output_field=BigIntegerField(),
    ),
    debits=Coalesce(
        Sum("amount_paise", filter=Q(entry_type=LedgerEntry.DEBIT)),
        Value(0),
        output_field=BigIntegerField(),
    ),
)

held = Payout.objects.filter(
    merchant=self,
    status__in=[Payout.PENDING, Payout.PROCESSING],
).aggregate(
    total=Coalesce(Sum("amount_paise"), Value(0), output_field=BigIntegerField())
)["total"]

available_balance = (ledger["credits"] - ledger["debits"]) - held
```

This produces a single SQL `SELECT … SUM(CASE WHEN …)` query — PostgreSQL/SQLite sums directly in the DB. There is no Python arithmetic on fetched rows.

### The invariant (mathematically)

```
available_balance = SUM(credits) - SUM(debits) - SUM(held_amount)

where held_amount = SUM(payout.amount_paise) for status IN ('pending', 'processing')
```

**SQL equivalent:**
```sql
SELECT
  (SELECT COALESCE(SUM(amount_paise), 0)
   FROM merchants_ledgerentry
   WHERE merchant_id = $1 AND entry_type = 'credit')
  -
  (SELECT COALESCE(SUM(amount_paise), 0)
   FROM merchants_ledgerentry
   WHERE merchant_id = $1 AND entry_type = 'debit')
  -
  (SELECT COALESCE(SUM(amount_paise), 0)
   FROM payouts_payout
   WHERE merchant_id = $1 AND status IN ('pending', 'processing'))
AS available_balance;
```

### Why no drift occurs

**Credits and debits instead of a running balance field:** A running balance field requires every concurrent write to read-then-update it. That is a classic check-then-act race condition requiring application-level serialisation or optimistic locking. Both introduce failure modes.

With an append-only ledger, the authoritative balance is always the aggregate of immutable rows. A bug cannot corrupt history — it can only leave a wrong entry, which is auditable and reversible.

**When is a debit entry created?** Only when a payout reaches `completed` status, inside the same `transaction.atomic()` block as the state transition. If the state update succeeds but the ledger write fails, the transaction rolls back atomically. There is no state where a payout is `completed` without a corresponding debit entry.

**What about failed payouts?** No debit entry is ever created for them. The `held` query filters on `status IN ('pending', 'processing')`. A failed payout falls out of that filter automatically — its amount flows back into `available_balance` with zero additional writes.

### DB-level ledger constraint

```python
# merchants/models.py — LedgerEntry.Meta
constraints = [
    # Amount must always be positive — blocks zero/negative entries at DB level
    CheckConstraint(check=Q(amount_paise__gt=0), name="ledgerentry_positive_amount"),

    # Exactly one DEBIT per payout — partial unique index blocks double-debit
    # even if application code calls _complete_payout twice
    UniqueConstraint(
        fields=["payout"],
        condition=Q(entry_type="debit"),
        name="unique_debit_per_payout",
    ),
]
```

These constraints are the last line of defense. Even if application code has a bug, the database rejects the write and the transaction rolls back.

### How ledger handles rollback

Rollback is a non-event: the ledger is append-only and immutable. A crashed transaction simply leaves no trace — no entry was committed. There is no compensating transaction needed. This is why we use append-only debits-on-completion rather than a mutable balance column.

---

## 2. The Lock

### Exact code that prevents two concurrent payouts from overdrawing

```python
# payouts/views.py — create_payout()

with transaction.atomic():
    # --- THE LOCK ---
    merchant = Merchant.objects.select_for_update().get(id=merchant.id)

    # --- IDEMPOTENCY CHECK (inside the lock) ---
    existing = Payout.objects.filter(
        merchant=merchant, idempotency_key=idempotency_key
    ).first()
    if existing:
        ...return existing payout (HTTP 200)...

    # --- BALANCE CHECK (DB-level aggregation, same transaction) ---
    balance = merchant.get_balance()
    available = balance["available_balance_paise"]

    if available < amount_paise:
        return Response({"error": "Insufficient funds"}, status=400)

    # --- CREATE PAYOUT ---
    payout = Payout.objects.create(...)
```

### The database primitive

`SELECT ... FOR UPDATE` on the `Merchant` row (PostgreSQL row-level exclusive lock).

When Request A calls `Merchant.objects.select_for_update().get(id=X)`, PostgreSQL acquires an **exclusive row lock** on that merchant's row for the duration of the transaction. Request B, arriving simultaneously with the same merchant ID, blocks at the same line until Request A's transaction commits or rolls back.

**The scenario (₹100 balance, two ₹60 requests):**

1. Request A acquires the merchant lock.
2. Request B issues `SELECT ... FOR UPDATE` — **blocks at the DB level**.
3. Request A aggregates the balance: 10,000 paise available. 6,000 ≤ 10,000 → creates payout. Commits.
4. Request B's lock is released. It now runs the same aggregation. Available = 10,000 − 6,000 (held by A's pending payout) = 4,000. 6,000 > 4,000 → **400 Insufficient Funds**.

### Why the race condition is impossible

The check-then-create is atomic at the **database level**, not the Python level. The `SELECT FOR UPDATE` makes it impossible for two concurrent requests to both pass the balance check for the same merchant:

- Without the lock: Thread A reads balance → Thread B reads balance → Thread A creates payout → Thread B creates payout → **overdraft**.
- With the lock: Thread A acquires lock → Thread B blocks → Thread A creates payout, commits → Thread B unblocks, reads **updated** balance → Thread B is rejected.

**Why not Python-level locking?** A `threading.Lock()` only works within a single process. Under Gunicorn with multiple workers, the lock lives in each worker's memory — different workers never contend. Only a database-level lock is visible across all processes and connections.

---

## 3. The Idempotency

### Table schema

```python
class Payout(models.Model):
    idempotency_key = models.UUIDField(db_index=True)
    idempotency_key_created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("merchant", "idempotency_key")]
```

The composite unique constraint (`merchant_id`, `idempotency_key`) is enforced at the DB level. The same UUID from two different merchants creates two independent payouts.

### Request lifecycle

**Case A — First request:**
```
lock merchant → filter(idempotency_key) → not found → create payout → return 201
```

**Case B — Duplicate after success (same key, payout already completed):**
```
lock merchant → filter(idempotency_key) → found, not expired → return 200 (existing payout)
```
The client gets the exact same payout object, including its `completed` status. No second payout is created.

**Case C — Duplicate during in-flight request:**
```
Request A: lock merchant → not found → [creating payout...]
Request B: select_for_update → BLOCKS
Request A: payout created → commit
Request B: unblocked → filter(idempotency_key) → found → return 200
```
Request B is forced to wait by the merchant lock until A's transaction commits. B then finds A's payout and returns it. There is **no window** where both requests can miss each other's row.

**Case D — Expired key (> 24 hours):**
```
lock merchant → filter(idempotency_key) → found, expired → return 409
```
Client generates a new UUID and retries.

### Detection logic

```python
existing = Payout.objects.filter(
    merchant=merchant, idempotency_key=idempotency_key
).first()

if existing:
    if existing.idempotency_key_expired:   # > 24h since creation
        return Response({"error": "Key expired"}, status=409)
    return Response(PayoutSerializer(existing).data, status=200)
```

---

## 4. The State Machine

### Legal transitions

```
pending  →  processing  →  completed
                        →  failed
```

All other transitions are **illegal**. The state machine lives in `payouts/state_machine.py`:

```python
VALID_TRANSITIONS: dict[str, list[str]] = {
    "pending":    ["processing"],
    "processing": ["completed", "failed"],
}

def assert_transition_allowed(current_status: str, next_status: str) -> None:
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if next_status not in allowed:
        raise InvalidStateTransition(current_status, next_status)
```

### Enforcement in every write path

Every status update goes through `assert_transition_allowed` inside a `SELECT FOR UPDATE` transaction:

```python
# payouts/tasks.py — _complete_payout()
def _complete_payout(payout_id: str) -> None:
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)

        try:
            assert_transition_allowed(payout.status, Payout.COMPLETED)
        except InvalidStateTransition:
            logger.warning("invalid transition %s -> completed", payout.status)
            return  # ← no-op; no state change, no ledger entry

        payout.status = Payout.COMPLETED
        payout.save(update_fields=["status", "updated_at"])
        LedgerEntry.objects.create(...)   # debit, same transaction
```

The same guard exists in `_fail_payout`. The `select_for_update` on the **payout row** prevents two concurrent workers from both passing the state check — the second one finds the status already changed and exits silently.

### Blocked transitions (verified by test_state_machine.py)

| Transition | Blocked? | Why |
|---|---|---|
| `completed → pending` | ✅ | Not in VALID_TRANSITIONS |
| `completed → processing` | ✅ | Not in VALID_TRANSITIONS |
| `completed → failed` | ✅ | Would lose the debit entry |
| `failed → completed` | ✅ | Would create debit without re-processing |
| `failed → pending` | ✅ | Not in VALID_TRANSITIONS |
| `pending → completed` | ✅ | Must go through processing |

---

## 5. Transaction Isolation Level

### What we use and why

The Django default for PostgreSQL is **READ COMMITTED** (`ISOLATION LEVEL READ COMMITTED`). This is sufficient because:

| Anomaly | Present in RC? | How we prevent it |
|---|---|---|
| Dirty read | ❌ | RC never reads uncommitted data |
| Lost update | ⚠️ Yes without locks | `SELECT FOR UPDATE` serialises writes per merchant |
| Phantom read | ⚠️ Yes | `SELECT FOR UPDATE` on the merchant row serialises the entire check-create sequence |

**Could we use REPEATABLE READ or SERIALIZABLE?**

Yes, but unnecessary overhead:
- **REPEATABLE READ** would prevent phantom reads but still needs explicit locks in our concurrent-write scenario.
- **SERIALIZABLE** aborts conflicting transactions automatically, but requires retry logic at the application level — the same retry we already implement for SQLite lock errors.

**The `SELECT FOR UPDATE` makes READ COMMITTED behave like SERIALIZABLE for our specific access pattern** (all writes per merchant are serialised through the lock), at a fraction of the overhead.

---

## 6. Failure Simulation

### DB failure: transaction crash mid-update

`_complete_payout` writes two things atomically: `payout.status = COMPLETED` and a `LedgerEntry(DEBIT)`. Both are inside a single `transaction.atomic()`.

If the process crashes after the `payout.save()` but before `LedgerEntry.objects.create()`:
- PostgreSQL rolls back the entire transaction on connection loss.
- The payout stays in `PROCESSING`, the debit entry is never written.
- `check_and_retry_stuck_payouts` detects the stuck payout and re-queues it after the backoff threshold.

**Verified by `test_complete_payout_rolls_back_if_ledger_write_fails`** — monkey-patches `LedgerEntry.objects.create` to raise `RuntimeError` mid-transaction, confirms the payout stays in PROCESSING.

### Worker failure: crash after setting status = PROCESSING

The `process_payout` task sets `status = PROCESSING` inside its own transaction, then calls the bank simulation outside any transaction. If the worker crashes after that:
- The payout remains stuck in `PROCESSING`.
- `check_and_retry_stuck_payouts` (runs every 10s) detects payouts where `processing_started_at < now - threshold` and re-queues them.
- Exponential backoff: 30s / 60s / 120s per attempt.
- After MAX_ATTEMPTS (3), the payout is moved to FAILED and funds are released.

### Duplicate worker execution

Two Celery workers race to process the same payout. Both call `_complete_payout`:

1. Worker A: `SELECT FOR UPDATE` on payout → acquires lock → `assert_transition_allowed("processing", "completed")` passes → writes COMPLETED + DEBIT entry → commits.
2. Worker B: `SELECT FOR UPDATE` → waits → acquired after A commits → status is now `"completed"` → `assert_transition_allowed("completed", "completed")` → raises `InvalidStateTransition` → function returns early, no second DEBIT entry.

The `unique_debit_per_payout` DB constraint is the final backstop: even if the state machine check is somehow bypassed, the DB rejects the second DEBIT entry with a unique constraint violation, rolling back the transaction.

**Verified by `test_second_complete_is_noop`.**

---

## 7. The AI Audit

### What AI gave me (wrong)

When I asked an AI to generate the balance calculation for the payout creation view:

```python
# AI-generated — WRONG: two critical bugs

merchant = Merchant.objects.get(id=merchant_id)
balance = merchant.available_balance  # ← denormalised cached field

if balance < amount_paise:
    raise InsufficientFunds()

merchant.available_balance -= amount_paise  # ← Python arithmetic on a stale read
merchant.save()

payout = Payout.objects.create(...)
```

**Bug 1 — Check-then-act race condition (TOCTOU).**
Between the `GET` and the `UPDATE`, another request can read the same stale `available_balance` and both pass the check. With ₹100 and two simultaneous ₹60 requests: both read 10,000, both pass `10,000 >= 6,000`, both decrement to 4,000, both save — effectively overdrawing to −2,000.

The AI knew to check balance but did not wrap the read-check-write in a database-level lock.

**Bug 2 — Denormalised balance field (two sources of truth).**
`available_balance` column and the ledger are separate. Any bug that writes a ledger entry without updating the field silently corrupts balance. An append-only ledger with no cached column cannot drift.

**Bug 3 — Python arithmetic instead of DB aggregation.**
`merchant.available_balance -= amount_paise` is arithmetic on a Python integer, not a SQL expression. Under concurrent load two reads return the same value; both decrements overwrite each other.

### What I replaced it with

```python
with transaction.atomic():
    # Row-level lock — serialises all payout creation for this merchant
    merchant = Merchant.objects.select_for_update().get(id=merchant.id)

    # Balance derived entirely from the ledger in the same locked transaction
    balance = merchant.get_balance()   # pure SUM() in DB, no Python arithmetic
    available = balance["available_balance_paise"]

    if available < amount_paise:
        return Response({"error": "Insufficient funds"}, status=400)

    payout = Payout.objects.create(...)   # held funds = new pending payout row
```

No balance column to drift. No race between read and write. Lock makes check-then-create atomic at DB level.

---

## 8. Edge Cases

### 100 parallel requests, same merchant

With `SELECT FOR UPDATE` all 100 requests queue behind the merchant row lock. Each request sees the balance updated by every request that committed before it. Only requests that find `available >= amount` succeed. No overdraft is possible regardless of concurrency.

**Lock contention cost:** Under high concurrency, requests wait in a queue. The queue depth equals the number of concurrent requests. For a write-heavy API this can become a bottleneck. Production mitigation: shard merchants across database nodes, or use optimistic concurrency (version column + retry on conflict). For the current scale this is not needed.

### Same idempotency key across merchants

Explicitly tested in `test_keys_are_scoped_per_merchant`. The `unique_together = [("merchant", "idempotency_key")]` constraint is **per merchant** — the same UUID from two merchants creates two independent payouts. This is correct: idempotency is per-client, not global.

### Key replay attack

An attacker who intercepts a merchant's idempotency key and replays it as a different merchant gets:
- A fresh payout for their own merchant (different `merchant_id` → different key scope).
- They cannot access or affect the original merchant's payout.

### Duplicate debit entry (ledger corruption attempt)

The `unique_debit_per_payout` partial unique constraint at the DB level blocks a second `DEBIT` entry for the same `payout_id`. Even a direct SQL `INSERT` against the DB would fail with a unique constraint violation.

### Negative balance attempt

The application layer rejects `available < amount_paise` before creating a payout. But even if that check were bypassed, the ledger invariant cannot go negative through normal operations: `available = credits - debits - held`. Debits are only written on `completed` payouts (which were checked at creation). The only way to get a negative available balance is to create a payout that was not checked — which is blocked by the lock+check sequence.

---

## 9. Self-Critique: 3 Ways This System Can Still Fail

### Failure Mode 1: Celery broker down — payout created but never processed

**Scenario:** The `transaction.atomic()` commits (payout created in DB), then `process_payout.delay()` fails because RabbitMQ/Redis is unreachable. The payout stays in `PENDING` forever.

**Current mitigation:** `pickup_pending_payouts` sweeps for `PENDING` payouts periodically.

**Production fix:** Use Celery's `transaction.on_commit` hook to enqueue the task only after the DB transaction commits, and configure Celery with a persistent broker (Redis AOF or RabbitMQ with durable queues + publisher confirms). Add a database-backed task queue as a fallback (e.g., `django-celery-results`).

### Failure Mode 2: Clock skew breaks stuck-payout detection

**Scenario:** `check_and_retry_stuck_payouts` compares `processing_started_at` (set on the DB server) with `timezone.now()` (evaluated on the Celery worker). If the Celery worker clock is ahead of the DB server clock, `elapsed` is overestimated — payouts are retried too early. If behind, they're retried too late or never.

**Production fix:** Always read `NOW()` from PostgreSQL, not from `timezone.now()` in Python:
```sql
SELECT id, attempt_count,
       EXTRACT(EPOCH FROM (NOW() - processing_started_at)) AS elapsed_seconds
FROM payouts_payout
WHERE status = 'processing'
AND (NOW() - processing_started_at) > INTERVAL '30 seconds'
```

### Failure Mode 3: `select_for_update` does not work across read replicas

**Scenario:** A read replica is added and the balance check accidentally hits the replica (stale data). `select_for_update()` is a no-op on a replica — it returns stale balance data and the lock is not acquired on the primary.

**Production fix:** Ensure `get_balance()` is always called with a connection pinned to the primary (`using="default"` in Django's multi-DB setup). Add a read routing guard that routes `SELECT FOR UPDATE` queries to the primary only. Test with a canary assertion: after acquiring the lock, verify the `merchant.id` was read from the primary by checking a write timestamp.

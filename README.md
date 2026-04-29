# Playto Payout Engine

Cross-border payout infrastructure for Indian merchants. Merchants accumulate balance from international customer payments (credits) and withdraw to Indian bank accounts (payouts).

## Quick Start (Docker — recommended)

```bash
git clone <repo>
cd playto-payout
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api/v1/
- Django Admin: http://localhost:8000/admin/ (User: `admin` | Pass: `admin123`)

---

## Local Development

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Node.js 20+

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your DB and Redis URLs

python manage.py makemigrations merchants payouts
python manage.py migrate
python manage.py seed             # Seeds 3 merchants with credit history
python manage.py runserver
```

### Celery Worker (separate terminal)

```bash
cd backend
source venv/bin/activate
celery -A playto worker --loglevel=info
```

### Celery Beat Scheduler (separate terminal)

```bash
cd backend
source venv/bin/activate
python manage.py migrate          # ensures django_celery_beat tables exist
celery -A playto beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

---

## Running Tests

```bash
cd backend
python manage.py test tests --verbosity=2
```

The concurrency test uses `TransactionTestCase` (real commits, not rolled-back savepoints) so it requires a real PostgreSQL connection — not SQLite.

---

## API Reference

All payout endpoints require:
- `X-Merchant-ID: <uuid>` — which merchant is acting
- `Idempotency-Key: <uuid>` — for `POST /api/v1/payouts/` only

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/merchants/` | List all merchants |
| GET | `/api/v1/merchants/{id}/balance/` | Balance breakdown |
| GET | `/api/v1/merchants/{id}/ledger/` | Credit/debit history |
| POST | `/api/v1/payouts/` | Create payout |
| GET | `/api/v1/payouts/list/` | List payouts for merchant |
| GET | `/api/v1/payouts/{id}/` | Get single payout |

### Create Payout

```http
POST /api/v1/payouts/
X-Merchant-ID: <merchant-uuid>
Idempotency-Key: <uuid>
Content-Type: application/json

{
  "amount_paise": 50000,
  "bank_account_id": "<bank-account-uuid>"
}
```

**Responses**
- `201 Created` — new payout created
- `200 OK` — duplicate idempotency key, returns existing payout
- `400 Bad Request` — insufficient funds or validation error
- `409 Conflict` — idempotency key expired (>24h)

---

## Architecture Notes

See [EXPLAINER.md](./EXPLAINER.md) for the detailed technical deep-dive on:
- Why ledger entries are credits/debits (not a balance field)
- The exact SELECT FOR UPDATE lock that prevents overdrawing
- Idempotency key scoping and in-flight handling
- State machine enforcement
- AI audit

---

## Seed Data

The seed command creates 3 merchants with synchronized ledger and payout history:

| Merchant | Total Credits | Available Balance |
|----------|---------------|-------------------|
| Arjun Designs | ₹52,500.00 | ₹32,500.00 |
| Priya Writes | ₹24,500.00 | ₹20,000.00 |
| Dev Studio Co | ₹97,000.00 | ₹70,000.00 |

**Admin Credentials**: `admin` / `admin123`

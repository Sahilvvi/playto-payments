const BASE = "/api/v1";

async function request(path, options = {}) {
  const { headers: callerHeaders = {}, ...restOptions } = options;
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...callerHeaders },
    ...restOptions,
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

export const api = {
  getMerchants: () => request("/merchants/"),

  getBalance: (merchantId) => request(`/merchants/${merchantId}/balance/`),

  getLedger: (merchantId) => request(`/merchants/${merchantId}/ledger/`),

  getPayouts: (merchantId) =>
    request("/payouts/list/", {
      headers: { "X-Merchant-ID": merchantId },
    }),

  createPayout: (merchantId, idempotencyKey, body) =>
    request("/payouts/", {
      method: "POST",
      headers: {
        "X-Merchant-ID": merchantId,
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(body),
    }),
};

export function formatINR(paise) {
  const rupees = paise / 100;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
  }).format(rupees);
}

export function generateUUID() {
  return crypto.randomUUID();
}

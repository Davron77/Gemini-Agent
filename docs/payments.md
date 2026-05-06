# Payments — Frontend Guide

This document describes the two payment-related endpoints the frontend integrates with. Click is the only payment provider currently in use.

There are two things a user can do with money:

1. **Buy credits** — pick a tier, pay, get credits.
2. **Activate a service** — pay a flat fee to publish one of their own services so the public can see it.

Both flows look the same to the frontend:

```
1. Frontend calls our endpoint with a Bearer token
2. Backend returns a payment_url
3. Frontend redirects the user to payment_url
4. User pays inside Click
5. Click redirects the user back to FRONTEND_SUCCESS_URL
6. Frontend re-fetches the relevant resource to show the updated state
```

> ⚠ The redirect-back is **not** a guarantee of success. The user may have closed the tab, cancelled, or the bank may have declined. Always re-fetch state from the API before showing a success screen.

---

## 1. Pricing

| Action | What the user pays | What they get |
|---|---|---|
| Buy `bronze` | ~$20 (`241,000` so'm) | **5 credits** |
| Buy `silver` | ~$35 (`422,000` so'm) | **10 credits** |
| Buy `gold` | ~$90 (`1,085,000` so'm) | **30 credits** |
| Activate one service | ~$5 (`60,000` so'm) | That service goes live |

> The amounts shown are in **tiyin** (1 so'm = 100 tiyin) — that's what Click bills the user. The `user.balance` field, on the other hand, is in **credits** (5/10/30). Don't confuse the two when showing them in the UI.

---

## 2. Endpoints

Both endpoints require the user's `Authorization: Bearer <access_token>` header.

### 2.1 `POST /api/v1/payments/buy-credit`

Start a credit purchase.

**Request body:**
```json
{ "tier": "bronze" }
```

`tier` must be exactly one of `"bronze"`, `"silver"`, `"gold"`.

**Success response (200):**
```json
{
  "order_id": 42,
  "invoice_id": 17,
  "payment_url": "https://my.click.uz/services/pay?service_id=…&merchant_id=…&transaction_param=17"
}
```

**Error responses:**

| Code | Detail | When |
|---|---|---|
| `400` | `"Invalid tier"` | Tier is not bronze/silver/gold |
| `401` | `"Not authenticated"` / `"Invalid or expired token"` | Token missing or bad |

**What to do with the response:** redirect the user to `payment_url`. Don't try to render the Click form yourself.

---

### 2.2 `POST /api/v1/payments/activate-service/{service_id}`

Start a payment to activate (publish) one of your own services.

**Request:** no body. `service_id` is in the URL.

```http
POST /api/v1/payments/activate-service/15
Authorization: Bearer <token>
```

**Success response (200):**
```json
{
  "order_id": 42,
  "invoice_id": 18,
  "payment_url": "https://my.click.uz/services/pay?service_id=…&merchant_id=…&transaction_param=18"
}
```

**Error responses:**

| Code | Detail | When |
|---|---|---|
| `404` | `"Service not found"` | No service with that id, or it's been deleted |
| `403` | `"You can only activate your own services"` | The service's owner ≠ the authenticated user |
| `400` | `"Service is already active"` | Service status is already `active`. Hide the activate button in the UI in this case. |
| `401` | `"Not authenticated"` / `"Invalid or expired token"` | Token missing or bad |

**What to do with the response:** redirect the user to `payment_url`.

---

## 3. After the user comes back from Click

Click sends the user back to the configured success URL whether the payment was completed, cancelled, or failed. **The URL alone tells you nothing.** Confirm via the API:

- After **buy-credit** → re-fetch `/api/v1/users/me` and show the new `balance` (in credits).
- After **activate-service** → re-fetch `/api/v1/services/{id}` and check `status === "active"`.

If the state hasn't updated yet (the webhook usually takes a second or two), poll once or twice with a short delay before showing an error.

---

## 4. Suggested UI rules

### Buy credits screen
- Show a card per tier with the so'm/USD price + the credits awarded.
- On click: `POST /payments/buy-credit { tier }` → redirect to `payment_url`.
- After return, fetch `/users/me` and show the new `balance`.

### Service detail / dashboard
- If `service.status !== "active"` AND the viewer is the service's owner → show **"Activate for $5"** button.
- On click: `POST /payments/activate-service/{id}` → redirect to `payment_url`.
- If status is already `"active"` → hide the activation button. (The API will reject with `400 "Service is already active"` if you call it anyway.)
- After return, re-fetch the service and check `status`.

### Error handling
- `403` on activate-service → user is trying to activate someone else's service. Show "You can only activate your own services" and hide the button.
- `400 "Service is already active"` → race condition with another tab/device; just refresh the service.

---

## 5. TypeScript example

```ts
// Buy a credit pack
async function buyCredit(tier: "bronze" | "silver" | "gold") {
  const { payment_url } = await api.post("/payments/buy-credit", { tier })
    .then(r => r.data);
  window.location.href = payment_url;
}

// Activate a service the current user owns
async function activateService(serviceId: number) {
  const { payment_url } = await api.post(`/payments/activate-service/${serviceId}`)
    .then(r => r.data);
  window.location.href = payment_url;
}

// After redirect-back from Click
async function onReturnFromClick() {
  // For credit purchases:
  const me = await api.get("/users/me").then(r => r.data);
  showBalance(me.balance);            // in credits

  // Or for service activation:
  const svc = await api.get(`/services/${serviceId}`).then(r => r.data);
  if (svc.status === "active") {
    showSuccess();
  } else {
    // webhook may not have fired yet — wait a bit, then retry
    setTimeout(onReturnFromClick, 2000);
  }
}
```

---

## 6. Quick reference

| Action | Method + path | Body | Auth |
|---|---|---|---|
| Buy credits | `POST /api/v1/payments/buy-credit` | `{ "tier": "bronze" \| "silver" \| "gold" }` | Bearer |
| Activate service | `POST /api/v1/payments/activate-service/{id}` | — | Bearer |

Both return `{ order_id, invoice_id, payment_url }`. Redirect to `payment_url`. Confirm success by re-fetching `/users/me` (balance) or `/services/{id}` (status).

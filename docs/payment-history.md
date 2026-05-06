# Payment History API

---

## 1. Name

`GET /api/v1/payments/history` — fetch the authenticated user's credit balance history (purchases and spendings).

---

## 2. Purpose

Shows a paginated, newest-first list of every change to the user's **credit balance**. Each row is one event — either credits added (they bought a pack) or credits spent (they activated a service).

Use this to render a "Transactions" / "History" tab where the user can see what happened to their balance, when, and why.

> **Credits, not money.** The number you display from this endpoint is in *credits* (integer, e.g. `5`, `30`, `-5`). The user paid the actual money in so'm via Click on a different endpoint. Don't put a currency symbol in the UI.

---

## 3. How to use

### Basic call

```ts
const res = await api.get("/payments/history?page=1&per_page=20");
const data = res.data; // PaymentHistoryList — see §5
```

### With filters

```ts
const params = new URLSearchParams({
  page: "1",
  per_page: "20",
  reason: "credit_purchase",        // optional
  date_from: "2026-01-01T00:00:00", // optional
  date_to:   "2026-04-30T23:59:59", // optional
});
const { data } = await api.get(`/payments/history?${params}`);
```

### Auth header (always required)

```http
Authorization: Bearer <access_token>
```

If the header is missing or the token is invalid, the request returns **401**. Handle this the same way you handle every other authenticated call (redirect to login).

---

## 4. Parameters

All parameters are sent as **query string**, not body. There is no request body.

### `page`

- **Type:** `number` (integer ≥ 1)
- **Required:** ❌ optional (default `1`)
- **Description:** Which page of results to return. The server splits the full result set into pages of `per_page` items; `page=1` is the first (newest) page, `page=2` is the next batch, and so on.
- **Example:** `2`

### `per_page`

- **Type:** `number` (integer, between `1` and `100`)
- **Required:** ❌ optional (default `20`)
- **Description:** How many rows you want in one page. The server caps this at 100 — sending `per_page=500` returns a `422` validation error. Use a small value (10–25) for normal lists; use a higher value only if you're rendering a "load all" view.
- **Example:** `20`

### `user_id`

- **Type:** `number` (integer)
- **Required:** ❌ optional. **Admin-only knob** — see Frontend Notes §6.
- **Description:** Whose history to fetch. Regular users **must not send this** (or must send their own id) — sending another user's id returns `403`. Admin / Super Admin users may pass any user's id, or omit this entirely to get the entire system's history.
- **Example:** `42`

### `reason`

- **Type:** `string` (enum — must be one of: `"credit_purchase"`, `"service_activation"`)
- **Required:** ❌ optional (default: no filter, returns all reasons)
- **Description:** Filters the list to only one type of event. Pass nothing to see everything. Sending a value the API doesn't know returns `422`.
  - `"credit_purchase"` → only the rows where the user *received* credits (bought a pack).
  - `"service_activation"` → only the rows where the user *spent* credits to publish a service.
- **Example:** `"credit_purchase"`

### `date_from`

- **Type:** `string` (ISO 8601 datetime, no timezone, server treats it as UTC)
- **Required:** ❌ optional
- **Description:** Inclusive lower bound. Only rows with `created_at >= date_from` are returned. Useful for "Last 30 days" / "This month" filters. If the user picks a date in your UI, send it as `YYYY-MM-DDT00:00:00`.
- **Example:** `"2026-01-01T00:00:00"`

### `date_to`

- **Type:** `string` (ISO 8601 datetime)
- **Required:** ❌ optional
- **Description:** Inclusive upper bound. Only rows with `created_at <= date_to` are returned. Pair with `date_from` for a date range. To include the entire end-day, send `YYYY-MM-DDT23:59:59`.
- **Example:** `"2026-04-30T23:59:59"`

---

## 5. Returns / Response

`200 OK`. The body always has the same shape, even when empty (it returns an empty `items` array, never a 404).

### Top-level (`PaymentHistoryList`)

| Field | Type | Description |
|---|---|---|
| `items` | `PaymentHistoryItem[]` | The page of rows. Length is **at most** `per_page`. May be `[]`. |
| `total` | `number` | How many rows match the filters in total — across **all** pages. Use this for "Showing X of Y" labels and to decide when to hide the pager. |
| `page` | `number` | Echo of the `page` you requested. |
| `per_page` | `number` | Echo of the `per_page` you requested. |
| `total_pages` | `number` | How many pages exist (server-computed: `ceil(total / per_page)`). When `total === 0`, this is `0` — render no pager. |

### Each row (`PaymentHistoryItem`)

| Field | Type | Description |
|---|---|---|
| `id` | `number` | Stable primary key. Use as React `key` and for dedupe across re-fetches. Never reused. |
| `amount` | `number` | **Signed** integer, in credits. **Positive** = credits added (incoming). **Negative** = credits removed (outgoing). The sign is the source of truth — don't infer it from `reason`. |
| `reason` | `string` enum | Why this row exists. One of `"credit_purchase"` (positive) or `"service_activation"` (negative). New values may appear later — always have a `default` branch. |
| `balance_before` | `number` | The user's `balance` (in credits) **just before** this transaction. |
| `balance_after` | `number` | The user's `balance` (in credits) **just after** this transaction. **Invariant:** `balance_after === balance_before + amount`. |
| `reference_type` | `string` enum | Which entity this row relates to. One of `"order"` (a credit-pack purchase order) or `"service"` (a service that got activated). Tells you which page to link to. |
| `reference_id` | `number` | The id of that entity. Combine with `reference_type` to build a link, e.g. `/services/${reference_id}`. |
| `created_at` | `string` | ISO datetime in UTC, **no timezone suffix** (e.g. `"2026-04-25T11:14:02"`). Parse with `new Date(item.created_at)` — JS will treat it as local time, so if you need UTC display, append `"Z"` first. |

### Example response

```json
{
  "items": [
    {
      "id": 312,
      "amount": 30,
      "reason": "credit_purchase",
      "balance_before": 5,
      "balance_after": 35,
      "reference_type": "order",
      "reference_id": 87,
      "created_at": "2026-04-25T11:14:02"
    },
    {
      "id": 311,
      "amount": -5,
      "reason": "service_activation",
      "balance_before": 10,
      "balance_after": 5,
      "reference_type": "service",
      "reference_id": 22,
      "created_at": "2026-04-22T18:01:47"
    }
  ],
  "total": 47,
  "page": 1,
  "per_page": 20,
  "total_pages": 3
}
```

### Empty response

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "per_page": 20,
  "total_pages": 0
}
```

### Error responses

| Status | When |
|---|---|
| `401` | No / invalid / expired token. Treat the same as any other 401 — kick to login. |
| `403` | Non-admin user passed someone else's `user_id`. Detail: `"You do not have access to this action"`. Don't show a global error page; just inline-warn and reset the filter. |
| `422` | Validation error (e.g. `per_page=0`, `reason="foo"`, malformed datetime). Show "Invalid filters" inline. |

---

## 6. Frontend Notes

### Edge cases

- **Empty history is `200`, not `404`.** Always check `data.total === 0` (or `items.length === 0`) for the empty state, never rely on error codes.
- **Webhook lag.** A `credit_purchase` row appears only **after** Click confirms the payment via webhook (typically 1–3 seconds after the user is redirected back). If the user just bought credits and immediately opens the history tab, the row may not be there yet. For the "did my purchase land?" check, prefer polling `GET /users/me` for the new `balance` rather than this endpoint.
- **`amount` of zero never happens.** Every row is a real movement, so you can safely use `amount > 0` for "income" and `amount < 0` for "spend" without a third branch.
- **`balance_before` / `balance_after` reflect the user's balance at that point in time**, not their *current* balance. To show the live balance, fetch `/users/me`.
- **`total_pages = 0` when `total = 0`.** Hide the pager — don't render "Page 1 of 0".

### Common mistakes

- ❌ Treating `amount` as money/so'm. It is **credits** (integer). Don't add `$` or `so'm`.
- ❌ Inferring sign from `reason`. Future reasons may flip the sign. Always read `amount`'s sign directly.
- ❌ Computing `total_pages` on the client. Use the server's `total_pages` — it already handles the `total = 0` and rounding cases.
- ❌ Sending `user_id` from a regular user's screen. You'll get a 403. Only send it from an admin panel.
- ❌ Crashing on unknown `reason` or `reference_type`. The backend may add new values; your `switch` must have a `default`.
- ❌ Parsing `created_at` as local time without thinking. Server returns UTC without a `Z`. If your users are in different timezones, append `"Z"` before `new Date(...)`.

### Integration tips

**Loading state.** This endpoint is a normal HTTP request (no streaming). Show a spinner while `await`ing, swap to the table on success. Typical response time is well under 200ms.

**Pagination component.** Drive the pager from the server's `total_pages`. On page change, just bump the `page` query param and re-fetch — keep the other filters in URL state so the user can share/bookmark.

**Filters change → reset to page 1.** If the user changes `reason` or the date range, set `page=1` before fetching. Otherwise they may land on an out-of-range page and get `items: []`.

**Caching.** Safe to cache per `(user_id, page, filters)` for short TTLs (5–10s). Bust the cache after a successful purchase or service activation since the user expects to see the new row immediately.

**TypeScript types** (drop into your client):

```ts
export type PaymentReason = "credit_purchase" | "service_activation";
export type PaymentRefType = "order" | "service";

export interface PaymentHistoryItem {
  id: number;
  amount: number;              // signed integer, in credits
  reason: PaymentReason;
  balance_before: number;
  balance_after: number;
  reference_type: PaymentRefType;
  reference_id: number;
  created_at: string;          // ISO 8601 UTC, no "Z"
}

export interface PaymentHistoryList {
  items: PaymentHistoryItem[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}
```

**Helper for labels & links:**

```ts
function reasonLabel(r: string): string {
  switch (r) {
    case "credit_purchase":    return "Credits purchased";
    case "service_activation": return "Service activated";
    default:                   return r.replace(/_/g, " ");
  }
}

function detailLinkFor(item: PaymentHistoryItem): string | null {
  switch (item.reference_type) {
    case "service": return `/services/${item.reference_id}`;
    case "order":   return `/orders/${item.reference_id}`;
    default:        return null;
  }
}
```

**Row example (React):**

```tsx
function HistoryRow({ item }: { item: PaymentHistoryItem }) {
  const positive = item.amount > 0;
  return (
    <tr>
      <td>{reasonLabel(item.reason)}</td>
      <td style={{ color: positive ? "green" : "red" }}>
        {positive ? "+" : ""}{item.amount} credits
      </td>
      <td>Balance: {item.balance_after}</td>
      <td>{new Date(item.created_at).toLocaleString()}</td>
      <td>
        {detailLinkFor(item) && <a href={detailLinkFor(item)!}>View</a>}
      </td>
    </tr>
  );
}
```

# Change user balance (admin)

Use this when an **admin** or **super admin** needs to **add or remove credits** on a user’s account from your admin UI.

**Endpoint:** `PATCH {API_V1_PREFIX}/admin/users/{user_id}/change-balance`  
Example: `PATCH /api/v1/admin/users/42/change-balance`  
(`API_V1_PREFIX` is usually `/api/v1` — check your environment.)

**Who can call it:** only users with role **admin** or **super admin**. Send `Authorization: Bearer <access_token>`.

**Path:** replace `{user_id}` with the numeric user id.

**Headers:** `Content-Type: application/json` and your bearer token.

---

## Request body (JSON)

Send a JSON object with these fields:

- **`amount`** (required, integer): how many credits to **add**. Use a **negative** number to **subtract** credits. Example: `50` adds 50, `-10` removes 10.
- **`reason`** (optional, string): why the change happened, for reporting. For normal manual work in the admin panel, use **`"by_admin"`**. Other allowed values are **`"credit_purchase"`** and **`"service_activation"`** — use those only if your product flow really matches those names.
- **`comment`** (optional, string): free text shown in admin/support context (e.g. ticket id, short explanation). Can be omitted or empty.

Minimal body (credit only):

```json
{ "amount": 50, "reason": "by_admin" }
```

With a note:

```json
{ "amount": 50, "reason": "by_admin", "comment": "Refund — ticket #1234" }
```

Debit example:

```json
{ "amount": -10, "reason": "by_admin", "comment": "Duplicate credit removed" }
```

---

## Response

On success the server responds with **HTTP 200** and the **full user profile** — the same shape as **`UserResponse`** (for example the same JSON you get from **`GET …/admin/users/{user_id}`**). It is **not** limited to `id` and `balance`; you get the whole object so you can refresh name, email, role, status, company, location, etc. in one response.

Typical fields include (names as in JSON): `id`, `email`, `first_name`, `last_name`, `full_name`, `phone`, `avatar_url`, `balance`, `city`, `state`, `zip_code`, `country`, `company_name`, `company_logo`, `mc_number`, `dot_number`, `status`, `email_verified`, `role`, `sell_status`, `can_provide_services`, `service_status`, `bio`, `website`, `social_links`, `created_at`, `last_login_at`, and others defined in the API schema.

For this flow, **`balance`** is the one that **changed**; **`id`** should still match the `user_id` in the URL. Use the full body to update your user detail state if you keep one in the client.

**Example** (illustrative — your payload may include more or null fields):

```json
{
  "id": 42,
  "email": "user@example.com",
  "first_name": "Jane",
  "last_name": "Doe",
  "full_name": "Jane Doe",
  "balance": 150,
  "role": "seller",
  "status": "active",
  "company_name": "Example LLC",
  "country": "USA",
  "created_at": "2025-01-15T10:00:00Z"
}
```

Exact keys and enums: **`/docs`** → **`UserResponse`**.

---

## Quick checklist

- Wrong or missing token → **401**. Not an admin → **403**. Bad JSON or invalid `reason` string → **422**.
- Confirm with the operator before sending a **negative** `amount`; the API does not stop the balance from going **below zero** by itself.
- After a debit, consider showing the new `balance` and optionally linking to that user’s payment history in your app if you already have that screen.

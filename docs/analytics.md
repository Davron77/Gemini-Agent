# Analytics — Service statistics API

This document describes every **statistics / analytics** endpoint under the services router: paths, parameters, request bodies, responses, and how each endpoint behaves on the server.

**Base URL:** `{API_V1_PREFIX}/services`  
Default `API_V1_PREFIX` is **`/api/v1`**, so paths look like **`/api/v1/services/...`**. Configure per environment.

**Authentication:** All endpoints below require a valid **Bearer** access token and one of: **`SELLER`**, **`ADMIN`**, **`SUPER_ADMIN`**.

**HTTP method:** Every stats route is **`GET`**. There is **no request body**.

---

## Summary table

| # | Method | Path | Purpose |
|---|--------|------|---------|
| 1 | `GET` | `/services/{service_id}/stats` | Snapshot for one listing |
| 2 | `GET` | `/services/stats` | Ranked list of listings (cumulative or date range) |
| 3 | `GET` | `/services/stats/time-based` | Time buckets (hourly table) for charts |
| 4 | `GET` | `/services/stats/best-period` | Best single bucket + optional per-seller breakdown (admin) |
| 5 | `GET` | `/services/stats/overview` | Platform or seller totals + daily series |

*(Paths are relative to `API_V1_PREFIX`; e.g. full path `/api/v1/services/stats`.)*

---

## What questions can this API answer?

Each row maps a **product question** to the **HTTP endpoint** that answers it (paths are under `{API_V1_PREFIX}/services`).

| Question | Endpoint | Short answer |
|----------|----------|----------------|
| How many **page views** does this listing have right now? | `GET /services/{service_id}/stats` | `view_count` (Redis when present, else DB). |
| How many **contact reveals** for this listing? | `GET /services/{service_id}/stats` | `view_contact_count`. |
| What is this listing’s **contact rate %**? | `GET /services/{service_id}/stats` | `contact_rate_percent`. |
| Which listings have the **most views** (all time, ranked)? | `GET /services/stats` | Cumulative mode: omit `date_from` / `date_to`; use `sort_by=views`. |
| Which listings had the **most views in a date range**? | `GET /services/stats` | Pass **both** `date_from` and `date_to`; `sort_by=views`. |
| Which listings had the **most contact opens** (cumulative or range)? | `GET /services/stats` | `sort_by=contacts` (+ optional date range). |
| Who **converts** best (contacts ÷ views)? | `GET /services/stats` | `sort_by=conversion_rate`. |
| Which listings are **“worst”** (views but no contacts)? | `GET /services/stats` | `sort_by=worst`. |
| How do **views and contacts trend over time** (chart)? | `GET /services/stats/time-based` | `group_by=hour|day|week|month`; optional `date_from` / `date_to`. |
| How did **one service** trend over time? | `GET /services/stats/time-based` | Add `service_id={id}` (seller must own it). |
| What are **headline KPIs** (counts, all-time views/contacts, rates)? | `GET /services/stats/overview` | Top-level fields + `daily` for a day-level series. |
| How did **daily** views/contacts look in a chosen window? | `GET /services/stats/overview` | Set `date_from` / `date_to`; read `daily.items`. |
| How many **active / inactive / unpaid** services (scoped)? | `GET /services/stats/overview` | `total_active_services`, etc. |
| **When** was the busiest bucket (peak hour/day) for a scope? | `GET /services/stats/best-period` | Top-level `hour`, `views`, `contact_views`; tune `metric`, `group_by`. |
| For **each seller**, when was **their** peak bucket? (admin, whole market) | `GET /services/stats/best-period` | Omit `user_id`; read `users` (size capped by `limit`). |

**Admin-only scoping (same endpoints, query params):** use `provider_id` on **`/stats`**, **`/stats/time-based`**, **`/stats/overview`** to restrict to one seller; use `user_id` on **`/stats/best-period`** for one seller’s best bucket (then `users` is not returned).

**Not covered by these routes:** per-event timestamps, raw event streams, revenue, search placement, sectors/tags breakdown, or metrics outside service views / contact reveals.

---

## 1. `GET /services/{service_id}/stats`

### Path parameters

| Name | Type | Description |
|------|------|-------------|
| `service_id` | integer | ID of the service. Must exist and not be treated as deleted for lookup (404 if not found). |

### Query parameters

None.

### Request body

None.

### Authorization

- **Seller:** only if `service.provider_id` equals the current user → **200**. Otherwise **403** (“You can only view stats for your own services”).
- **Admin / Super admin:** any service → **200**.

### How it works

1. Loads the service by `service_id`.
2. Reads **Redis** keys `view_count:service:{id}` and `view_contact_count:service:{id}` when present.
3. If a Redis key is missing, falls back to **`services.view_count`** and **`services.view_contact_count`** on the row.
4. Computes `contact_rate_percent = (contacts / views) * 100` when `views > 0`, else `0`, rounded to 2 decimals.

### Response: `ServiceStatsResponse`

JSON object:

| Field | Type | Description |
|-------|------|-------------|
| `service_id` | integer | Same as path param. |
| `title` | string or `null` | Service display name (`name`). |
| `view_count` | integer | Page views (Redis-preferred). |
| `view_contact_count` | integer | Contact-detail opens (Redis-preferred). |
| `contact_rate_percent` | number (float) | Percentage; `0.0` if no views. |

### Status codes

| Code | When |
|------|------|
| `200` | Success |
| `403` | Seller viewing another seller’s service |
| `404` | Service not found |

---

## 2. `GET /services/stats`

Returns a **sorted list** of services with view/contact counts per row. Either **lifetime-style** counts (Redis + DB) or **in-range** sums from **`service_stats_hourly`**.

### Path parameters

None.

### Query parameters

| Name | Type | Required | Default | Constraints | Description |
|------|------|----------|---------|---------------|-------------|
| `provider_id` | integer | no | `null` | — | **Admin / Super admin:** filter to that seller’s services (`null` = whole marketplace). **Seller:** must equal own user id or be omitted; otherwise **403**. |
| `sort_by` | string | no | `views` | One of: `views`, `contacts`, `conversion_rate`, `worst` | Primary sort key. |
| `order` | string | no | `desc` | `asc` or `desc` | Sort direction for `views`, `contacts`, `conversion_rate`. For `worst`, order is fixed (lowest views among zero-contact services). |
| `limit` | integer | no | `null` (server uses **5** when omitted in repository) | `1`–`1000` if provided | Max number of services returned. |
| `date_from` | datetime (ISO) | conditional | `null` | — | Start of window for hourly aggregation. |
| `date_to` | datetime (ISO) | conditional | `null` | — | End of window for hourly aggregation. |

**Rule:** `date_from` and `date_to` must **both be omitted** or **both provided**. If exactly one is sent → **422** with message *`date_from and date_to must both be provided or both omitted`*.

### Request body

None.

### Authorization (router)

- **Admin / Super admin:** `provider_id` optional (any seller or whole platform).
- **Seller:** if `provider_id` is set and ≠ current user → **403** (“Insufficient permissions”). Otherwise effective scope is **current seller**.

### How it works

**A) Both `date_from` and `date_to` set**

1. Aggregates **`service_stats_hourly`** joined to **`services`**, grouped by **service**, restricted to non-deleted services and optional `provider_id`.
2. Applies `sort_by` / `order` (and `worst`: only services with **zero** contact views in the range, ordered by ascending views in range).
3. Returns up to `limit` rows. Each row’s `view_count` / `view_contact_count` are **only for that date range** (field names unchanged for compatibility).

**B) No date range**

1. Queries **`services`** ranked by cumulative columns / conversion / worst (non-deleted, optional `provider_id`).
2. For each service, prefers **Redis** per-service keys; else DB columns.
3. Builds `contact_rate_percent` per row.

### Response: `ServiceStatsListResponse`

| Field | Type | Description |
|-------|------|-------------|
| `items` | array of objects | Each element matches **`ServiceStatsResponse`** (see §1). |
| `total` | integer | Always **`items.length`** for this endpoint (not a separate DB total count). |

Each item in `items`:

| Field | Type | Description |
|-------|------|-------------|
| `service_id` | integer | Service id. |
| `title` | string or `null` | Service name. |
| `view_count` | integer | Cumulative or in-range views (see mode above). |
| `view_contact_count` | integer | Cumulative or in-range contact views. |
| `contact_rate_percent` | number | `(view_contact_count / view_count) * 100` if `view_count > 0`, else `0`. |

### Status codes

| Code | When |
|------|------|
| `200` | Success |
| `403` | Seller misused `provider_id` |
| `422` | Only one of `date_from`, `date_to` provided |

---

## 3. `GET /services/stats/time-based`

Time series for **charts** from **`service_stats_hourly`**, bucketed with `date_trunc`. Soft-deleted services are excluded.

### Path parameters

None.

### Query parameters

| Name | Type | Required | Default | Constraints | Description |
|------|------|----------|---------|---------------|-------------|
| `date_from` | datetime (ISO) | no | If omitted: **`date_to` minus 30 days** | — | Inclusive lower bound on `hour`. |
| `date_to` | datetime (ISO) | no | If omitted: **now (UTC)** | — | Upper bound on `hour`. |
| `group_by` | string | no | `day` | `hour`, `day`, `week`, or `month` | PostgreSQL `date_trunc` grain. |
| `provider_id` | integer | no | `null` | — | **Admin:** limit to one seller’s services. **Seller:** must be self or omitted → else **403**. |
| `service_id` | integer | no | `null` | — | Limit to one listing. **Seller** must own it → else **403**; unknown id → **404**. **Admin:** any id that exists and is not soft-deleted; if the id does not exist or is deleted, the active-service filter matches nothing → **`200`** with **empty `items`** (not 404). |

### Request body

None.

### Authorization

- **Admin / Super admin:** `provider_id` is optional global vs one seller; `service_id` optional.
- **Seller:** data is always scoped to own listings; cannot set another seller’s `provider_id` or another user’s `service_id`.

### How it works

1. Resolves `date_to` (default now UTC), then `date_from` (default 30 days before `date_to`).
2. Builds a subquery of **non-deleted** `services.id`, optionally filtered by `provider_id` and/or `service_id`.
3. Sums `views` and `contact_views` from **`service_stats_hourly`** per **`date_trunc(group_by, hour)`**, filtered to those service ids and the time range.
4. Returns rows ordered by bucket ascending.

### Response: `TimeStatsResponse`

| Field | Type | Description |
|-------|------|-------------|
| `group_by` | string | Echo of the `group_by` query param (`hour` / `day` / `week` / `month`). |
| `date_from` | string (ISO datetime) | Effective range start used for the query (after defaults). |
| `date_to` | string (ISO datetime) | Effective range end used for the query. |
| `items` | array | List of **`TimeStatItem`** (see below). |

**`TimeStatItem` (each element of `items`):**

| Field | Type | Description |
|-------|------|-------------|
| `date` | string (ISO datetime) | Start of the time bucket (truncated instant). |
| `views` | integer | Sum of page views in that bucket. |
| `contact_views` | integer | Sum of contact views in that bucket. |

### Status codes

| Code | When |
|------|------|
| `200` | Success |
| `403` | Seller scope violation (`provider_id` / `service_id` ownership) |
| `404` | **Seller** only: `service_id` set but no non-deleted service with that id (not found). **Admin** does not get 404 for a bad `service_id` — response is **`200`** with **`items: []`**. |

---

## 4. `GET /services/stats/best-period`

Finds the **single best time bucket** in the range by `metric`, and optionally returns **each seller’s** own best bucket (admin, marketplace-wide only).

### Path parameters

None.

### Query parameters

| Name | Type | Required | Default | Constraints | Description |
|------|------|----------|---------|---------------|-------------|
| `user_id` | integer | no | `null` | — | **Admin:** `null` = marketplace-wide top bucket + **`users`** list; set to a user id = that seller only (no `users`). **Seller:** ignored; always scoped to self. |
| `metric` | string | no | `views` | `views`, `contact_views`, `conversion_rate` | What “best” means for ordering buckets. |
| `group_by` | string | no | `hour` | `hour` or `day` | Bucket size for aggregation. |
| `date_from` | datetime (ISO) | no | If omitted: **`date_to` minus 30 days** | — | Range start. |
| `date_to` | datetime (ISO) | no | If omitted: **now (UTC)** | — | Range end. |
| `limit` | integer | no | `20` | `1`–`100` | When **admin** and **`user_id` omitted**: maximum length of **`users`**. For **sellers** (and admin with **`user_id` set**), the query param is accepted but **has no effect** on the response (there is no `users` list). |

### Request body

None.

### Authorization

- **Seller:** always own services; `user_id` query param cannot point at another seller (403 if tried).
- **Admin:** full use of `user_id` and `limit` as above.

### How it works

1. Resolves `date_to` and `date_from` like time-based stats.
2. Maps caller to a **`target_provider`** (`user_id` for admin, always self for seller).
3. **`get_best_period` (repository):** aggregates hourly rows into buckets (`group_by`), sums views/contacts per bucket, picks **one** bucket with highest `metric` (for `conversion_rate`, uses contacts/views).
4. Builds the top-level object: `user_id` = `target_provider` ( **`null`** for admin marketplace-wide ), `hour` = winning bucket start or **`null`** if no data, `views` / `contact_views` for that bucket (or zeros).
5. **If admin and `user_id` is omitted:** runs a second query that, for each seller, finds their best bucket by the same `metric`, then orders sellers by **total views in the full range** descending and keeps the first **`limit`** rows. Those become **`users`**.

### Response: `BestPeriodResponse`

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | integer or `null` | Scoped seller for the **top-level** best row (`null` = global when admin omitted `user_id`). |
| `hour` | string (ISO datetime) or `null` | Start of the winning time bucket for the top-level row; `null` if no rows in range. |
| `views` | integer | Views in that top-level bucket. |
| `contact_views` | integer | Contact views in that top-level bucket. |
| `users` | array or `null` | Present (list, possibly empty) only for **admin** with **`user_id` omitted**. Each element is **`BestPeriodUserItem`**. Otherwise **`null`** / omitted in JSON. |

**`BestPeriodUserItem` (elements of `users`):**

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | integer | Seller (provider) id. |
| `hour` | string (ISO datetime) | That seller’s best bucket start (same `group_by` / `metric` logic). |
| `views` | integer | Views in that bucket. |
| `contact_views` | integer | Contact views in that bucket. |

### Status codes

| Code | When |
|------|------|
| `200` | Success |
| `403` | Seller permission error on `user_id` |

---

## 5. `GET /services/stats/overview`

Dashboard **headline numbers** (all-time style aggregates from **`services`**) plus a **`daily`** block built from **`service_stats_hourly`** by **day**.

### Path parameters

None.

### Query parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `provider_id` | integer | no | `null` | **Admin:** restrict aggregates to that seller; `null` = entire marketplace. **Seller:** must match self or be omitted; else **403**. |
| `date_from` | datetime (ISO) | no | If omitted: **`date_to` minus 30 days** | Start of range used only for the **`daily`** section. |
| `date_to` | datetime (ISO) | no | If omitted: **now (UTC)** | End of range for **`daily`**. |


### Request body

None.

### Authorization

Same pattern as other seller-scoped routes: sellers always see **own** data; admins may pass `provider_id`.

### How it works

1. **`get_aggregated_stats`:** counts services by status and sums **`services.view_count`** / **`view_contact_count`** (and derives `contact_rate_percent`) for the chosen scope. These top-level fields are **cumulative / DB snapshot** and are **not** limited to `date_from`–`date_to`. **Note:** this query does **not** filter **`deleted_at`**, so **soft-deleted** rows can still contribute to **`total_services`**, status counts, **`total_views`**, and **`total_contacts`**. The **`daily`** series uses hourly aggregates which **exclude** deleted services.
2. Normalizes `date_to` (default now), `date_from` (default 30 days earlier).
3. Calls the same logic as time-based stats with **`group_by = day`** for that range and scope.
4. Builds **`daily`:** includes `date_from`, `date_to`, sums of `views` / `contact_views` across all **`daily.items`**, and **`items`**: one row per day with `date`, `views`, `contact_views`.

### Response: `PlatformOverviewStatsResponse`

**Top-level (cumulative scope):**

| Field | Type | Description |
|-------|------|-------------|
| `total_services` | integer | Count of services in scope. |
| `total_active_services` | integer | Count with active status. |
| `total_inactive_services` | integer | Count inactive. |
| `total_unpaid_services` | integer | Count unpaid. |
| `total_views` | integer | Sum of `view_count` on `services` in scope. |
| `total_contacts` | integer | Sum of `view_contact_count` in scope. |
| `contact_rate_percent` | number | `(total_contacts / total_views) * 100` if `total_views > 0`, else `0` (rounded in code). |
| `daily` | object or `null` | In current implementation, **always populated** with structure below. Schema allows `null` for backward compatibility. |

**`daily` object (`DailyOverviewSummary`):**

| Field | Type | Description |
|-------|------|-------------|
| `date_from` | string (ISO datetime) | Effective start of daily series. |
| `date_to` | string (ISO datetime) | Effective end of daily series. |
| `total_views` | integer | Sum of `items[].views` (range-only). |
| `total_contacts` | integer | Sum of `items[].contact_views` (range-only). |
| `items` | array | List of **`TimeStatItem`** (`date`, `views`, `contact_views`) per day in range. |

### Status codes

| Code | When |
|------|------|
| `200` | Success |
| `403` | Seller misused `provider_id` |

---

## Shared notes

- **Datetimes** in JSON are ISO 8601 strings; prefer UTC on the client.
- **Hourly table** name in DB: **`service_stats_hourly`** (see migrations / models). Counters on listings can still be driven by **Redis** for the snapshot and list endpoints without date range.
- **401** / **403** for missing or invalid auth are handled by your global auth dependencies (not repeated per endpoint above).
- OpenAPI UI: **`/docs`**, **`/redoc`**.

## Related documentation

- **`service-analytics-frontend.md`** — frontend-oriented recipes and TypeScript-style shapes.
- **`service-views.md`** — how views and contact reveals are counted (dedup, etc.).

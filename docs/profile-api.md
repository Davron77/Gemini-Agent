# Profile Module — Frontend Integration Guide

> Base URL: `/api/v1`
>
> All endpoints require `Authorization: Bearer <token>` header.
> All company-scoped endpoints additionally require `X-Company-ID: <uuid>` header.

This guide covers everything needed to render and maintain the **employee profile page** (the big card with avatar, stats, personal and professional info, documents, employment history) plus **avatar upload** and **self-service profile editing**.

---

## Table of Contents

1. [Enums & Constants](#enums--constants)
2. [Access Rules](#access-rules)
3. [Profile Overview](#profile-overview) — the one-shot page endpoint
4. [Current User (`/me`)](#current-user-me)
5. [Avatar Upload & Delete](#avatar-upload--delete)
6. [Editing Profile Data](#editing-profile-data)
7. [Response Schemas](#response-schemas)
8. [Error Codes](#error-codes)
9. [Code Examples](#code-examples)

---

## Enums & Constants

### `EmployeeStatus`

| Value         | Meaning                          |
|---------------|----------------------------------|
| `pending`     | Profile created, not onboarded   |
| `active`      | Onboarded and working            |
| `on_leave`    | Temporarily out                  |
| `suspended`   | Disciplinary hold                |
| `terminated`  | Offboarded                       |

### `EmploymentType`

`full_time` · `part_time` · `contract` · `intern`

### `CompanyRole`

`admin` · `manager` · `employee`

### `HistoryType` (timeline events)

`hired` · `promoted` · `transferred` · `status_change` · `salary_change` · `terminated` · `asset_assigned`

### Avatar constraints

| Constraint      | Value                                  |
|-----------------|----------------------------------------|
| Max size        | **5 MB**                               |
| Allowed types   | `.jpg`, `.jpeg`, `.png`, `.webp`       |
| Content-Type    | must start with `image/`               |

---

## Access Rules

Who can see / edit what, by role. The same rules apply to every profile-related endpoint — there is no per-endpoint override.

### Viewing someone else's profile

| Role        | Can view                                                |
|-------------|---------------------------------------------------------|
| `admin`     | Any employee in the company                             |
| `manager`   | Self + any employee in a department **they head**       |
| `employee`  | Only their own profile                                  |

Callers outside the allowed scope get `403 Forbidden`.

### Editing profile data

| Field group                                               | Who can edit                             |
|-----------------------------------------------------------|------------------------------------------|
| `phone`, `personal_email`, `emergency_contact`, `address` | Self (any role)                          |
| `avatar`                                                  | Self only (via `/users/me/avatar`)       |
| `position_id`, `department_id`, `manager_id`, `hire_date`, `employment_type`, `status`, `work_location`, `salary`, `huntme_candidate_id`, `role` | HR (requires `employees:update` — admins and managers on their department) |
| `firstname`, `lastname`, `email`                          | Set at creation; SUPERADMIN-only via `/users/{id}` |

Non-privileged users who send HR-only fields will have those fields silently dropped — the request still succeeds for the allowed fields.

---

## Profile Overview

The single aggregated endpoint that drives the profile page. One round trip — no need to call `/employees/{id}`, `/employees/{id}/history`, and `/employees/{id}/documents` separately.

```
GET /api/v1/employees/{employee_id}/profile
```

> `employee_id` here is the **`user_companies.id`** (a.k.a. membership ID), not the underlying user ID and not the employee-profile row ID. This is the ID you already pass to other `/employees/{id}` endpoints.

**Permission:** See [Access Rules](#access-rules). Enforced automatically by the caller's permissions.

**Response:** `200 OK`

```json
{
  "id": "7c2c…",            // membership id (user_companies.id)
  "user_id": "b19a…",
  "company_id": "9f3e…",

  "header": {
    "full_name": "John Bob",
    "avatar_url": "https://s3.amazonaws.com/…?X-Amz-Signature=…",
    "job_title": "Senior Backend Engineer",
    "status": "active",
    "role": "employee"
  },

  "stats": {
    "employee_number": "EMP-2026-0001",
    "salary": "5000.00",
    "tenure_months": 12
  },

  "personal_information": {
    "full_name": "John Bob",
    "work_email": "john@company.com",
    "personal_email": "john@gmail.com",
    "phone": "+998901234567",
    "address": "Tashkent, Uzbekistan",
    "emergency_contact": {
      "name": "Jane Bob",
      "relation": "Spouse",
      "phone": "+998901234568"
    },
    "work_location": "Remote"
  },

  "professional_information": {
    "employee_id": "3c29…",   // employees.id (the profile row)
    "employee_number": "EMP-2026-0001",
    "hire_date": "2025-04-17",
    "termination_date": null,
    "job_title": "Senior Backend Engineer",
    "department": "IT Team",
    "reporting_manager": {
      "id": "…", "firstname": "Mike", "lastname": "Manager",
      "email": "mike@company.com", "phone": null
    },
    "employment_type": "full_time",
    "work_location": "Remote",
    "salary": "5000.00",
    "is_onboarded": true
  },

  "employment_history": [
    {
      "id": "…",
      "employee_id": "7c2c…",
      "type": "hired",
      "from_id": null,
      "to_id": "…",
      "changed_by_id": "…",
      "notes": "Hired into IT Team as Senior Backend Engineer",
      "created_at": "2025-04-17T16:19:00Z"
    }
  ],

  "documents": [
    {
      "id": "…",
      "filename": "contract.pdf",
      "file_size": 102400,
      "content_type": "application/pdf",
      "document_type": "contract",
      "visibility": "employee",
      "description": null,
      "uploaded_by_id": "…",
      "folder_id": null,
      "created_at": "2025-04-17T16:20:00Z"
    }
  ]
}
```

### Notes on specific fields

- `header.avatar_url` — **presigned S3 URL**, valid for 15 minutes. Use it directly as `<img src>`. No `Authorization` header needed when fetching it. It is `null` if the user has not uploaded an avatar.
- `header.status` — the coloured status dot. `null` when the member has no employee profile (role = admin/manager with no employee record).
- `stats.tenure_months` — whole months between `hire_date` and today (or `termination_date`). Format client-side as e.g. `"1y 2m"`.
- `stats.salary`, `professional_information.salary` — returned as string (Decimal). Parse with care.
- `employment_history` — newest first. Use this to render the timeline card.
- `documents` — only documents attached to **this employee's file** (not company-library docs).

### Document download URLs

`documents[].` entries do **not** include a `download_url`. When the user clicks a document, call the existing document-download endpoint:

```
GET /api/v1/documents/{document_id}/download  →  { download_url }
```

See `DOCUMENTS_API_GUIDE.md` for details.

---

## Current User (`/me`)

Used by the top-bar avatar + name + workspace switcher.

```
GET /api/v1/users/me
```

**Permission:** Any authenticated user. Does **not** require `X-Company-ID`.

**Response:** `200 OK`

```json
{
  "id": "…",
  "email": "john@company.com",
  "firstname": "John",
  "lastname": "Bob",
  "role": "admin",
  "avatar_url": "https://s3.amazonaws.com/…?X-Amz-Signature=…",
  "companies": [
    { "id": "…", "name": "HuntMe" }
  ]
}
```

- `avatar_url` is a fresh **presigned URL (15 min expiry)** or `null`.
- SUPERADMIN sees an empty `companies` list (they implicitly belong everywhere).

---

## Avatar Upload & Delete

The backend uploads the image to S3 and stores the S3 key. Every response gives you back a short-lived presigned GET URL.

### Upload / Replace

```
POST /api/v1/users/me/avatar
```

> `multipart/form-data`, **not** JSON. Self-only — no `employee_id` path parameter.

**Form fields:**

| Field  | Type | Required | Notes                                           |
|--------|------|----------|-------------------------------------------------|
| `file` | file | **Yes**  | jpg / jpeg / png / webp, max 5 MB, `image/*`    |

**Response:** `201 Created`

```json
{ "avatar_url": "https://s3.amazonaws.com/…?X-Amz-Signature=…" }
```

Behaviour:
- Any previously-uploaded avatar is deleted from S3 after the new one is saved.
- On DB failure the just-uploaded S3 object is rolled back, so no orphans.
- The returned URL expires in 15 min — cache the binary or request `/me` again as needed.

### Delete

```
DELETE /api/v1/users/me/avatar
```

**Response:** `204 No Content`

Removes both the S3 object and the DB reference. Subsequent `/me` / profile responses will have `avatar_url: null`.

---

## Editing Profile Data

### Self-service fields

Employees can update their own contact info via the existing member-update endpoint. The backend filters the body to a self-editable allowlist when the caller is editing their own membership without `employees:update`.

```
PATCH /api/v1/employees/{employee_id}      # employee_id = caller's own user_companies.id
```

**Body (JSON) — all fields optional:**

```json
{
  "phone": "+998901234567",
  "personal_email": "john@gmail.com",
  "address": "Tashkent, Uzbekistan",
  "emergency_contact": {
    "name": "Jane Bob",
    "relation": "Spouse",
    "phone": "+998901234568"
  }
}
```

HR-only fields sent in the same request are silently dropped — no error. The response is a `MemberDetailRead`.

### HR-only fields

Callers with `employees:update` can send the full `EmployeeUpdate` schema:

| Field                 | Type          | Notes                                         |
|-----------------------|---------------|-----------------------------------------------|
| `role`                | `CompanyRole` | Triggers permission + profile transitions     |
| `position_id`         | uuid          |                                               |
| `department_id`       | uuid          |                                               |
| `manager_id`          | uuid          | Must belong to the same company               |
| `hire_date`           | date          |                                               |
| `employment_type`     | enum          |                                               |
| `status`              | enum          | Writes a `status_change` history entry         |
| `work_location`       | string        |                                               |
| `salary`              | decimal       | Writes a `salary_change` history entry         |
| `huntme_candidate_id` | uuid          |                                               |

### Promote / Transfer / Terminate (dedicated actions)

Prefer these over a bare `PATCH` — they validate effective dates, write proper history entries, and in the termination case cancel pending requests and reassign direct reports.

| Action     | Endpoint                                            |
|------------|-----------------------------------------------------|
| Promote    | `POST /api/v1/employees/{id}/promote`               |
| Transfer   | `POST /api/v1/employees/{id}/transfer`              |
| Terminate  | `POST /api/v1/employees/{id}/terminate`             |
| Onboarded  | `PATCH /api/v1/employees/{id}/onboarded`            |

See each endpoint's OpenAPI docs for payload shape.

---

## Response Schemas

### `EmployeeProfileOverview`

```typescript
interface EmployeeProfileOverview {
  id: string;           // user_companies.id (membership id)
  user_id: string;
  company_id: string;

  header: ProfileHeader;
  stats: ProfileStats;
  personal_information: PersonalInformation;
  professional_information: ProfessionalInformation;
  employment_history: EmploymentHistoryRead[];
  documents: DocumentListItem[];
}

interface ProfileHeader {
  full_name: string;
  avatar_url: string | null;            // presigned S3, 15 min
  job_title: string | null;
  status: EmployeeStatus | null;
  role: CompanyRole;
}

interface ProfileStats {
  employee_number: string | null;
  salary: string | null;                // Decimal as string
  tenure_months: number | null;
}

interface PersonalInformation {
  full_name: string;
  work_email: string;
  personal_email: string | null;
  phone: string | null;
  address: string | null;
  emergency_contact: Record<string, unknown> | null;
  work_location: string | null;
}

interface ProfessionalInformation {
  employee_id: string | null;           // employees.id (profile row)
  employee_number: string | null;
  hire_date: string | null;             // ISO date
  termination_date: string | null;
  job_title: string | null;
  department: string | null;
  reporting_manager: UserInfo | null;
  employment_type: EmploymentType | null;
  work_location: string | null;
  salary: string | null;
  is_onboarded: boolean;
}

interface UserInfo {
  id: string;
  firstname: string;
  lastname: string;
  email: string;
  phone: string | null;
}

interface EmploymentHistoryRead {
  id: string;
  employee_id: string;                  // user_companies.id
  type: HistoryType;
  from_id: string | null;
  to_id: string | null;
  changed_by_id: string;
  notes: string | null;
  created_at: string;                   // ISO datetime
}
```

### `UserInfo` (from `/me`)

```typescript
interface Me {
  id: string;
  email: string;
  firstname: string;
  lastname: string;
  role: "superadmin" | "admin" | "manager" | "employee";
  avatar_url: string | null;
  companies: { id: string; name: string }[];
}
```

### `AvatarRead`

```typescript
interface AvatarRead {
  avatar_url: string | null;
}
```

---

## Error Codes

| Status | When                                                                         |
|--------|------------------------------------------------------------------------------|
| `400`  | Missing filename, bad avatar extension/content-type, file > 5 MB             |
| `401`  | Missing or invalid JWT token                                                 |
| `403`  | Caller's scope does not cover the target employee, or editing someone else   |
| `404`  | Employee/member not found (wrong id, wrong company, soft-deleted)            |

Error body is a standard FastAPI detail envelope:

```json
{ "detail": "Access denied" }
```

---

## Code Examples

### Load the profile page (React / Axios)

```javascript
const fetchProfile = async (employeeId) => {
  const { data } = await axios.get(
    `/api/v1/employees/${employeeId}/profile`,
    {
      headers: {
        "Authorization": `Bearer ${token}`,
        "X-Company-ID": companyId,
      },
    }
  );
  return data; // EmployeeProfileOverview
};
```

### Render tenure `"1y 2m"`

```javascript
const formatTenure = (months) => {
  if (months == null) return "—";
  const y = Math.floor(months / 12);
  const m = months % 12;
  if (y && m) return `${y}y ${m}m`;
  if (y)      return `${y}y`;
  return `${m}m`;
};
```

### Upload an avatar

```javascript
const uploadAvatar = async (file) => {
  const form = new FormData();
  form.append("file", file);
  const { data } = await axios.post("/api/v1/users/me/avatar", form, {
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "multipart/form-data",
    },
  });
  return data.avatar_url; // presigned S3 URL
};
```

### React avatar input

```jsx
const AvatarUpload = ({ onUploaded }) => {
  const handleChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const allowed = [".jpg", ".jpeg", ".png", ".webp"];
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!allowed.includes(ext))       return alert("Image must be jpg/jpeg/png/webp");
    if (file.size > 5 * 1024 * 1024)  return alert("Image exceeds 5 MB");

    const url = await uploadAvatar(file);
    onUploaded(url);
  };

  return (
    <input type="file" accept="image/jpeg,image/png,image/webp" onChange={handleChange} />
  );
};
```

### Self-edit contact info

```javascript
const updateMyContact = async (membershipId, patch) => {
  // patch may contain: phone, personal_email, address, emergency_contact
  const { data } = await axios.patch(
    `/api/v1/employees/${membershipId}`,
    patch,
    {
      headers: {
        "Authorization": `Bearer ${token}`,
        "X-Company-ID": companyId,
      },
    }
  );
  return data; // MemberDetailRead
};
```

### Refresh the avatar when it expires

Presigned URLs expire after 15 minutes. If a user keeps the page open longer than that, the `<img>` will start returning 403. Two easy strategies:

- Re-fetch the profile / `/me` when the tab regains focus.
- Or set a timer that swaps the `<img src>` every ~10 minutes from a cached `/me` call.

```javascript
useEffect(() => {
  const id = setInterval(async () => {
    const { data } = await axios.get("/api/v1/users/me", {
      headers: { "Authorization": `Bearer ${token}` },
    });
    setAvatarUrl(data.avatar_url);
  }, 10 * 60 * 1000); // 10 min
  return () => clearInterval(id);
}, []);
```

# Delete Account Endpoint

## `DELETE /users/me/account`

Permanently deletes the authenticated user's account. All personal data is removed and the account is immediately locked. This action is **irreversible**.

---

## Request

### Headers

| Header | Value | Required |
|--------|-------|----------|
| `Authorization` | `Bearer <access_token>` | ✅ Yes |

### Body

None.

### Example

```http
DELETE /users/me/account
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Response

### Success — `200 OK`

```json
{
  "success": true,
  "message": "Your account has been permanently deleted. We're sorry to see you go."
}
```

### Error — `401 Unauthorized`

Returned when the token is missing, expired, or the account is already disabled.

```json
{
  "detail": "Not authenticated"
}
```

### Error — `404 Not Found`

Returned when the user ID from the token no longer maps to a record.

```json
{
  "detail": "User not found"
}
```

---

## What happens on deletion

| Data | Action |
|------|--------|
| Name, email, phone, photo | Wiped immediately |
| Password & Google ID | Nulled — login becomes impossible |
| Profile, skills, resume, education, courses | Permanently deleted |
| Notifications, FCM tokens, OTPs | Permanently deleted |
| Saved jobs, reward records | Permanently deleted |
| Active job listings (employers) | Set to Inactive |
| Company contact info (employers) | Wiped |
| Job applications, employments, offers, interviews | **Kept** — other users retain their history |
| Blacklist & employer notes about this user | **Kept** — employer side remains intact |
| Payment transactions | **Kept** — financial records are never deleted |
| Audit logs | **Kept** — immutable history |

---

## UI Guidelines

- **Show a confirmation dialog** before calling this endpoint — the action cannot be undone.
- **Immediately log the user out** on success. Invalidate the local token and redirect to the login/landing screen.
- The user's email is freed after deletion, so they can re-register with the same address later if they choose.
- Do not retry on success — calling the endpoint a second time will return `401` since the account is disabled.

---

## Flow Diagram

```
User taps "Delete Account"
        │
        ▼
Confirmation dialog shown
        │
  User confirms
        │
        ▼
DELETE /users/me/account
   + Authorization header
        │
        ▼
     200 OK
        │
        ▼
Clear local token → Redirect to Login
```

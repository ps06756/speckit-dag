# Data Model: User Authentication

## User

| Field | Type | Notes |
|---|---|---|
| id | UUID | primary key |
| email | text | unique, stored lowercase |
| password_hash | text | argon2id |
| verified_at | timestamp | null until the email is confirmed |

## VerificationToken

| Field | Type | Notes |
|---|---|---|
| token | text | random, 32 bytes, URL-safe |
| user_id | UUID | references User |
| purpose | enum | `verify_email` or `reset_password` |
| expires_at | timestamp | 24 hours after creation (FR-002) |

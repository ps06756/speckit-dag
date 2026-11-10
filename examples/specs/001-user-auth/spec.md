# Feature Specification: User Authentication

**Feature Branch**: `001-user-auth`
**Status**: Draft

## User Scenarios & Testing

### User Story 1 - Sign up with email (Priority: P1)

A visitor creates an account with an email and password, then confirms the email
from a link we send.

**Independent Test**: Sign up with a new email, follow the link, and see the account
marked as verified.

**Acceptance Scenarios**:

1. **Given** an unused email, **When** the visitor signs up, **Then** an account is
   created and a verification email is sent.
2. **Given** an email that is already registered, **When** the visitor signs up,
   **Then** they see that the email is taken.

### User Story 2 - Log in (Priority: P2)

A user with a verified account logs in with their email and password.

**Independent Test**: Log in with a verified account and receive a session.

### User Story 3 - Reset password (Priority: P3)

A user who forgot their password requests a reset link and sets a new password.

**Independent Test**: Request a reset, follow the link, set a new password, and log
in with it.

## Requirements

- **FR-001**: The system MUST store passwords only as salted hashes.
- **FR-002**: Verification and reset links MUST expire after 24 hours.
- **FR-003**: The system MUST rate-limit sign-up, login and reset requests.

---
description: "Task list for user authentication"
---

# Tasks: User Authentication

**Input**: Design documents from `/specs/001-user-auth/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Create project structure per implementation plan
- [ ] T002 [P] Configure ruff and black in pyproject.toml
- [ ] T003 [P] Add CI workflow in .github/workflows/ci.yml

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Set up database schema and migrations in src/db/migrations/
- [ ] T005 [P] Implement password hashing helpers in src/lib/crypto.py
- [ ] T006 [P] Configure structured logging in src/lib/logging.py
- [ ] T007 Create base API router and error handling in src/api/app.py

**Checkpoint**: Foundation ready - user story work can now begin in parallel

---

## Phase 3: User Story 1 - Sign up with email (Priority: P1) 🎯 MVP

**Goal**: A visitor can create an account with an email and password.

### Tests for User Story 1

- [ ] T008 [P] [US1] Contract test for POST /signup in tests/contract/test_signup.py
- [ ] T009 [P] [US1] Integration test for the sign-up flow in tests/integration/test_signup.py

### Implementation for User Story 1

- [ ] T010 [P] [US1] Create User model in src/models/user.py
- [ ] T011 [P] [US1] Create VerificationToken model in src/models/token.py
- [ ] T012 [US1] Implement SignupService in src/services/signup.py
- [ ] T013 [US1] Implement POST /signup endpoint in src/api/signup.py

---

## Phase 4: User Story 2 - Log in (Priority: P2)

### Tests for User Story 2

- [ ] T014 [P] [US2] Contract test for POST /login in tests/contract/test_login.py

### Implementation for User Story 2

- [ ] T015 [P] [US2] Implement session store in src/services/sessions.py
- [ ] T016 [US2] Implement POST /login endpoint in src/api/login.py

---

## Phase 5: User Story 3 - Reset password (Priority: P3)

### Implementation for User Story 3

- [ ] T017 [P] [US3] Implement reset-token service in src/services/reset.py (depends on T011)
- [ ] T018 [US3] Implement POST /password-reset endpoint in src/api/reset.py

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T019 [P] Document auth endpoints in docs/api.md
- [ ] T020 [P] Add rate limiting to auth endpoints in src/api/middleware.py
- [ ] T021 Run quickstart.md validation

---

## Dependencies & Execution Order

- Setup (Phase 1) → Foundational (Phase 2) → User stories (Phase 3+) → Polish (Phase 6)
- User stories can run in parallel once Foundational is done

### Parallel Example: User Story 1

```bash
Task: "Contract test for POST /signup in tests/contract/test_signup.py"
- [ ] T999 This line is inside a code fence and is ignored
```

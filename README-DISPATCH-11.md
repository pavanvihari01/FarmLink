# Dispatch #11 — Profile editing

## What this archive contains

    backend/app/api/routes.py        (PATCH /auth/me, user_out includes phone)
    backend/app/schemas/api.py       (ProfileUpdateInput, UserOut.phone)
    frontend/src/lib/api.ts          (updateProfile)
    frontend/src/pages/Profile.tsx   (account form)
    frontend/src/App.tsx             (passes onUserUpdate to Profile)

No migration. `users.phone` has existed on the model since the beginning — it
was simply never returned by `UserOut` or editable anywhere.

## How to apply

Extract with **overwrite on**, then:

    cd E:\myApps\Project\FarmLink\backend
    uvicorn app.main:app --reload

No database deletion — no schema changed. `--reload` should pick up `routes.py`
on its own, but a restart is cleaner.

    cd E:\myApps\Project\FarmLink\frontend
    pnpm build
    pnpm dev

    cd E:\myApps\Project\FarmLink\backend
    pytest

Expect **105 passed**, same as before. No new tests in this dispatch; profile
editing is verified by hand below.

## What the endpoint does

`PATCH /auth/me` takes any subset of `{name, email, phone}`.

**`null` means "leave it alone." `""` means "clear it."** That distinction is
why every field is nullable rather than required. A form that always sends all
three cannot otherwise tell "I did not touch the phone field" from "I deleted
my phone number."

Email is checked for uniqueness before writing:

- another account already has it → 409
- it is your own current email → no-op, not an error

**The token is not reissued.** It carries only the user id and role, and neither
changes here. That is why you stay signed in after changing your email — and
why the form says so.

## Verify by hand

1. Sign in as `buyer@farmlink.demo` / `Demo123!`.
2. Go to `/profile`. An **Account** section now sits above addresses.
3. Change your name, save. The header updates without a page reload.
4. Change your email to a fresh address, save. **You stay signed in.**
5. Try an email another account already uses. Expect
   `Another account already uses that email` and no change.
6. Clear the phone field, save, reload. It stays empty.

Steps 4 and 6 are the two subtle behaviours.

## Known limitations

- **No password change.** Needs a current-password check and probably email
  confirmation. Its own dispatch.
- **No account deletion.** Admins can deactivate, but the row stays.
- **No email verification.** There is no mail sending anywhere in the project.
- **`phone` on an Address and `phone` on the account are unrelated.** One is a
  delivery contact, the other is yours. Nothing syncs them, and nothing should.
- **No unsaved-changes guard.** Navigating away mid-edit discards silently.
- **Still no listing edit or delete.** The most conspicuous gap in the app.

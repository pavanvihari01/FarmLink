# Dispatch #2 — Registration form

## What this archive contains

    FarmLink/frontend/src/pages/Register.tsx   (rewritten)
    FarmLink/frontend/src/lib/api.ts           (one type change)
    FarmLink/frontend/src/App.tsx              (one route prop)

Nothing else. No backend change, no CSS change, no new dependency.

## How to apply

Unzip at the project root:

    E:\myApps\Project

Then:

    cd E:\myApps\Project\FarmLink\frontend
    pnpm build
    pnpm dev

## What changed

### Register.tsx — marketing panel becomes a real form

`Register` previously rendered static copy with a "Choose your role" button
that just linked to `/login`. It now posts to the existing
`POST /auth/register` endpoint and logs the new user straight in.

Validation uses `react-hook-form` + `zod`, both already in `package.json` and
previously imported nowhere. The schema mirrors the backend's `RegisterInput`
field-for-field:

| Field | Rule | Backend equivalent |
| --- | --- | --- |
| name | 2–120 chars | `Field(min_length=2, max_length=120)` |
| email | valid address | `EmailStr` |
| password | min 8 chars | `Field(min_length=8)` |
| confirm | must equal password | **frontend only** |
| phone | optional | `str | None = None` |
| role | `buyer` or `farmer` | backend rejects anything else with 422 |

`confirm` has no backend counterpart. It exists purely to catch typos before
the request is sent, and is never transmitted.

Role selection is a two-button toggle built from the existing `.demo-list`
class rather than a `<select>`, so it matches the demo-login buttons visually.
The selected state uses an inline `style` — the only way to show selection
without editing `styles.css`, which this dispatch does not touch.

### api.ts — `register` payload is now typed

Was:

    register: (data: Record<string,string>) => ...

`Record<string,string>` cannot express an optional `phone`, so a blank phone
field would have been sent as `""` and stored as an empty string rather than
`NULL`. The signature is now an exported `RegisterPayload` type with
`phone?: string`. The request body and response handling are unchanged.

### App.tsx — `/register` route passes `onLogin`

Was:

    <Route path="/register" element={<Register />} />

Now:

    <Route path="/register" element={<Register onLogin={setUser} />} />

Without this the new user would authenticate successfully, receive a token,
and still appear signed out, because nothing could call `setUser`.

## Verify

    cd E:\myApps\Project\FarmLink\frontend
    pnpm build

Expect zero TypeScript errors. Then `pnpm dev` with the backend running, and:

1. Go to `/register`. Fill in a name, a fresh email, and a password of 8+
   characters. Pick **Farmer**. Submit.
2. You should land on `/dashboard` already signed in, with the header showing
   **Dashboard** and **Sign out** instead of **Sign in**.
3. Sign out. Go to `/register` again and submit the **same email**. Expect
   `An account already exists for that email` shown above the submit button,
   not a browser alert or a silent failure.
4. Submit with mismatched passwords. Expect `Passwords do not match` directly
   under the confirm field, and no network request.
5. Submit with a 7-character password. Expect `Password must be at least 8
   characters`, no network request.

Admin accounts cannot be created through this form. The backend rejects any
role other than `buyer` or `farmer` with a 422, and the UI only offers those
two. That is deliberate — admin accounts come from the seed.

## Known limitations

- **The dashboard is still hardcoded.** A freshly registered farmer has zero
  listings and zero orders, but `/dashboard` will show `Active listings: 7`,
  `Open orders: 4`, and `Expected demand: High`. This is dispatch #3.
- **Passwords are not strength-checked.** Only length, matching the backend.
- **No email verification.** Registration logs you in immediately.
- **`isSubmitting` disables the submit button but there is no request timeout.**
  A hung backend leaves the button reading "Creating account…" indefinitely.

# Dispatch #6 — Farmer order management + two corrections

## What this archive contains

Corrections to dispatch #5:

    FarmLink/frontend/src/pages/Profile.tsx    (compile fix)
    FarmLink/frontend/src/pages/Checkout.tsx   (dead code removed)

New in dispatch #6:

    FarmLink/frontend/src/pages/Orders.tsx     (farmer actions)
    FarmLink/frontend/src/lib/api.ts           (two methods added)

**Backend is unchanged.** `PATCH /orders/{id}/status` and
`POST /orders/{id}/reopen` were built in dispatch #4. This is the UI for them.

**`styles.css` is NOT touched.** Reuses `.button.small`, `.text-button`,
`.order-card`, `.order-head`, `.order-status`, `.tabs`, and `.result-banner`,
all of which already exist.

## How to apply

Unzip at the project root. Overwrite all four files.

    cd E:\myApps\Project\FarmLink\frontend
    pnpm build
    pnpm dev

No database change, no migration, no backend restart needed.

## Correction 1 — Profile.tsx did not compile

The form handlers were typed as:

    const addAddress = async (e: React.FormEvent<HTMLFormElement>) => {

`Profile.tsx` imports `{ useEffect, useState }` from `react` — there is no
`React` identifier in scope. With `jsx: "react-jsx"`, `React` is a UMD global,
and TypeScript rejects referencing a UMD global from inside a module:

    'React' refers to a UMD global, but the current file is a module.

`pnpm build` would have failed. Now imports the type directly:

    import { useEffect, useState, type FormEvent } from 'react';
    const addAddress = async (e: FormEvent<HTMLFormElement>) => {

If your build was already failing, this was why.

## Correction 2 — Checkout.tsx dead code

Declared `const nav = useNavigate()` and never used it. Removed, along with the
now-unused `useNavigate` import. Cosmetic — `noUnusedLocals` is not enabled, so
this never broke the build.

## Dispatch #6 — farmer actions

`Orders.tsx` now renders role-appropriate controls.

**Farmer**, by current status:

| Status | Buttons |
| --- | --- |
| `requested` | **Accept** (primary), Reject |
| `accepted` | **Mark completed** (primary) |
| `rejected` / `cancelled` | **Reopen** |
| `completed` | none — final |

**Buyer** is unchanged: **Cancel order** on `requested` and `accepted` only.

These mirror `ALLOWED_TRANSITIONS` in `backend/app/api/routes.py` exactly.
The UI cannot offer a move the server would reject with 409.

### Reopen reports capping

`POST /orders/{id}/reopen` returns the new quantity and whether it was reduced.
The UI surfaces that rather than silently shrinking the order:

> Order reopened at 5 units — only that much stock was left. Total is now
> Rs 50.00.

If the original quantity still fits, the message says so instead. This is what
the `capped` field is for — it was broken in dispatch #4 and fixed in the #4
patch, so **that patch must be applied** for this message to be accurate.

### Reopen when no stock remains

The backend returns 409 "No stock is available, so this order cannot be
reopened." The page shows that message above the list. The button stays visible
— there is no client-side pre-check, because stock can change between render
and click.

## Verify

    cd E:\myApps\Project\FarmLink\frontend
    pnpm build

Zero TypeScript errors. Then with the backend running:

1. Sign in as `buyer@farmlink.demo`, add something to the cart, and place an
   order.
2. Sign out. Sign in as `farmer@farmlink.demo`. Go to `/orders`.
3. The new order appears under **Open** with an `Accept` button.
4. Click **Accept**. The badge changes to `accepted` and a **Mark completed**
   button replaces the accept/reject pair.
5. Click **Mark completed**. It moves to the **Completed** tab.
6. Place another order as the buyer. As the farmer, click **Reject**.
7. The order moves to **Cancelled** and now shows a **Reopen** button.
8. Click **Reopen**. It returns to `requested`, and the notice reports the
   quantity — capped or not.

Step 8 is the one that proves the reopen flow end to end.

## Known limitations

- **The listing link still goes to `/marketplace`**, not to the specific
  listing. There is no `/listings/:id` route. Same as dispatch #5.
- **No farmer action on the dashboard.** The dashboard shows counts and links
  to the marketplace; order actions live only on `/orders`. Worth adding a
  shortcut later.
- **Admin sees the buyer view.** `Orders.tsx` branches on `role === 'farmer'`,
  so an admin gets the buyer layout with a Cancel button they cannot use —
  `update_order_status` allows admins any transition, but `isBuyer` is false
  for them, so no cancel button renders. Admins see a read-only list. Admin
  moderation is dispatch #9.
- **No optimistic update.** Every action refetches the whole list. At demo
  scale that is a fraction of a second; at hundreds of orders it would need
  per-row updates.
- **No confirmation dialog on Reject.** One click declines the order. Cancel
  and Reject are both single-click and both reversible (Reopen), so this was
  deliberate — but it is a misclick risk.

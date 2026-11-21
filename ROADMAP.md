# Roadmap

Things I might add to bookings. Version 1.0.0 covers the whole loop for one small
business (set up services, staff and hours, take bookings online, remind, run the
day from the calendar, look back on the dashboard), so nothing here is promised or
scheduled. These are ideas, written down with enough detail that I (or anyone else)
can pick one up later without starting from zero. Items may change, move between
groups or be dropped.

What the app does today is in the [README](README.md), including its
"Assumptions and limits" section, which several items below lift.

- **Next**: small or well understood. I would start with these.
- **Later**: worth doing, but bigger or waiting on a decision.
- **Maybe**: not sure yet that they are worth the extra complexity.

Sizes are rough: **S** is an evening or two, **M** a few evenings up to a couple of
weekends, **L** several weeks of spare time.

Each item is meant to fit in one pull request and to be covered by the test suite.
Tests live in `<app>/tests/` and run with pytest-django against PostgreSQL, through
the Django test client for views. There are no browser tests. The rules that matter
are kept out of views so they can be tested on their own: free-time logic in the pure
functions of `scheduling/slots.py`, booking state changes in
`appointments/services.py`, calendar layout in `dashboard/calendar.py`, numbers in
`dashboard/stats.py`. New logic belongs in modules like those, not in a view or a
template. Model changes bring their own migration in the app's `migrations/` folder;
CI runs `makemigrations --check`, so a forgotten one fails the build.

When an item ships, its row in the Overview says `Shipped` in the Group column, its
section moves under a `## Shipped` heading at the end with one paragraph on what was
built and what was left out, and the same pull request updates the README (features,
configuration table, assumptions and limits) and adds an entry under a
`## Unreleased` heading at the top of `CHANGELOG.md`.

"Depends on" lists real prerequisites only. Items that merely touch the same file are
not listed there; the bigger overlaps are mentioned in the items.

## Overview

| #   | Item                                        | Group | Area          | Size | Depends on |
| --- | ------------------------------------------- | ----- | ------------- | ---- | ---------- |
| 1   | Run the scheduled commands in the stack     | Next  | ops           | S    | -          |
| 2   | Emails that are retried, not lost           | Next  | notifications | M    | -          |
| 3   | Move and edit bookings from the dashboard   | Next  | calendar      | M    | -          |
| 4   | Slow down password guessing                 | Next  | security      | S    | -          |
| 5   | Limits on the public booking page           | Next  | security      | S    | -          |
| 6   | Backups, restore and upgrades               | Later | ops           | S    | -          |
| 7   | Staff logins and roles                      | Later | accounts      | L    | -          |
| 8   | Waiting list for full days                  | Later | booking       | M    | 2          |
| 9   | Recurring bookings                          | Later | booking       | M    | -          |
| 10  | Several services in one visit               | Later | booking       | M    | -          |
| 11  | Classes with several places                 | Later | booking       | L    | -          |
| 12  | Questions on the booking form               | Later | booking       | M    | -          |
| 13  | Customer records                            | Later | customers     | M    | -          |
| 14  | Erasing and exporting a customer's data     | Later | privacy       | S    | 13         |
| 15  | Busy times from an outside calendar         | Later | scheduling    | M    | -          |
| 16  | New links for feeds and bookings            | Later | security      | S    | -          |
| 17  | Partly closed days and business breaks      | Later | scheduling    | S    | -          |
| 18  | Currency and price display                  | Later | settings      | S    | -          |
| 19  | Reminder timing                             | Later | notifications | S    | 2          |
| 20  | Cancellation reasons and late cancellations | Later | booking       | S    | -          |
| 21  | A follow-up email after the visit           | Later | notifications | S    | 2          |
| 22  | History of changes to a booking             | Later | calendar      | M    | -          |
| 23  | Drag to move on the calendar                | Later | calendar      | M    | 3          |
| 24  | Booking page on another website             | Later | booking       | M    | 5          |
| 25  | Booking page in other languages             | Later | booking       | M    | -          |
| 26  | Accessibility pass                          | Later | ui            | M    | -          |
| 27  | Browser tests for the booking flow          | Later | tests         | M    | -          |
| 28  | A content security policy                   | Later | security      | S    | -          |
| 29  | Health and metrics for running it           | Later | ops           | S    | 1          |
| 30  | Dashboard numbers that follow the business  | Later | dashboard     | S    | -          |
| 31  | Online payments and deposits                | Maybe | payments      | L    | 2          |
| 32  | Text message reminders                      | Maybe | notifications | M    | 19         |
| 33  | Several locations per account               | Maybe | businesses    | L    | 7          |
| 34  | Two-step sign-in                            | Maybe | accounts      | M    | 4          |
| 35  | "My bookings" for returning customers       | Maybe | customers     | M    | 13         |
| 36  | Webhooks and a JSON API                     | Maybe | api           | L    | 7          |
| 37  | Public holidays as closed days              | Maybe | scheduling    | S    | 17         |

## Next

### 1. Run the scheduled commands in the stack

Reminders and the expiry of unconfirmed bookings only happen when someone runs
`send_reminders` and `expire_bookings`. The README asks for cron, but
`docker-compose.yml` has no scheduler, so with `docker compose up` no reminder is
ever sent and pending bookings are never marked expired. The hold still stops
counting after 30 minutes (`Booking.objects.blocking` checks `hold_expires_at`), so
nothing is double-booked, but the calendar and lists keep showing "Awaiting
confirmation" for bookings that will never happen.

- A `run_scheduled` management command in `core` that loops: run
  `expire_unconfirmed()` and `send_due_reminders()` every `SCHEDULE_INTERVAL_SECONDS`
  (default 120), log what each did, and exit cleanly on SIGTERM.
- A `scheduler` service in `docker-compose.yml` with the app image and
  `command: python manage.py run_scheduled`, `restart: unless-stopped`. It does not
  run migrations; it waits for the app's health check.
- Both functions are already safe to run often and in parallel (reminders claim the
  row with an `update` before sending), so two schedulers by mistake do no harm.
- Tricky: a crash inside one run must not kill the loop. Catch, log with the
  traceback, and carry on at the next tick.
- Tricky: the entrypoint seeds the demo when `SEED_DEMO=true`. The scheduler should
  not; give it its own entrypoint argument or skip the seed when the command is the
  scheduler.
- The README section "Scheduled commands" says that compose does this now and cron
  is for running without Docker.
- Tests: the command with a fake clock runs both functions and stops after one tick
  in test mode (`--once`); an exception in one run is logged and the next run goes
  ahead.

### 2. Emails that are retried, not lost

Emails are sent inline, after the commit (`_after_commit` in
`appointments/services.py`), and `_send` in `notifications/emails.py` catches every
exception and logs it. A mail provider that is down for a minute loses every
confirmation in that minute, and nobody finds out unless they read the logs. The
reminder path is worse: `send_due_reminders` sets `reminder_sent_at` before calling
`booking_reminder`, so a failed send is recorded as sent and never tried again.

- An outbox: an `OutgoingEmail` model in `notifications` (`booking`, `kind`,
  `to`, rendered subject and bodies, attachment, `status`, `attempts`,
  `next_attempt_at`, `last_error`, `sent_at`). The booking events write a row
  inside the same transaction as the change, which is better than `on_commit`: the
  email exists exactly when the change does.
- A `send_outbox` function, called by the scheduler from item 1 and right after the
  commit for speed, that sends due rows, marks them sent, or schedules a retry with
  growing gaps (1, 5, 15, 60 minutes, then give up after a day).
- Rows claimed with `select_for_update(skip_locked=True)`, so the inline send and
  the scheduler never send the same row twice.
- Reminders become "write an outbox row" instead of "send"; `reminder_sent_at` then
  means "queued", which is what the claim needs.
- The booking panel shows the emails for a booking and their state; failed ones get
  a "send again" button.
- Tricky: rendering at write time freezes the content, which is right (the email
  describes the booking as it was when the event happened) but means a template fix
  does not reach queued rows. Fine.
- Tricky: the outbox grows. Delete sent rows after 90 days in the same scheduler
  loop.
- Undecided: whether to render at send time instead, to keep the table small. I lean
  towards render at write time; the bodies are short.
- Tests: in `notifications/tests/`: a send that raises is retried later and
  `last_error` kept; a reminder that fails is still sent on the next run; two
  concurrent `send_outbox` calls send once; a rolled back booking leaves no row.

### 3. Move and edit bookings from the dashboard

The business cannot move a booking. The booking panel has outcome, cancel and an
internal note (`dashboard/urls.py`), and moving only exists on the customer's link
(`manage_reschedule`). When a customer phones to move their appointment, the
business has to cancel it (which emails a cancellation) and book again (which emails
a new booking with a new reference). Customer details cannot be corrected either:
a typo in the email address means the customer never gets anything.

- "Move" in the booking panel: a day and time picker reusing the slots partial the
  customer uses, with the same staff member by default and an option to pick another
  one who offers the service. `reschedule_booking` takes an optional `staff` and the
  same `override` flag `create_booking` has for times outside the free slots.
- "Edit details": name, email, phone and the customer's note. Changing the email
  sends the confirmation again to the new address, since the old one presumably
  never arrived.
- The customer gets the "moved" email as today; a checkbox "don't email the
  customer" covers the case where it was agreed on the phone.
- Lifting "Moving a booking keeps the same staff member" in the README's limits.
- Tricky: moving to another staff member needs both staff rows locked
  (`_lock_staff` already sorts by id, so two moves in opposite directions cannot
  deadlock).
- Tricky: a business move ignores `cancellation_notice_hours`, which only limits
  customers. It should still refuse bookings that are closed (`is_open`).
- Tricky: the staff feed and the staff copy email. A move between staff should tell
  both.
- Tests: in `appointments/tests/` for the service (new staff, override, lock order);
  in `dashboard/tests/` for the views, including another business's booking giving
  a 404.

### 4. Slow down password guessing

Business accounts sign in with email and password through Django's `LoginView`, and
nothing limits failed attempts. The password reset form can also be used to send
reset emails to any address as fast as someone can post the form. Django ships no
throttling of its own.

- A small limiter in `core/ratelimit.py` on Django's cache: a counter per key with
  an expiry. Keys: email plus client address for failed sign-ins (10 per 15
  minutes), address alone for sign-ups and reset requests (5 per hour).
- `LoginView.form_invalid` counts a failure; `form_valid` resets. When a key is
  over the limit the form shows "Too many attempts, try again in N minutes" and does
  not check the password at all.
- The cache is the local memory cache today (no `CACHES` setting). With several
  gunicorn workers each worker counts on its own. Use Django's database cache
  (`createcachetable` in the entrypoint) so the count is shared and survives a
  restart, which needs no new service.
- Tricky: the client address. Behind a proxy (`BEHIND_PROXY=true`) it is in
  `X-Forwarded-For`, but only the proxy's own entry can be trusted. Take the
  right-most address added by the trusted proxy, configured with a
  `TRUSTED_PROXY_COUNT` setting, default 1 when behind a proxy and 0 otherwise.
- Tests: in `accounts/tests/test_auth.py`: the eleventh failure is refused even
  with the right password, success resets, reset emails are limited per address.

### 5. Limits on the public booking page

The booking page needs no account, which is the point, and it has a honeypot field
against simple bots (`test_honeypot_stops_bots`). Nothing else limits it. Anyone can
create bookings in a loop, each holding a slot and sending an email to whatever
address was typed in, from the business's name. That fills a day's calendar and
turns the app into a way to send mail to strangers.

- Use the limiter from item 4: per client address, at most N bookings per hour
  (`PUBLIC_BOOKINGS_PER_HOUR`, default 10) and M per day across all businesses; per
  customer email, at most a few open future bookings at the same business.
- With `require_confirmation` on, an unconfirmed booking already only holds the
  slot for 30 minutes. Count unconfirmed bookings per address separately, with a
  lower limit, since they are the cheapest to abuse.
- The `slots` and `manage` views are reads; a generous per-address limit stops
  scraping and guessing without bothering anyone.
- Tricky: a salon's own front desk wifi books many times a day for walk-ins. Those
  go through the dashboard (`Source.DASHBOARD`), which is signed in and not
  limited. The limit only applies to online bookings.
- Tricky: telling the customer. A plain "too many bookings from your connection,
  please call the business" with the business phone number is better than an
  error page.
- Tests: in `appointments/tests/test_booking_flow.py`: the limit per address and per
  email, dashboard bookings not counted.

## Later

### 6. Backups, restore and upgrades

All data is in the `db-data` volume, and the README's only note is that
`docker compose down -v` deletes it. For a business that runs its diary on this, a
lost volume is a lost diary.

- A `backup` service under a compose profile that runs `pg_dump -Fc` into
  `./backups` with a dated name and keeps the last `BACKUP_KEEP` files. The
  scheduler from item 1 could call it, but a host cron line running
  `docker compose --profile backup run --rm backup` is simpler and does not need
  the app image to carry the PostgreSQL client.
- A `restore` command in the same service, documented with the steps around it:
  stop app and scheduler, restore, start again (migrations run on start and bring an
  older dump forward).
- A "Running it for real" page under `docs/` (new folder) with backups, restore,
  moving to another server, and upgrading: back up, pull, `up --build`. A major
  PostgreSQL upgrade cannot reuse the volume and needs dump and restore.
- Tricky: `SECRET_KEY` is part of the backup in practice. Restoring without it breaks
  every booking link and staff feed already sent (the README says so in
  Troubleshooting). The docs should say to keep it with the backups.
- Tests: a CI step that seeds, dumps, drops, restores and checks a booking count.

### 7. Staff logins and roles

"Staff don't log in" is the first limit in the README. Staff follow their bookings
through the calendar feed and email copies, and the owner does every change. In a
salon with four chairs that means the owner's password is on the front desk.

- Roles on a new `Membership` (user, business, role): owner (everything, including
  settings and deletion), manager (bookings, customers, staff hours and time off),
  staff (their own calendar and bookings, their own time off, read-only otherwise).
- `StaffMember` gets an optional link to a user, so a staff login sees "my day".
- Invites by email with a signed, expiring link, reusing the account sign-up form.
- Every view decorated with `business_required` today learns the role. That is the
  bulk of the work: one decorator that takes the required role, and a test per view
  that a staff login gets 403 where it should.
- Tricky: `Business.owner` is a one-to-one field and `Business.for_user` reads it.
  Keep the owner field for the account that pays the bills and deletes the business,
  and resolve "which business is this user in" through memberships.
- Tricky: a user who works at two businesses. Allow several memberships and a
  switcher; it costs little once memberships exist, and item 33 needs it.
- Tests: a role matrix over every dashboard and settings view, invites, staff seeing
  only their own bookings.

### 8. Waiting list for full days

When a day is full the booking page shows no times, and the customer goes
elsewhere. Then someone cancels and the slot stays empty.

- On a day without free times, "Tell me if something opens up" takes name, email,
  service and optionally staff and a time range. A `WaitlistEntry` model with an
  expiry at the end of that day.
- When a booking is cancelled or expires (`cancel_booking`, `expire_unconfirmed`),
  find entries for that day whose request now fits, using `available_slots`, and
  email them a link to the booking page for that day. Through the outbox from item 2.
- First come, first served by default: email entries in the order they joined, a
  few at a time, so ten people do not race for one slot. The others are emailed if
  the slot is still free after an hour.
- Tricky: no hold. Offering a hold per waiting customer makes the slot logic aware
  of offers, which is a lot. The email says "first to book gets it".
- Tricky: spam. Waitlist sign-ups need the same limits as bookings (item 5).
- Tests: a cancellation emails the right entries in order; entries for other days or
  services are left alone; expired entries are removed.

### 9. Recurring bookings

Tutors, physios and cleaners see the same people at the same time every week. Each
of those is booked one by one today, by the business or by the customer.

- From the dashboard, "repeat this booking" every 1, 2 or 4 weeks, for N times or
  until a date. Each occurrence is a normal `Booking` linked by a `series_id`, so
  slots, calendar, stats and emails keep working.
- All occurrences are checked first, then created in one transaction; the business
  sees which ones are not free (holiday, time off) and can skip them or book them
  with the override.
- Cancelling offers "this one" or "this and the following". The customer's link
  manages one occurrence at a time.
- Tricky: emails. One email for the series with all dates, not twenty. The
  calendar file can hold one event per occurrence (an `RRULE` breaks as soon as one
  occurrence moves).
- Tricky: online recurring bookings by customers are more abuse-prone; start with
  the dashboard only.
- Tests: creation with conflicts, cancelling the rest of a series, the series email.

### 10. Several services in one visit

"A booking is with one staff member for one service." A cut and a colour, or a
consultation followed by a treatment, are two bookings today, made one after the
other, with no guarantee they line up.

- On the booking page, "add another service" after picking the first. The visit's
  duration is the sum, the buffers are the first service's before and the last one's
  after, and the staff member must offer all of them.
- Data: a visit is one `Booking` with `BookingItem` rows (service, duration, price),
  and the booking's own service becomes the first item. Lists and stats sum items
  for revenue and count services by item.
- `scheduling/slots.py` already works on a `ServiceSpec` (duration and buffers);
  building one from several services is a pure function and the rest of the slot
  logic does not change.
- Tricky: the migration. Every existing booking gets one item copied from its own
  fields, and the old fields stay for a release so nothing reads an empty table.
- Undecided: different staff for each service in one visit (colour by one person,
  cut by another). That is a different slot problem; leave it out.
- Tests: slots for a combined spec, a visit across a split shift refused, revenue in
  stats.

### 11. Classes with several places

Yoga studios, group lessons and workshops sell places in one session, not a staff
member's time. That model does not exist here: a booking blocks the staff member.

- A `capacity` on `Service` (1 means today's behaviour). For capacity over 1, a
  session is a time on a staff member's schedule, and bookings join it until it is
  full. The slot logic treats a staff member as busy only while a session is full or
  for other services.
- Sessions can be generated from working hours (every hour) or set by hand as a
  timetable; I lean towards a timetable, since classes run at fixed times.
- The booking page shows places left; the calendar shows one block per session with
  a list of attendees.
- Tricky: locking. Two customers taking the last place must not both get it; lock
  the session row, not only the staff row.
- Tricky: cancelling a whole session (teacher ill) emails everyone in it.
- Large because it touches slots, booking, calendar, stats and emails. A separate
  item from 10 on purpose.
- Tests: places count down, the last place is taken once under concurrency, session
  cancellation.

### 12. Questions on the booking form

The booking form asks for name, email, phone and a note. A physio needs "Where does
it hurt?", a tutor "Which year?", a salon "First visit?".

- Per service, a list of questions: short text, long text, yes or no, a choice from a
  list; each required or optional. Stored as JSON on the service and validated with a
  form built from it at request time.
- Answers stored as JSON on the booking, shown in the booking panel and in the
  business email, included in the CSV export as one column per question.
- Tricky: a question changed or removed after bookings answered it. Store the
  question text with each answer so old bookings still read correctly.
- Tricky: health questions are sensitive data. Keep them out of the staff calendar
  feed (`event_lines(include_customer=True)` includes the customer note today) and
  say so in the settings.
- Tests: form building and validation per type; answers in the panel, email and CSV.

### 13. Customer records

Customers are not a table: the customer list groups bookings by email
(`dashboard/lists.py`). A customer who books with two addresses is two customers, a
phone booking with no email cannot be found again, and there is nowhere to keep
"allergic to ammonia" except the internal note of every booking.

- A `Customer` model per business (name, email, phone, notes, created) and a
  foreign key on `Booking`. Online bookings match an existing customer by email
  (case-insensitive) and otherwise create one.
- The data migration creates customers from existing bookings grouped as the list
  groups them today.
- Customer page: details, notes, all bookings, no-show count; "merge into" for
  duplicates; "book again" prefilled.
- The dashboard's new booking form picks an existing customer by search.
- Tricky: matching on phone. Phone formats vary; normalise digits for search, never
  merge automatically on phone.
- Tricky: a booking keeps its own copy of name and email (what was typed then) as
  well as the link. Emails go to the booking's address.
- Tests: matching, merging moves bookings, the migration on existing data.

### 14. Erasing and exporting a customer's data

A business that serves people in the EU or UK has to answer "delete my data" and
"what do you have on me". There is no way to do either here except the Django admin.

- On the customer page from item 13: "Download data" (bookings, answers, notes as
  JSON) and "Erase": names, emails, phones, notes and answers on every booking are
  replaced with a placeholder, and the customer row is deleted. The bookings stay,
  so revenue and staff history still add up.
- A retention setting: erase customer details from bookings older than N months
  automatically, run by the scheduler from item 1. Off by default.
- Tricky: emails already in the outbox (item 2) for that customer. Delete unsent
  rows on erasure.
- Tests: erasure leaves counts and revenue unchanged and no personal data in the
  booking rows; retention with a fixed clock.

### 15. Busy times from an outside calendar

Staff have lives in other calendars: a dentist appointment in Google Calendar, a
second job. Today that has to be entered again as time off, or the staff member
gets booked over it.

- Per staff member, an optional iCalendar url (every major calendar can publish a
  private one). The scheduler fetches it every 15 minutes and stores busy intervals
  (`ExternalBusy`: staff, start, end, feed). `load_schedules` adds them to `busy`
  like time off.
- Parse only what is needed: `VEVENT` start, end, `RRULE` expansion within the
  booking window, `TRANSP:TRANSPARENT` skipped, all-day events as full days in the
  business's time zone. A small parser is possible, but recurrence rules are where
  bugs live; the `icalendar` and `recurring-ical-events` packages are the safer
  choice.
- Tricky: fetching urls a business user typed. The same care as any server-side
  fetch: http and https only, refuse private addresses, size and time limits.
- Tricky: the feed is down. Keep the last good copy and show its age on the staff
  page; never treat a failed fetch as "nothing busy" silently.
- Not in this item: writing bookings into the outside calendar. The staff feed
  already lets a phone subscribe.
- Tests: parsing with recurring and all-day events across a clock change; slots
  blocked by external busy times; a failed fetch keeps the old data.

### 16. New links for feeds and bookings

Both kinds of private link are signatures of a fixed value: the staff feed signs the
staff member's id (`feed_token` in `dashboard/feeds.py`) and the booking link signs
the booking's `public_id` (`appointments/tokens.py`). They never change. A staff
member who leaves keeps a working feed of the business's bookings with customer names
and phone numbers until `SECRET_KEY` changes, which breaks every link at once.

- A `feed_version` integer on `StaffMember`, part of what the feed signs. "Get a new
  link" on the staff page bumps it; deactivating a staff member bumps it too.
- For booking links, a `link_version` on `Booking` the same way, bumped by an
  action in the booking panel ("send a new link"), for the case where a customer
  forwarded their email.
- Tricky: old links. A feed signed without a version must keep working until the
  first rotation, or every subscribed phone breaks on upgrade. Treat a missing
  version as version 0.
- Also: deactivated staff should not have a working feed at all; `staff_feed` does not
  check `is_active` today.
- Tests: rotation breaks the old link and the new one works; old-format links still
  work at version 0; inactive staff get a 404.

### 17. Partly closed days and business breaks

`ClosedDay` is a whole date. Closing at 13:00 on Christmas Eve, or for a two hour
team training, means time off for every staff member one by one.

- Optional `start_time` and `end_time` on `ClosedDay` (both empty means the whole
  day). In `load_schedules` a partly closed day becomes a busy interval for every
  staff member; the whole-day check in `available_slots` and `available_days` stays
  for the full-day case.
- A `TimeOff` with an end before its start is only caught by the form; a check
  constraint in the same migration makes it impossible, as `WorkingHours` already
  has.
- Tricky: existing bookings inside a newly closed period. Show them after saving
  ("3 bookings are in this time") with links; do not cancel anything automatically.
- Tests: slots around a partial closure in the business's time zone, the constraint.

### 18. Currency and price display

"Prices are shown as plain amounts with no currency." A customer sees "45.00" on the
booking page and in emails, and the dashboard's revenue has no unit.

- A `currency` on `Business` (ISO code, default from the time zone's country would be
  clever and wrong; ask during setup). A template filter `money` that formats with the
  symbol and the business's locale conventions for the few currencies people will
  pick, through Python's `babel` if it is acceptable as a dependency, or a small
  table otherwise.
- Every place that prints a price uses the filter: booking pages, emails, booking
  panel, lists, CSV (amount and currency in separate columns), dashboard.
- Tests: the filter for a few currencies; a grep-style test that no template prints
  `.price` without the filter.

### 19. Reminder timing

One reminder, 24 hours before (`REMINDER_LEAD` in `notifications/reminders.py`), and
none for bookings made less than a day ahead. A physio with morning appointments
wants a reminder the evening before; a hairdresser wants one two hours before as
well.

- Per business, up to two reminders, each a number of hours before the start. The
  claim moves from `reminder_sent_at` on the booking to a `Reminder` row per booking
  and lead time, unique, so each is sent once.
- Through the outbox from item 2, so a failed reminder is retried and not marked
  sent.
- Tricky: moving a booking resets reminders (it sets `reminder_sent_at = None`
  today); with rows, delete the unsent ones and keep the sent ones for history.
- Tricky: "the evening before" is a local time, not a number of hours. Allow "at
  18:00 the day before" as a second kind, computed in the business's time zone.
- Tests: two leads, short-notice bookings, a move after the first reminder, the
  evening-before kind across a clock change.

### 20. Cancellation reasons and late cancellations

A cancellation records who cancelled and when. The dashboard shows a cancellation
rate, but not why, and a customer who cancels inside the notice period can only do
it by phone, which is then recorded as the business cancelling.

- An optional reason on cancel, a short list plus free text, on the customer's page
  and in the booking panel. Shown on the dashboard as counts per reason.
- `cancelled_late` (boolean) computed at cancel time from
  `cancellation_notice_hours`, so a business cancelling on behalf of a customer can
  record "customer, late". The dashboard rate can then separate late cancellations
  and no-shows from the rest.
- Tests: reasons saved and counted; late flag at the boundary.

### 21. A follow-up email after the visit

After a completed appointment the business may want to thank the customer, ask
them to book again or leave a review somewhere.

- Per business, an optional follow-up email sent N hours after a booking is marked
  completed, with an editable text and an optional link (their review page, their
  booking page). Queued by `set_outcome` through the outbox from item 2 with a
  `next_attempt_at` in the future, so no new scheduling is needed.
- Unsubscribe: a signed link in the email that turns off follow-ups for that email
  address at that business. Marketing-like emails need it.
- Tests: queued on completion, not on no-show, not after unsubscribing.

### 22. History of changes to a booking

A booking has `created_at`, `updated_at`, `cancelled_at` and `cancelled_by`. Who
moved it, from when to when, who changed the note, whether the customer or the
business made the change: none of that is kept. When a customer says "I never
cancelled", there is nothing to look at.

- A `BookingEvent` model (booking, kind, actor, from and to values as JSON, at)
  written by every function in `appointments/services.py` and by the note view. The
  actor is a user, "customer via link", or "system" (expiry, scheduler).
- Shown as a short timeline in the booking panel.
- Tricky: the events must be written inside the same transaction as the change; the
  services already use `transaction.atomic`, so this is the place.
- Tests: every service function writes its event with the right actor; the panel
  shows them in order.

### 23. Drag to move on the calendar

With item 3 a booking can be moved from its panel. On a busy day the natural way is
to drag it to another time or another staff member's column, as every calendar app
does.

- Draggable blocks in the day and week views (`dashboard/calendar.py` already lays
  out positions), dropping posts to the move endpoint from item 3 with the new start
  and staff, snapped to the business's slot interval. htmx swaps the day.
- A drop on a time that is not free asks "book outside free times?" (the override).
- Tricky: keyboard and touch. Dragging needs an alternative; the panel's "Move" from
  item 3 is that alternative, and the calendar should say so.
- Tricky: a small amount of custom JavaScript in `static/js/app.js`; keep the drag
  code free of a framework and test the snapping as a pure function on the server.
- Tests: the endpoint with snapped times; the conflict answer.

### 24. Booking page on another website

Businesses already have a website and want the booking form on it, not a link away.
`X_FRAME_OPTIONS = "DENY"` stops any framing, which is right for the dashboard.

- An embeddable version of the public pages (`/b/<slug>/?embed=1`, or a separate
  url prefix) without the page chrome, allowed in frames from origins listed in the
  business settings through `Content-Security-Policy: frame-ancestors` on those
  responses only. The dashboard keeps `DENY`.
- A snippet in the settings: an `iframe` and a few lines of script that resize it to
  its content with `postMessage`.
- Tricky: cookies in frames. The public pages need the CSRF cookie for the booking
  POST; in a third-party frame browsers block it. Use a CSRF token in the form only
  (no cookie) for the embedded pages, or `SameSite=None; Secure` for that cookie,
  which needs https.
- Depends on item 5: an embedded form is easier to abuse from someone else's page.
- Tests: headers on embedded and normal pages; the booking POST works without the
  CSRF cookie in embed mode.

### 25. Booking page in other languages

Everything a customer sees is English: booking pages, emails, the calendar file.
Small businesses are in every country.

- Django's translation machinery on the public templates, the customer emails and
  the strings in `appointments/views.py` and `notifications/emails.py`. A `language`
  on `Business` chooses the language of its public pages and customer emails; the
  dashboard can stay English at first.
- Dates and times through Django's localised formats instead of the fixed
  formats in templates (`date:"D j M Y"`, `date:"H:i"`).
- One extra language shipped with the item (whichever I can check properly), so the
  machinery is proved.
- Tricky: emails are rendered outside a request; activate the business's language
  around rendering.
- Tests: the public page and an email in the second language; untranslated strings
  fall back to English.

### 26. Accessibility pass

The booking page is the part most people will use, on phones, often in a hurry. It
has a day picker, time buttons loaded by htmx and a form.

- The day picker and time list as real buttons with labels that say the full date
  and time ("Tuesday 3 March, 10:30, with Ana"), and an `aria-live` region that
  announces when htmx has loaded new times.
- Focus moves to the time list after picking a day and to the form after picking a
  time; error messages linked to their fields.
- The accent colour is chosen by the business (`accent_color`). Check its contrast
  against white text when saved and warn, or pick a dark or light text colour
  automatically.
- The calendar in the dashboard is a visual grid; a list view of the same day for
  screen readers is cheaper than making the grid accessible.
- Tests: view tests for the labels and live region; a contrast check function with
  unit tests.

### 27. Browser tests for the booking flow

Tests use the Django client, which does not run htmx. The booking page is several
htmx swaps (service, staff, day, times, form), the reschedule page the same, and a
broken `hx-target` would pass every test.

- Playwright with pytest against `live_server`, in a separate CI job: book as a
  customer, confirm from the email (read from Django's `locmem` outbox), move and
  cancel from the link, and add a booking from the dashboard.
- Tricky: times. Freeze "now" for the server with a setting the tests can set, or
  pick slots relative to the real clock; the slot logic depends on minimum notice.
- Keep it to a handful of flows; the Django client stays the main level.

### 28. A content security policy

Security headers are set (`nosniff`, `Referrer-Policy`, `X-Frame-Options`, HSTS when
configured), but no content security policy. The public templates print
business-supplied text (description, service names) and customers' notes appear in
the dashboard; Django escapes them, and a policy is the second line if a `|safe`
ever slips in.

- A middleware that sets
  `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:;
frame-ancestors 'none'; form-action 'self'; base-uri 'none'`.
- Tricky: `public_base.html` writes the accent colour in an inline `<style>` block.
  Move it to a `style` attribute on the body with a CSS variable (allowed by
  `style-src` only with `'unsafe-inline'`), or serve a tiny per-business stylesheet,
  or use a nonce. I lean towards the nonce for that one block.
- Tricky: htmx can evaluate code from attributes and run scripts in swapped
  responses. The templates use no `hx-on` today; set `htmx.config.allowEval = false`
  and `htmx.config.allowScriptTags = false` so it stays that way.
- Tricky: item 24 needs a different `frame-ancestors` for embedded pages.
- Tests: the header on every kind of response; a template test that no inline script
  is left.

### 29. Health and metrics for running it

`/healthz` checks the app and the database, logs can be JSON. Nothing tells the owner
that reminders stopped going out or that the mail server has rejected everything
since Tuesday.

- `/healthz` also reports the scheduler's last run (item 1 writes a timestamp) and
  the number of failed emails in the outbox (item 2), with a `degraded` status when
  the scheduler is late or failures pile up. It stays 200 for the process check; a
  separate `/readyz` returns 503 when the database is down.
- A short "system" box on the dashboard for the owner: last reminder run, emails
  failing. People running this will not read logs.
- Optional `/metrics` in Prometheus text format behind a token: bookings created,
  emails sent and failed, request durations.
- Tests: the health answers for a late scheduler and for failed emails.

### 30. Dashboard numbers that follow the business

The dashboard has revenue for the week and month, rates and bookings per week, all
in the business's time zone (`dashboard/stats.py`). It cannot show another period,
compare with the last one, or split by staff member, which is the first thing an
owner with staff asks.

- A period picker (this week, last week, this month, last month, a custom range) and
  the same numbers per staff member and per service, with the previous period next to
  them.
- Utilisation: booked minutes over working minutes per staff member, from working
  hours minus time off. That is the number that tells an owner whether to hire.
- Tricky: utilisation needs the working hours of past weeks as they were, and only
  the current hours are stored. Accept that and say it on the page, or keep a
  history of hours changes; I would accept it.
- Tests: stats over a range with a clock change in it; utilisation with time off.

## Maybe

### 31. Online payments and deposits

"There are no online payments." No-shows cost small businesses real money, and a
deposit at booking is the common cure. It needs a payment provider, which is a hosted
service, so it can only ever be optional.

- An optional Stripe integration (or a provider interface with Stripe as the one
  implementation): a deposit amount or percentage per service, a Checkout session
  after the booking form, the booking held as pending until the webhook confirms
  payment, the same way `require_confirmation` holds it today.
- Refunds on cancellation inside the notice period, none after it.
- Tricky: webhooks must be verified, idempotent and able to arrive before or after
  the customer returns to the page.
- Tricky: money handling brings tax and receipts questions I do not want this app
  to answer. That is why it is Maybe.

### 32. Text message reminders

Emails are easy to miss; text messages are what most booking apps use for
reminders. They need an SMS gateway, which is a paid hosted service.

- A provider interface with one implementation that posts to a configurable HTTP
  endpoint (works with most gateways, including self-hosted ones on an Android
  phone), off unless configured. Reminders from item 19 go by SMS when the business
  turns it on and the customer gave a mobile number.
- Tricky: phone numbers are free text today. Normalising to E.164 needs a country,
  which the business's time zone does not reliably give; ask in settings.
- Tricky: consent and opt-out ("reply STOP") depend on the country and the gateway.

### 33. Several locations per account

"One business per account." A business with two salons runs two accounts, with two
logins and two dashboards.

- With memberships from item 7, one user can belong to several businesses already.
  This item adds a switcher in the dashboard and an overview across them, and lets a
  staff member work at more than one location (their busy time must count across
  both).
- Tricky: a staff member at two locations means `load_schedules` has to see bookings
  from both businesses for that person, which breaks the clean "everything is per
  business" rule. That is the reason it is Maybe.

### 34. Two-step sign-in

Business accounts hold customers' names, emails and phone numbers. Email and
password is the only protection.

- TOTP with an authenticator app, recovery codes, and a "remember this device for 30
  days" cookie. A small amount of code on the standard library (`hmac`), or
  `django-otp` if a dependency is acceptable.
- Required for owners once item 7 adds staff logins? I would offer it, not require
  it.
- Tests: RFC 6238 test vectors, sign-in with and without a code, recovery codes used
  once.

### 35. "My bookings" for returning customers

Customers manage one booking at a time from its link. Someone with three upcoming
appointments needs three emails to find them.

- On the business page, "Find my bookings": enter an email, receive a link (signed,
  expiring in an hour) to a page listing that email's upcoming bookings at that
  business, each with its manage link.
- Tricky: the page must not reveal whether an email has bookings; the answer is
  always "if there are bookings for this address, we have sent a link".
- Depends on item 13 for matching bookings to one customer.

### 36. Webhooks and a JSON API

Businesses that use other tools (an accounting app, a newsletter) want bookings to
flow there. Today the only way out is the CSV export.

- Webhooks: per business, a url and a secret; events for booking created, moved,
  cancelled, completed, sent through a queue like the email outbox (item 2) with an
  HMAC signature and retries.
- A read-only JSON API with personal tokens for bookings, customers and services.
- Tricky: the same care as any server-side fetch for webhook urls (no private
  addresses).
- Depends on item 7 so API tokens belong to a user with a role.

### 37. Public holidays as closed days

Bank holidays are entered by hand each year in the closed days list.

- "Add public holidays" on the closed days page: pick a country and region, see the
  next twelve months of holidays from the `holidays` package (offline data, no
  service), tick the ones the business closes on.
- Depends on item 17 only if half-day holidays should be offered.
- Small, but a new dependency with yearly data updates; Maybe until someone asks.

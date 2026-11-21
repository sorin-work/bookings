# bookings

Online booking for small service businesses: salons, tutors, physios and anyone else
who works by appointment. The business sets up its services, staff and working hours;
customers pick a free time on the business's booking page, with no account needed, and
manage their booking from a signed link in the confirmation email.

## Features

- **Services** with a duration, price and buffer time before and after (to set up or
  clean up). Archived services stay on old bookings but can't be booked.
- **Staff** with the services they offer, weekly working hours (split shifts too) and
  time off.
  Staff who have left can be deactivated, and each has a colour on the calendar and a
  private calendar feed to subscribe to on their phone.
- **Free times** worked out from working hours, existing bookings and their buffers,
  time off, minimum notice and how far ahead customers may book, in the business's
  time zone.
  Days the whole business is closed are left out.
- **Public booking page** per business at `/b/<slug>/`: pick a service, a staff member
  (or anyone available), a day and a time, then enter a name, email and phone number.
- **Booking link**: customers see, cancel or move their booking from a signed link.
  Businesses can ask customers to confirm by email first (the slot is held for 30
  minutes), and stop online changes close to the appointment.
- **Emails** to the customer and the business for new, cancelled and moved bookings,
  with a calendar file attached.
  Reminders go out a day before, and staff get a copy of their own bookings.
- **Calendar** for the team with day and week views, a details panel for each booking
  and buttons to mark it completed, a no-show or cancelled.
- **Dashboard** with today's appointments, what's coming up and the revenue for the
  week and month.
  Also cancellation and no-show rates, the most booked services and bookings per week.
- **Bookings and customers**: a searchable, filterable list of bookings with CSV
  export, bookings added by hand for phone and walk-in customers, and a customer list
  with visit counts and history.

## Stack

| Part      | Tech                                                                   |
| --------- | ---------------------------------------------------------------------- |
| App       | Python 3.12, Django 5.2, server-rendered templates, htmx 2             |
| Database  | PostgreSQL 17                                                          |
| Serving   | gunicorn, whitenoise for static files                                  |
| Email     | SMTP; mailpit catches everything locally                               |
| Tests     | pytest, pytest-django                                                  |
| Lint      | ruff (lint and format)                                                 |
| Ops       | Docker Compose, multi-stage Dockerfile, GitHub Actions                 |

## Architecture

```
browser ──> app (gunicorn :8000) ──> db (Postgres :5432)
             Django + whitenoise   ──> mailpit (SMTP :1025, web UI :8025)
```

One Django project (`config`) with an app per area:

| App             | What's in it                                                          |
| --------------- | --------------------------------------------------------------------- |
| `accounts`      | User model (email login), sign up, password reset, account deletion   |
| `businesses`    | Business, services, staff, working hours, time off, closed days       |
| `scheduling`    | Free-slot calculation; no models                                      |
| `appointments`  | Bookings, the public booking pages, signed links, calendar files      |
| `notifications` | Emails and reminders                                                  |
| `dashboard`     | Calendar, dashboard, bookings and customer lists, staff feeds         |
| `core`          | Health check, middleware, demo seed, shared template tags             |

The rules that matter most are kept apart from the views so they're easy to test:

| Module                        | What it does                                                   |
| ----------------------------- | -------------------------------------------------------------- |
| `scheduling/slots.py`         | Pure functions: free start times from shifts and busy periods   |
| `scheduling/availability.py`  | Loads hours, bookings, time off and closed days for `slots`     |
| `appointments/services.py`    | Creating, moving, cancelling and confirming bookings            |
| `appointments/tokens.py`      | Signed booking links                                            |
| `dashboard/calendar.py`       | Day and week grids, with overlapping bookings side by side      |
| `dashboard/stats.py`          | Dashboard numbers in the business's time zone                   |

Business users sign in with Django's session auth. Customers never log in: their
booking link carries a signed token (Django's `signing`, salted per purpose), so it
can't be guessed or changed to point at another booking.

## How free times are worked out

For a service on a given day, each staff member who offers it gets a list of candidate
start times: every *slot interval* (15 minutes by default) from the start of each of
their shifts, as long as the appointment ends by the end of the shift. A candidate is
kept when:

1. it starts after now plus the business's minimum notice, and the day is within the
   booking window (`max_advance_days`);
2. the appointment *and its buffers* don't overlap another booking (with that
   booking's buffers) or time off. Buffers may run outside working hours, so a 10
   minute clean-up after the last appointment of the day is fine;
3. the business isn't closed that day.

Touching periods don't overlap: one appointment can end at 10:00 and the next start at
10:00. Shifts are local wall-clock times, so 09:00 stays 09:00 after the clocks change;
all comparisons happen in UTC.

Cancelled and expired bookings don't block anything. A booking waiting for email
confirmation holds its time for 30 minutes. With "anyone available", the booking goes
to the free staff member with the fewest bookings that day. Creating, moving and
confirming a booking lock the staff rows and check again inside the transaction, so
two customers can't take the same time.

## Running with Docker

```bash
cp .env.example .env    # optional, the defaults work
docker compose up --build
```

Then open http://localhost:4406 and log in with the demo account:

- **Email:** `demo@example.com`
- **Password:** `demo-password`

The app container runs the migrations on start and, because `SEED_DEMO=true`, creates
the demo account with a salon, four staff members and about five months of bookings
around today. Its public booking page is at
http://localhost:4406/b/maple-street-salon/. Set `SEED_DEMO=false` for an empty
database.

| Service | Host port | URL                                                    | Notes                       |
| ------- | --------- | ------------------------------------------------------ | --------------------------- |
| app     | 4406      | http://localhost:4406                                  | gunicorn, health at /healthz |
| mailpit | 8026      | http://localhost:8026                                  | every email the app sends   |
| db      | 5446      | `postgresql://bookings:bookings@localhost:5446/bookings` | Postgres 17               |

Ports can be changed with `APP_PORT`, `MAILPIT_UI_PORT` and `DB_PORT` (in `.env` or
inline, e.g. `APP_PORT=8080 docker compose up`). Data lives in the `db-data` volume;
`docker compose down -v` removes it.

Every email the app sends (confirmations, cancellations, password resets) ends up in
mailpit instead of a real inbox: open http://localhost:8026 to read them and click the
booking links. Mailpit's SMTP port is only reachable from the app container.

## Running without Docker

You need Python 3.12 and PostgreSQL. The easiest way to get the database (and mailpit)
is still Docker:

```bash
docker compose up -d db mailpit
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py seed_demo          # optional: the demo account
DEBUG=true python manage.py runserver
```

The app connects to `postgres://bookings:bookings@localhost:5446/bookings` by default;
set `DATABASE_URL` to use another database. Without `EMAIL_HOST`, emails are printed to
the console.
`make db`, `make run`, `make test` and `make lint` wrap the usual commands.

### Scheduled commands

Two management commands should run every few minutes, from cron or a scheduler of your
choice:

```bash
python manage.py send_reminders     # emails customers whose appointment is in the next 24 hours
python manage.py expire_bookings    # releases bookings that weren't confirmed in time
```

Both are safe to run as often as you like. With Docker:
`docker compose exec app python manage.py send_reminders`.

### Configuration

| Variable               | Default                                              | Notes                                   |
| ---------------------- | ---------------------------------------------------- | --------------------------------------- |
| `DATABASE_URL`         | `postgres://bookings:bookings@localhost:5446/bookings` |                                       |
| `SECRET_KEY`           | an insecure development value                        | signs sessions and booking links        |
| `DEBUG`                | `false`                                              |                                         |
| `ALLOWED_HOSTS`        | `localhost,127.0.0.1`                                | comma separated                         |
| `CSRF_TRUSTED_ORIGINS` | empty                                                | e.g. `https://book.example.com`         |
| `SITE_URL`             | `http://localhost:8000`                              | start of links in emails                |
| `EMAIL_HOST`, `EMAIL_PORT` | empty, `25`                                      | console backend without a host          |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | empty            |                                         |
| `DEFAULT_FROM_EMAIL`   | `Bookings <no-reply@bookings.local>`                 |                                         |
| `SEED_DEMO`            | `false` (`true` in docker compose)                   | read by the docker entrypoint           |
| `SECURE_COOKIES`       | `false`                                              | set behind https                        |
| `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` | `false`, `0`                   |                                         |
| `BEHIND_PROXY`         | `false`                                              | trust `X-Forwarded-Proto`               |
| `LOG_LEVEL`, `LOG_FORMAT` | `INFO`, `plain`                                   | `LOG_FORMAT=json` for one JSON object per line |

## Tests

```bash
pytest                    # needs the database from docker compose (port 5446)
ruff check .
ruff format --check .
```

pytest-django creates and drops a `test_bookings` database next to the real one.
CI (`.github/workflows/ci.yml`) runs the linter and the tests against Postgres and builds
the Docker image.

## Deploying

The Docker image is meant to run behind a reverse proxy (Caddy, nginx, a platform's
load balancer) that terminates https. On the app container set:

- `SECRET_KEY` to a long random value, and keep it: changing it breaks every booking
  link already sent to customers.
- `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and `SITE_URL` to the public address.
- `SECURE_COOKIES=true`, `BEHIND_PROXY=true` and, once everything works over https,
  `SECURE_HSTS_SECONDS=31536000`.
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
  `EMAIL_USE_TLS` and `DEFAULT_FROM_EMAIL` for a real mail provider.

Migrations run on every start. Remember the two scheduled commands below.

## Project layout

```
config/          settings, urls, wsgi
accounts/        user model, auth views
businesses/      business, services, staff, hours, time off, closed days
scheduling/      slots.py (pure) and availability.py (database)
appointments/    booking model, public pages, booking links, services, ics
notifications/   emails, reminders
dashboard/       calendar, dashboard, lists, staff feeds
core/            health check, middleware, demo seed, template tags
templates/       all templates, one folder per app; emails/ for email bodies
static/          css, htmx, a little js
docker/          entrypoint
```

## Assumptions and limits

- One business per account, managed by its owner. Staff don't log in; they can follow
  their bookings through the calendar feed and the email copies.
- A booking is with one staff member for one service. Moving a booking keeps the same
  staff member.
- Prices are shown as plain amounts with no currency and there are no online payments.
- Reminders and expiry depend on the two scheduled commands above.

## Roadmap

Ideas for what could come next, with notes on how each would be built, are in
[ROADMAP.md](ROADMAP.md).

## Troubleshooting

- **Port already in use**: another project is using 4406, 5446 or 8026. Pick other
  ports in `.env`, e.g. `APP_PORT=4416`.
- **`connection refused` from pytest or runserver**: the database isn't running; start
  it with `docker compose up -d db`.
- **No demo data**: the seed only runs when the demo account doesn't exist yet. Use
  `docker compose down -v` to start from an empty database.
- **Booking links stopped working**: they are signed with `SECRET_KEY`; links sent
  before it changed can't be verified any more.

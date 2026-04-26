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
- **Free times** worked out from working hours, existing bookings and their buffers,
  time off, minimum notice and how far ahead customers may book, in the business's
  time zone.
- **Public booking page** per business at `/b/<slug>/`: pick a service, a staff member
  (or anyone available), a day and a time, then enter a name, email and phone number.
- **Booking link**: customers see, cancel or move their booking from a signed link.
- **Emails** to the customer and the business for new, cancelled and moved bookings,
  with a calendar file attached.
- **Calendar** for the team with day and week views, a details panel for each booking
  and buttons to mark it completed, a no-show or cancelled.
- **Dashboard** with today's appointments, what's coming up and the revenue for the
  week and month.

## Stack

Python 3.12, Django 5.2, PostgreSQL, server-rendered templates with htmx, gunicorn and
whitenoise. Tests use pytest and pytest-django; ruff for linting.

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

## Tests

```bash
pytest                    # needs the database from docker compose (port 5446)
ruff check .
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

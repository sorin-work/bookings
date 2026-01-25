.PHONY: install db run test lint format migrations seed up down

install:
	pip install -r requirements-dev.txt

db:
	docker compose up -d db mailpit

run:
	DEBUG=true python manage.py runserver

test:
	pytest

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

migrations:
	python manage.py makemigrations

seed:
	python manage.py seed_demo

up:
	docker compose up --build -d

down:
	docker compose down

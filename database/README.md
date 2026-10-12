# Smart Health - Database Infrastructure (Minimal & Refactored)

This directory contains the production-ready PostgreSQL database infrastructure synchronized strictly to support the existing Smart Health backend capabilities.

This database architecture was explicitly refactored to be minimal: it retains only the tables referenced by active logic in the backend, frontend, and offline PHC app, while maintaining strict referential integrity.

## Included Key Capabilities
- **Users**: Admin dashboard authorizations mapping locally.
- **Facilities & Inventory**: Consolidated unified tracking replacing medicine quantity states strictly over to transactional inventory.
- **Attendance**: Two-tier approach maintaining strict granular personnel attendance logs while safely wrapping summary variables specifically demanded by `/facility/attendance` FastApi requirements.
- **Predictive Data Storage**: Includes tables heavily referenced by the backend Prophet implementation including `daily_footfall` and `medicine_consumption`.
- **Offline Sync Logging**: Maintains safe offline-first application updates through strict conflict checks using unique UUID markers.

## Folder Structure

```text
database/
├── docker-compose.yml   - Container configurations (Postgres 16, pgAdmin 4) binding `.env`.
├── .env.example         - Template environment variables config map.
├── db.py                - High-performance psycopg2 database pooling module (Auto-loading `.env`).
├── schema.sql           - The authoritative PostgreSQL DDL definition heavily purged of unused bloat.
├── seed.py              - Python mock dataset generation script building minimal logic states.
└── README.md            - Setup documentation.
```

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- Python 3.10+ (For running `seed.py`)
- Python packages: `psycopg2-binary`, `passlib`, `bcrypt`, `python-dotenv`

## 1. Environment Variables

Begin by copying the example environment configuration into a `.env` file constraint in this directory.

```bash
cp .env.example .env
```
Ensure variables such as `DATABASE_URL` accurately match the backend setup expectations if you plan on bridging them later.

## 2. Running Docker Compose (Database Startup)

Startup PostgreSQL and pgAdmin 4:

```bash
docker-compose up -d
```

> [!NOTE] 
> Because we mounted `schema.sql` into `/docker-entrypoint-initdb.d/init.sql`, **Docker will automatically initialize our entire relational database layout** on the first boot dynamically. If you change `schema.sql`, you may have to rebuild your Docker volume:
> `docker-compose down -v && docker-compose up -d` 

## 3. Populate Database (Seed Script)

Before starting the backend, generate structured data including 10 PHCs initialized with 6 months of daily consumption and footprint data (used directly for ML predictive pipeline analysis).

1. Install Python dependencies:
```bash
pip install psycopg2-binary passlib bcrypt python-dotenv
```

2. Execute generator:
```bash
python seed.py
```

*Expected behavior: The script connects efficiently using connection pooling (via `db.py`), batch-inserts unified entries natively, skipping over deleted unused schema entities efficiently.*

## 4. Backend Connection

This database explicitly utilizes table structures corresponding accurately to FastAPI REST validations inside `/app/models/schemas.py`.

Table attributes mapping examples:
- Backend `phc_id` matches `facilities.phc_id` (String primary key).
- Backend `item_id` matches `medicines.item_id` (Serial integer referencing).
- Backend `doctors_present` matches identically into relational `phc_attendance_summary.doctors_present`.

With these adjustments confirmed via `schema.sql`, the existing backend codebase is completely unimpacted—it requires simply adopting your `.env` connection using `db.get_pool()`.

## Troubleshooting

- **Connection Refused in seed.py**: Wait up to 10 seconds for the database image to fully verify integrity after `docker-compose` begins. Database health status enforces retries, but initializations can run slightly staggered. 
- **Missing Environment**: Make sure you have python-dotenv (`pip install python-dotenv`) to prevent initialization problems when booting db routes organically.

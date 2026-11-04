# Backend Python

Backend inicial del Panel Caballito y Muñequita. Está separado del frontend para conservar intacta la interfaz actual.

## Requisitos

- Python 3.11 o superior.
- PostgreSQL 15 o superior para entornos persistentes.

## Ejecutar localmente

Desde la carpeta `backend`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

La API queda disponible en `http://127.0.0.1:8000`.
Documentación interactiva: `http://127.0.0.1:8000/docs`.

## Comprobaciones

- `GET /`: información del servicio.
- `GET /api/v1/health`: estado del proceso.
- `GET /api/v1/health/ready`: comprueba también la conexión con la base de datos.

## Base de datos y migraciones

Configurar `DATABASE_URL` en el archivo `.env`. El valor de ejemplo usa PostgreSQL local. Ejecutar `alembic upgrade head` para crear el esquema inicial. No subir nunca el archivo `.env` real al repositorio.

## Estado

Esta es la primera base técnica. Todavía no se habilitaron operaciones de negocio ni autenticación; se incorporarán con migraciones, validaciones y permisos antes de exponer la API públicamente.

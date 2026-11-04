# Panel Caballito y Muñequita

Prototipo del sistema de asistentes para una juguetería: la muñequita (clientes) y el caballito (pedidos y stock) son la base de datos en 3D, y seis asistentes giran a su alrededor (Atención, Pedidos, Stock, Local, Seguimiento y Vendedores).

## Cómo verlo

Abrí `index.html` en el navegador. Para publicarlo, activá GitHub Pages en **Settings → Pages → Deploy from a branch → main / (root)**.

## Qué incluye

- Escena 3D interactiva: todo se puede tocar y arrastrar, y los asistentes hacen gestos.
- Tableros de la muñequita y el caballito que se abren con un toque.
- Pendientes, búsqueda y chat para pedirle cosas a los asistentes.
- Vendedores conectados por su app (simulado).
- Pantallita en vivo: stock del día con foto, precio y cantidad, y juguetes a medida con precio calculado desde la base de materiales.
- Envío por WhatsApp con el mensaje ya armado.
- Recorrido guiado ("¿Cómo se usa?") y tres idiomas (español, inglés y portugués).

## Pendiente para producción

- Los datos son de ejemplo y viven en el navegador. Hay que conectarlos a una base de datos real.
- El chat con IA funciona dentro de Claude. Fuera de Claude responde con reglas simples hasta que se agregue un servidor que llame a la API.
- WhatsApp Business API y la app de vendedores todavía no están conectadas.


## Backend Python en desarrollo

La rama `feature/python-backend` incorpora el primer backend con FastAPI y SQLAlchemy, separado de la interfaz visual existente.

### Ejecutar el backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Abrí `http://127.0.0.1:8000/docs` para explorar la API.

### Endpoints iniciales

- `GET /api/v1/health`
- `GET /api/v1/health/ready`
- `GET /api/v1/customers` y `POST /api/v1/customers`
- `GET /api/v1/products` y `POST /api/v1/products`
- `GET /api/v1/tasks` y `POST /api/v1/tasks`

### Importante

Esta rama es una base de desarrollo, no una versión lista para producción. Antes de publicar operaciones reales faltan migraciones de base de datos, autenticación y autorización, integración de la interfaz, pruebas de negocio, auditoría completa y configuración de despliegue. Los datos de demostración del frontend todavía no se migraron.

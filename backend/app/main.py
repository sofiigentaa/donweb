from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.routers import router as business_router
from app.auth_router import router as auth_router

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="API del Panel Caballito y Muñequita.",
)

# Configuración de CORS definitiva y a prueba de balas
"""app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)"""

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS"
    ],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept"
    ],
    max_age=600,
)

# Incluir los endpoints del proyecto (products, orders, activity, assistant, etc.)
app.include_router(business_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)


# Frontend estático: solo se exponen estos archivos (nunca la carpeta completa).
FRONTEND_DIR = Path(__file__).resolve().parents[2]
FRONTEND_PAGES = {"index.html", "admin.html", "seller.html", "store.html"}


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/{page}", include_in_schema=False)
def frontend_page(page: str) -> FileResponse:
    if page not in FRONTEND_PAGES:
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(FRONTEND_DIR / page)


@app.get(f"{settings.api_prefix}/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get(f"{settings.api_prefix}/health/ready", tags=["system"])
def health_ready(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Base de datos no disponible.") from exc

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer, Seller
from app.schemas import LoginRequest, TokenResponse, CustomerRegister, CustomerRegisterResponse, SellerCreate
from app.security import (
    verify_password, get_password_hash, create_access_token,
    generate_totp_secret, get_totp_uri, generate_qr_base64, verify_totp
)

router = APIRouter()

@router.post("/auth/register", response_model=CustomerRegisterResponse, tags=["auth"])
def register_customer(payload: CustomerRegister, db: Session = Depends(get_db)):
    if db.scalar(select(Customer).where(Customer.email == payload.email)):
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
    secret = generate_totp_secret()
    customer = Customer(
        name=payload.name, 
        email=payload.email, 
        password_hash=get_password_hash(payload.password),
        totp_secret=secret
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    
    token = create_access_token({"sub": str(customer.id), "role": "customer", "name": customer.name})
    uri = get_totp_uri(secret, customer.email)
    qr_base64 = generate_qr_base64(uri)
    
    return {
        "access_token": token, "token_type": "bearer", "role": "customer", 
        "name": customer.name, "qr_base64": qr_base64
    }

@router.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(Customer).where(Customer.email == payload.email))
    role = "customer"
    if not user:
        user = db.scalar(select(Seller).where(Seller.email == payload.email))
        role = "seller"
    
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
        
    if role == "seller" and user.totp_secret:
        if not payload.totp_code:
            raise HTTPException(status_code=401, detail="2FA_REQUIRED")
        if not verify_totp(user.totp_secret, payload.totp_code):
            raise HTTPException(status_code=401, detail="Código 2FA inválido")
            
    token = create_access_token({"sub": str(user.id), "role": role, "name": user.name})
    return {"access_token": token, "token_type": "bearer", "role": role, "name": user.name}

@router.post("/admin/sellers", tags=["auth"])
def create_seller(payload: SellerCreate, db: Session = Depends(get_db)):
    if db.scalar(select(Seller).where(Seller.email == payload.email)):
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
    secret = generate_totp_secret()
    seller = Seller(
        name=payload.name, email=payload.email, phone=payload.phone,
        password_hash=get_password_hash(payload.password), totp_secret=secret
    )
    db.add(seller)
    db.commit()
    db.refresh(seller)
    
    uri = get_totp_uri(secret, seller.email)
    qr_base64 = generate_qr_base64(uri)
    
    return {
        "id": seller.id, "name": seller.name, "email": seller.email,
        "qr_base64": qr_base64, "message": "Vendedor creado. Escaneá el QR con Google Authenticator."
    }

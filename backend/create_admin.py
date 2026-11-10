#!/usr/bin/env python3
"""Crea (o promueve) un administrador con 2FA.

Uso, desde la carpeta backend:
    .venv/bin/python create_admin.py "Sofi" sofi@jugueteria.com

Para la base de Render, usá la "External Database URL":
    DATABASE_URL='postgresql://...' .venv/bin/python create_admin.py "Sofi" sofi@jugueteria.com

Pide la contraseña sin mostrarla y muestra el QR para Google Authenticator.
Con --reset-2fa genera un QR nuevo para un admin existente.
"""
from __future__ import annotations

import argparse
import getpass
import sys

import pyotp
import qrcode
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Seller
from app.security import generate_totp_secret, get_password_hash, get_totp_uri


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name")
    parser.add_argument("email")
    parser.add_argument("--reset-2fa", action="store_true", help="genera un QR nuevo")
    args = parser.parse_args()

    password = getpass.getpass("Contraseña del admin: ")
    if len(password) < 8:
        print("La contraseña tiene que tener al menos 8 caracteres.")
        return 1
    if password != getpass.getpass("Repetila: "):
        print("Las contraseñas no coinciden.")
        return 1

    with SessionLocal() as db:
        admin = db.scalar(select(Seller).where(Seller.email == args.email))
        if admin is None:
            admin = Seller(name=args.name, email=args.email)
            db.add(admin)
        admin.name = args.name
        admin.password_hash = get_password_hash(password)
        admin.is_admin = True
        admin.active = True
        if args.reset_2fa or not admin.totp_secret:
            admin.totp_secret = generate_totp_secret()
        db.commit()
        secret = admin.totp_secret

    uri = get_totp_uri(secret, args.email)
    print(f"\nAdmin listo: {args.name} <{args.email}>")
    print("Escaneá este QR con Google Authenticator:\n")
    qr = qrcode.QRCode(border=1)
    qr.add_data(uri)
    qr.print_ascii(invert=True)
    print(f"Si no podés escanearlo, cargá esta clave a mano: {secret}")
    print(f"Comprobación: el código actual es {pyotp.TOTP(secret).now()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

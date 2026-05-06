"""
RouteZone -- Module securite (API key + JWT)
Partage entre tous les routers.
"""

import os
import hmac
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import text

from db import engine

# ── Configuration ────────────────────────────────────────────────
API_KEY = os.getenv("API_KEY", "routezone-secret-2024")
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "routezone-jwt-secret-change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

# ── API Key ──────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verifier_api_key(x_api_key: str = Depends(api_key_header)):
    if x_api_key is None or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=403, detail="Cle API invalide ou manquante")

# ── Hashage bcrypt ───────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# ── JWT ──────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

def create_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "email": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

# ── Dependencies FastAPI ─────────────────────────────────────────
def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    if token is None:
        raise HTTPException(status_code=401, detail="Token manquant", headers={"WWW-Authenticate": "Bearer"})
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token invalide ou expire", headers={"WWW-Authenticate": "Bearer"})
    return {"id": int(payload["sub"]), "email": payload["email"]}

def get_optional_user(token: str = Depends(oauth2_scheme)) -> Optional[dict]:
    if token is None:
        return None
    payload = decode_token(token)
    if payload is None:
        return None
    return {"id": int(payload["sub"]), "email": payload["email"]}

def verifier_api_key_ou_jwt(
    x_api_key: str = Depends(api_key_header),
    token: str = Depends(oauth2_scheme),
):
    """Accepte SOIT une API key valide SOIT un JWT valide."""
    # API key OK ?
    if x_api_key is not None and hmac.compare_digest(x_api_key, API_KEY):
        return
    # JWT OK ?
    if token is not None and decode_token(token) is not None:
        return
    raise HTTPException(status_code=403, detail="Authentification requise (API key ou JWT)")

# ── Operations BDD users ─────────────────────────────────────────
def create_user(email: str, password: str, nom: str = None) -> dict:
    hashed = hash_password(password)
    with engine.begin() as conn:
        existing = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Un compte existe deja avec cet email")
        row = conn.execute(
            text("INSERT INTO users (email, password_hash, nom) VALUES (:e, :p, :n) RETURNING id, email, nom"),
            {"e": email, "p": hashed, "n": nom}
        ).fetchone()
        return {"id": row[0], "email": row[1], "nom": row[2]}

def authenticate_user(email: str, password: str) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id, email, password_hash, nom FROM users WHERE email = :e"), {"e": email}).fetchone()
    if row is None or not verify_password(password, row[2]):
        return None
    return {"id": row[0], "email": row[1], "nom": row[3]}

# ── Schemas ──────────────────────────────────────────────────────
class UserRegister(BaseModel):
    email: str
    password: str
    nom: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str

"""
RouteZone -- Routes authentification (/auth)
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm

from security import (
    UserRegister, UserLogin, TokenResponse,
    create_user, authenticate_user, create_token, get_current_user,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse)
def register(data: UserRegister):
    """Inscription. Retourne un token JWT."""
    user = create_user(data.email, data.password, data.nom)
    token = create_token(user["id"], user["email"])
    return TokenResponse(access_token=token, user_id=user["id"], email=user["email"])


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin):
    """Connexion (format JSON). Retourne un token JWT."""
    user = authenticate_user(data.email, data.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    token = create_token(user["id"], user["email"])
    return TokenResponse(access_token=token, user_id=user["id"], email=user["email"])


@router.post("/token", response_model=TokenResponse)
def token_oauth2(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Connexion (format OAuth2 form-data) pour compatibilite Swagger UI.
    Le champ 'username' de OAuth2 correspond a l'email.
    """
    user = authenticate_user(form_data.username, form_data.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    token = create_token(user["id"], user["email"])
    return TokenResponse(access_token=token, user_id=user["id"], email=user["email"])


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Infos de l'utilisateur connecte."""
    return {"user_id": user["id"], "email": user["email"]}
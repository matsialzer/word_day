import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from worddays.web import auth
from worddays.web.schemas import LoginIn

router = APIRouter()


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response) -> dict:
    app = request.app
    ip = request.client.host if request.client else "unknown"
    if app.state.login_guard.is_blocked(ip):
        raise HTTPException(429, "Слишком много попыток. Попробуйте позже.")

    if not auth.check_password(body.password, app.state.settings.web_admin_password):
        app.state.login_guard.record_fail(ip)
        await asyncio.sleep(0.5)  # замедляем перебор
        raise HTTPException(401, "Неверный пароль")

    app.state.login_guard.reset(ip)
    fingerprint = auth.password_fingerprint(app.state.settings.web_admin_password)
    response.set_cookie(
        auth.COOKIE,
        app.state.serializer.dumps({"fp": fingerprint}),
        max_age=auth.SESSION_TTL,
        httponly=True,  # недоступна скриптам страницы
        samesite="strict",
        secure=app.state.settings.web_cookie_secure,
    )
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(auth.COOKIE)
    return {"ok": True}


@router.get("/me", dependencies=[Depends(auth.require_admin)])
async def me() -> dict:
    return {"admin": True}

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

from utils import db, templates, hash_pass, encode_jwt

login_router = APIRouter(prefix="/masuk")


@login_router.get("")
async def proctor_login_page(request: Request):
    return templates.TemplateResponse(
        "login.html", {"request": request, "user_type": "proktor", "status": True}
    )


@login_router.post("")
async def proctor_login(
    request: Request, username: str = Form(...), password: str = Form(...)
):
    hashed = hash_pass(password)
    proctor = await db.pool.fetchrow(
        "SELECT * FROM proctors WHERE username = $1 AND pass_hash = $2",
        username,
        hashed,
    )

    if not proctor:
        return templates.TemplateResponse(
            "login.html", {"request": request, "user_type": "proktor", "status": False}
        )

    payload = {
        "type": "proctor",
        "id": proctor["id"],
        "username": proctor["username"],
        "name": proctor["name"],
    }
    encoded_jwt = encode_jwt(payload)

    response = RedirectResponse("/proktor", 303)
    response.set_cookie("monde", encoded_jwt)
    return response


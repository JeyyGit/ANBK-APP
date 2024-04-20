from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

from utils import db, templates, encode_jwt

login_router = APIRouter(prefix="/masuk")


@login_router.get("")
async def student_login_page(request: Request):
    return templates.TemplateResponse(
        "login.html", {"request": request, "user_type": "siswa", "status": True}
    )


@login_router.post("")
async def student_login(
    request: Request, username: str = Form(...), password: str = Form(...)
):
    # hashed = hash_pass(password)
    student = await db.pool.fetchrow(
        "SELECT * FROM students WHERE username = $1 AND pass_hash = $2",
        username,
        password,
    )

    if not student:
        return templates.TemplateResponse(
            "login.html", {"request": request, "user_type": "siswa", "status": False}
        )

    payload = {
        "type": "student",
        "id": student["id"],
        "username": student["username"],
        "name": student["name"],
    }
    encoded_jwt = encode_jwt(payload)

    response = RedirectResponse("/siswa", 303)
    response.set_cookie("monde", encoded_jwt)
    return response

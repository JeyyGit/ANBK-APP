from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

import jwt
import datetime as dt
from typing import List, Literal

from utils import SECRET, db, templates, Database, hash_pass, encode_jwt, check_jwt
from routes.siswa import student_router
from routes.proktor import proctor_router

app = FastAPI()

app.mount("/assets", StaticFiles(directory="./assets"), name="assets")
app.add_middleware(SessionMiddleware, secret_key=SECRET)


@app.on_event("startup")
async def startup():
    await db.create_pool()


@app.get("/")
async def root_page(request: Request):
    jwt_str = request.cookies.get("monde")
    if jwt_str:
        try:
            payload = jwt.decode(jwt_str, SECRET, ["HS256"])
        except Exception as e:
            request.cookies.pop("monde")
            logged_in = False
        else:
            logged_in = True
    else:
        logged_in = False

    if logged_in:
        if payload["type"] == "student":
            return RedirectResponse("/siswa")
        elif payload["type"] == "proctor":
            return RedirectResponse("/proktor")

    return templates.TemplateResponse(
        "index.html", {"request": request, "logged_in": logged_in}
    )


app.include_router(student_router)
app.include_router(proctor_router)

@app.get("/keluar")
async def logout():
    response = RedirectResponse("/")
    response.delete_cookie("monde")
    return response

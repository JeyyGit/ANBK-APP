from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
import datetime as dt
import pytz

from utils import db, templates, check_jwt
from routes.proktor_masuk import login_router
from routes.proktor_modul import module_router
from routes.proktor_modul_paket import pack_router
from routes.proktor_modul_paket_soal import question_router
from routes.proktor_siswa import student_router
from routes.proktor_ujian import exam_router
from routes.proktor_percobaan import attempt_router
import humanize

proctor_router = APIRouter(prefix="/proktor")


@proctor_router.get("")
async def proctor_page(request: Request):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    logs = await db.pool.fetch("SELECT * FROM logs ORDER BY log_dt DESC LIMIT 6")
    return templates.TemplateResponse(
        "proktor.html",
        {
            "request": request,
            "proktor": payload,
            "logs": logs,
            "humanize": humanize,
            "now": dt.datetime.now(pytz.timezone("Asia/Jakarta")).replace(tzinfo=None),
        },
    )


proctor_router.include_router(login_router)
proctor_router.include_router(module_router)
proctor_router.include_router(pack_router)
proctor_router.include_router(question_router)
proctor_router.include_router(student_router)
proctor_router.include_router(exam_router)
proctor_router.include_router(attempt_router)

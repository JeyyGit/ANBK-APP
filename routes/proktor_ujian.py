from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

import datetime as dt

from utils import add_log, db, templates, check_jwt

exam_router = APIRouter(prefix="/ujian")


@exam_router.get("")
async def exam_page(request: Request):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    exams = await db.pool.fetch(
        """
        SELECT
            e.id AS exam_id,
            e.pack_id,
            e.archived,
            e.max_attempts,
            e.show_score,
            p.name AS pack_name,
            m.id AS module_id,
            m.name AS module_name,
            e.proctor_id,
            e.name AS exam_name,
            e.start_dt,
            e.end_dt,
            e.time_limit
        FROM
            exams e
        JOIN
            packs p ON e.pack_id = p.id
        JOIN
            modules m ON p.module_id = m.id
        ORDER BY
            e.id
    """
    )

    modules = await db.pool.fetch("SELECT * FROM modules ORDER BY id")
    packs = await db.pool.fetch(
        """
        SELECT packs.id, packs.name, packs.module_id, COUNT(questions) AS question_count
        FROM packs
        LEFT JOIN questions ON packs.id = questions.pack_id
        GROUP BY packs.id, packs.name;                            
    """
    )
    packs = [dict(pack) for pack in packs]

    return templates.TemplateResponse(
        "proktor_ujian.html",
        {
            "request": request,
            "proktor": payload,
            "exams": exams,
            "modules": modules,
            "packs": packs,
        },
    )


@exam_router.post("/tambah")
async def exam_add(
    request: Request,
    exam_name: str = Form(...),
    pack_id: int = Form(...),
    start_dt: dt.datetime = Form(...),
    end_dt: dt.datetime = Form(None),
    max_attempts: int = Form(...),
    show_score: bool = Form(False),
    day: int = Form(None),
    hour: int = Form(None),
    minute: int = Form(None),
    second: int = Form(None),
):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    if not (day or hour or minute or second):
        time_limit = None
    else:
        time_limit = dt.timedelta(days=day, hours=hour, minutes=minute, seconds=second)

    await db.pool.execute(
        "INSERT INTO exams (pack_id, proctor_id, name, start_dt, end_dt, time_limit, max_attempts, show_score) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
        pack_id,
        payload["id"],
        exam_name,
        start_dt,
        end_dt,
        time_limit,
        max_attempts,
        show_score
    )

    await add_log(payload, f"Menambahkan ujian baru `{exam_name}`")
    return RedirectResponse("/proktor/ujian", 303)


@exam_router.post("/{exam_id}/edit")
async def exam_edit(
    request: Request,
    exam_id: int,
    exam_name: str = Form(...),
    pack_id: int = Form(...),
    start_dt: dt.datetime = Form(...),
    end_dt: dt.datetime = Form(None),
    max_attempts: int = Form(...),
    show_score: bool = Form(False),
    day: int = Form(None),
    hour: int = Form(None),
    minute: int = Form(None),
    second: int = Form(None),
):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    exam = await db.pool.fetchrow("SELECT * FROM exams WHERE id = $1", exam_id)
    if not exam:
        return RedirectResponse("/", 303)

    if not (day or hour or minute or second):
        time_limit = None
    else:
        time_limit = dt.timedelta(days=day, hours=hour, minutes=minute, seconds=second)

    await db.pool.execute(
        "UPDATE exams SET name = $1, pack_id = $2, start_dt = $3, end_dt = $4, time_limit = $5, max_attempts = $6, show_score = $7 WHERE id = $8",
        exam_name,
        pack_id,
        start_dt,
        end_dt,
        time_limit,
        max_attempts,
        show_score,
        exam_id,
    )

    await add_log(payload, f"Menyunting ujian `{exam['name']}`")
    return RedirectResponse("/proktor/ujian", 303)

@exam_router.get("/{exam_id}/arsip")
async def exam_archive(request: Request, exam_id: int):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    archived = await db.pool.fetchval("SELECT archived FROM exams WHERE id = $1", exam_id)

    if archived:
        await db.pool.execute("UPDATE exams SET archived = false WHERE id = $1", exam_id)
    else:
        await db.pool.execute("UPDATE exams SET archived = true WHERE id = $1", exam_id)

    return RedirectResponse("/proktor/ujian")

@exam_router.get("/{exam_id}/hapus")
async def exam_delete(request: Request, exam_id: int):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    exam = await db.pool.fetchrow("SELECT * FROM exams WHERE id = $1", exam_id)
    if not exam:
        return RedirectResponse("/", 303)

    await db.pool.execute("DELETE FROM exams WHERE id = $1", exam_id)

    await add_log(payload, f"Menghapus ujian `{exam['name']}`")
    return RedirectResponse("/proktor/ujian")

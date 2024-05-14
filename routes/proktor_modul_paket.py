from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

from typing import List

from utils import add_log, db, templates, check_jwt

pack_router = APIRouter(prefix="")


@pack_router.get("/modul/{module_id}/paket/{pack_id}")
async def each_pack_page(request: Request, module_id: int, pack_id: int):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    module = await db.pool.fetchrow(
        "SELECT * FROM modules WHERE id = $1", module_id
    )
    pack = await db.pool.fetchrow(
        "SELECT * FROM packs WHERE id = $1", pack_id
    )
    questions = await db.pool.fetch(
        'SELECT * FROM questions WHERE pack_id = $1 ORDER BY "order"', pack_id
    )
    answers = await db.pool.fetch("SELECT * FROM answers")

    return templates.TemplateResponse(
        "pack_each.html.j2",
        {
            "request": request,
            "proktor": payload,
            "module": module,
            "pack": pack,
            "questions": questions,
            "answers": answers,
        },
    )


@pack_router.post("/modul/{module_id}/paket/{pack_id}/edit")
async def pack_edit(
    request: Request, module_id: int, pack_id: int, nama_paket: str = Form(...)
):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    pack = await db.pool.fetchrow("SELECT * FROM packs WHERE id = $1", pack_id)
    if not pack:
        return RedirectResponse("/", 303)

    await db.pool.execute(
        "UPDATE packs SET name = $1 WHERE id = $2", nama_paket, pack_id
    )

    await add_log(payload, f"Menyunting paket `{nama_paket or pack['name']}`")
    return RedirectResponse(f"/proktor/modul/{module_id}/paket/{pack_id}", 303)


@pack_router.get("/modul/{module_id}/paket/{pack_id}/hapus")
async def pack_delete(request: Request, module_id: int, pack_id: int):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    pack = await db.pool.fetchrow("SELECT * FROM packs WHERE id = $1", pack_id)
    if not pack:
        return RedirectResponse("/", 303)
    
    await db.pool.execute("DELETE FROM packs WHERE id = $1", pack_id)

    await add_log(payload, f"Menghapus paket `{pack['name']}`")
    return RedirectResponse(f"/proktor/modul/{module_id}")


@pack_router.post("/modul/{module_id}/paket/{pack_id}/tambah_soal")
async def add_question(
    request: Request,
    module_id: int,
    pack_id: int,
    pertanyaan: str = Form(...),
    pertanyaan_html: str = Form(...),
    jawaban: List[str] = Form(...),
    benar: List[bool] = Form(...),
):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    rights = []
    for x in benar:
        if x:
            rights.pop()
        rights.append(x)

    question_id = await db.pool.fetchval(
        "INSERT INTO questions (pack_id, question_text, question_html) VALUES ($1, $2, $3) RETURNING id",
        pack_id,
        pertanyaan,
        pertanyaan_html,
    )

    await db.pool.executemany(
        "INSERT INTO answers (question_id, answer_text, is_correct) VALUES ($1, $2, $3)",
        zip([int(question_id)] * len(jawaban), jawaban, rights),
    )
    await db.pool.execute(
        """
        UPDATE questions
        SET "order" = subquery.row_number
        FROM (
            SELECT id, row_number() OVER (PARTITION BY pack_id ORDER BY id) AS row_number
            FROM questions
        ) AS subquery
        WHERE questions.id = subquery.id
    """
    )

    await add_log(payload, "Menambahkan pertanyaan baru")
    return RedirectResponse(f"/proktor/modul/{module_id}/paket/{pack_id}", 303)

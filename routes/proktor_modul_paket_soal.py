from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

from typing import Literal, List

from utils import db, templates, check_jwt, add_log

question_router = APIRouter(prefix="")


@question_router.post("/modul/{module_id}/paket/{pack_id}/soal/{question_id}/edit")
async def edit_question(
    request: Request,
    module_id: int,
    pack_id: int,
    question_id: int,
    pertanyaan: str = Form(...),
    pertanyaan_html: str = Form(...),
    jawaban: List[str] = Form(...),
    benar: List[bool] = Form(...),
):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    await db.pool.execute(
        "UPDATE questions SET question_text = $1, question_html = $2 WHERE id = $3",
        pertanyaan,
        pertanyaan_html,
        question_id,
    )
    await db.pool.execute("DELETE FROM answers WHERE question_id = $1", question_id)

    rights = []
    for x in benar:
        if x:
            rights.pop()
        rights.append(x)
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

    await add_log(payload, f"Menyunting pertanyaan `id: {question_id}`")
    return RedirectResponse(f"/proktor/modul/{module_id}/paket/{pack_id}", 303)


@question_router.get("/modul/{module_id}/paket/{pack_id}/soal/{soal_id}")
async def swap_question(
    request: Request,
    module_id: int,
    pack_id: int,
    soal_id: int,
    direction: Literal["u", "d", "mu", "md"],
):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    current_order = await db.pool.fetchval(
        'SELECT "order" FROM questions WHERE id = $1', soal_id
    )

    if direction == "u":
        other_order = current_order - 1
    elif direction == "mu":
        other_order = 1
    elif direction == "d":
        other_order = current_order + 1
    elif direction == "md":
        other_order = await db.pool.fetchval(
            'SELECT MAX("order") as "max" FROM questions WHERE pack_id = 6'
        )

    other_id = await db.pool.fetchval(
        'SELECT id FROM questions WHERE pack_id = $1 AND "order" = $2',
        pack_id,
        other_order,
    )

    await db.pool.execute(
        'UPDATE questions SET "order" = $1 WHERE id = $2', other_order, soal_id
    )
    await db.pool.execute(
        'UPDATE questions SET "order" = $1 WHERE id = $2', current_order, other_id
    )

    return RedirectResponse(f"/proktor/modul/{module_id}/paket/{pack_id}")


@question_router.get("/modul/{module_id}/paket/{pack_id}/soal/{soal_id}/hapus")
async def delete_question(request: Request, module_id: int, pack_id: int, soal_id: int):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    await db.pool.execute("DELETE FROM questions WHERE id = $1", soal_id)
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

    await add_log(payload, f"Menghapus pertanyaan `id: {soal_id}`")
    return RedirectResponse(f"/proktor/modul/{module_id}/paket/{pack_id}")


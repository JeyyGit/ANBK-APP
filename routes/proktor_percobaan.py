from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from routes.siswa import get_attempt_scoring

from utils import check_jwt, db, templates

attempt_router = APIRouter(prefix="/percobaan")


@attempt_router.get("/")
async def attempt_page(request: Request):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    exams = await db.pool.fetch(
        "SELECT e.id, e.name, e.archived, COUNT(a.id) AS attempts_count FROM exams e LEFT JOIN attempts a ON a.exam_id = e.id GROUP BY e.id ORDER BY id"
    )

    return templates.TemplateResponse(
        "proktor_percobaan.html",
        {"request": request, "proktor": payload, "exams": exams},
    )


@attempt_router.get("/{exam_id}")
async def each_attempt_page(request: Request, exam_id: int):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    exam = await db.pool.fetchrow("SELECT * FROM exams WHERE id = $1", exam_id)
    attempts = await db.pool.fetch(
        """
        SELECT 
            a.id,
            a.student_id,
            a.start_dt,
            a.end_dt,
            a.current_question,
            s.name AS student_name,
            e.max_attempts,
            e.id AS exam_id,
            e.name AS exam_name,
            e.pack_id,
            e.proctor_id,
            e.start_dt AS exam_start_dt,
            e.end_dt AS exam_end_dt,
            e.time_limit,
            p.name AS pack_name
        FROM attempts a
        LEFT JOIN exams e ON
            a.exam_id = e.id
        LEFT JOIN students s ON
            a.student_id = s.id
        LEFT JOIN packs p ON
            e.pack_id = p.id
        WHERE e.id = $1
    """,
        exam_id,
    )
    packs = await db.pool.fetch(
        """
            SELECT packs.id, packs.name, packs.module_id, COUNT(questions) AS question_count
            FROM packs
            LEFT JOIN questions ON packs.id = questions.pack_id
            GROUP BY packs.id, packs.name;                            
        """
    )

    scores = {}
    for a in attempts:
        for p in packs:
            if a["pack_id"] == p["id"]:
                scores[a["id"]] = await get_attempt_scoring(
                    a["id"], p["question_count"]
                )

    return templates.TemplateResponse(
        "proktor_percobaan_each.html",
        {"request": request, "proktor": payload, "exam": exam, "attempts": attempts, "scores": scores},
    )

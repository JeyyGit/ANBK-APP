from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

from utils import db, templates, check_jwt, worker
from routes.siswa_masuk import login_router

from typing import List
import datetime as dt
import asyncio

student_router = APIRouter(prefix="/siswa")


@student_router.on_event("startup")
async def startup_event():
    asyncio.create_task(worker())


async def get_attempt(student_id):
    return await db.pool.fetchrow(
        """
        SELECT 
            a.id,
            a.student_id,
            a.start_dt,
            a.end_dt,
            a.current_question,
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
        LEFT JOIN packs p ON
            e.pack_id = p.id
        WHERE a.student_id = $1 AND a.end_dt IS NULL
    """,
        student_id,
    )


async def get_all_user_attempt(student_id):
    return await db.pool.fetch(
        """
        SELECT 
            a.id,
            a.student_id,
            a.start_dt,
            a.end_dt,
            a.current_question,
            e.id AS exam_id,
            e.name AS exam_name,
            e.pack_id,
            e.proctor_id,
            e.start_dt AS exam_start_dt,
            e.end_dt AS exam_end_dt,
            e.time_limit,
            e.show_score,
            p.name AS pack_name,
            m.name AS module_name
        FROM attempts a
        LEFT JOIN exams e ON
            a.exam_id = e.id
        LEFT JOIN packs p ON
            e.pack_id = p.id
        LEFT JOIN modules m ON
            p.module_id = m.id
        WHERE a.student_id = $1
        ORDER BY a.start_dt
    """,
        student_id,
    )


async def get_temp_ans(attempt_id):
    temp_ans = await db.pool.fetch(
        "SELECT * FROM temp_answers WHERE attempt_id = $1", attempt_id
    )
    return {tmp["question_id"]: tmp["chosen_answers"] for tmp in temp_ans}


async def get_attempt_scoring(attempt_id, total_questions):
    rows = await db.pool.fetch(
        """
        SELECT
            ta.question_id,
            COUNT(*) FILTER (WHERE a.is_correct AND a.id = ANY(ta.chosen_answers)) AS chosen_correct_count,
            COUNT(*) FILTER (WHERE a.is_correct) AS total_correct_count,
            COUNT(*) FILTER (WHERE NOT a.is_correct AND a.id = ANY(ta.chosen_answers)) AS chosen_incorrect_count
        FROM
            temp_answers ta
            INNER JOIN answers a ON ta.question_id = a.question_id
        WHERE
            ta.attempt_id = $1
        GROUP BY
            ta.question_id
    """,
        attempt_id,
    )

    correct_questions = 0
    for row in rows:
        chosen_correct_count = row["chosen_correct_count"]
        total_correct_count = row["total_correct_count"]
        chosen_incorrect_count = row["chosen_incorrect_count"]
        if total_correct_count == 1:
            if chosen_correct_count == 1 and chosen_incorrect_count == 0:
                correct_questions += 1
        else:
            if (
                chosen_correct_count == total_correct_count
                and chosen_incorrect_count == 0
            ):
                correct_questions += 1

    score_percentage = (
        (correct_questions / total_questions) * 100 if total_questions > 0 else 0
    )

    return {
        "corrects": correct_questions,
        "questions": total_questions,
        "score": score_percentage,
    }


@student_router.get("/c")
async def c(request: Request):
    request.session.clear()
    await db.pool.execute("DELETE FROM attempts")
    return RedirectResponse("/")


@student_router.get("")
async def siswa_page(request: Request):
    logged_in, payload = check_jwt(request, "student")

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
        ORDER BY e.id
    """
    )
    attempt = await get_attempt(payload["id"])
    user_attempts = await db.pool.fetch(
        "SELECT COUNT(*), exam_id FROM attempts WHERE student_id = $1 GROUP BY exam_id;",
        payload["id"],
    )
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
        "siswa.html",
        {
            "request": request,
            "siswa": payload,
            "exams": exams,
            "packs": packs,
            "attempt": attempt,
            "user_attempts": user_attempts,
        },
    )


@student_router.get("/masuk_ujian/{exam_id}")
async def enter_exam(request: Request, exam_id: int):
    logged_in, payload = check_jwt(request, "student")

    if not logged_in:
        return RedirectResponse("/")

    # start
    exams = await db.pool.fetch("SELECT * FROM exams ORDER BY start_dt")
    exam = await db.pool.fetchrow(
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
        WHERE
            e.id = $1
    """,
        exam_id,
    )
    if not exam:
        return RedirectResponse("/")

    attempt = await get_attempt(payload["id"])
    attempts = await get_all_user_attempt(payload["id"])
    user_attempts = await db.pool.fetchval(
        "SELECT COUNT(*) FROM attempts WHERE exam_id = $1 AND student_id = $2",
        exam_id,
        payload["id"],
    )

    pack = await db.pool.fetchrow(
        """
        SELECT packs.id, packs.name, packs.module_id, COUNT(questions) AS question_count
        FROM packs
        LEFT JOIN questions ON packs.id = questions.pack_id
        WHERE packs.id = $1
        GROUP BY packs.id, packs.name, packs.module_id;                         
    """,
        exam["pack_id"],
    )

    scores = {
        a["id"]: await get_attempt_scoring(a["id"], pack["question_count"])
        for a in attempts
    }

    return templates.TemplateResponse(
        "siswa_masuk_ujian.html",
        {
            "request": request,
            "siswa": payload,
            "exams": exams,
            "exam": exam,
            "pack": pack,
            "attempt": attempt,
            "attempts": attempts,
            "user_attempts": user_attempts,
            "scores": scores,
        },
    )


@student_router.get("/mulai_ujian/{exam_id}")
async def start_exam(request: Request, exam_id: int):
    logged_in, payload = check_jwt(request, "student")

    if not logged_in:
        return RedirectResponse("/")

    # start
    attempt = await db.pool.fetchrow(
        "SELECT * FROM attempts WHERE student_id = $1 AND end_dt IS NULL", payload["id"]
    )
    if attempt:
        return RedirectResponse("/siswa/ujian")

    exam = await db.pool.fetchrow(
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
        WHERE
            e.id = $1
    """,
        exam_id,
    )
    if not exam:
        return RedirectResponse("/")

    if exam["start_dt"] > exam["start_dt"].now():
        return RedirectResponse("/")

    if exam["end_dt"] and exam["end_dt"] < exam["end_dt"].now():
        return RedirectResponse("/")

    user_attempts = await db.pool.fetchval(
        "SELECT COUNT(*) FROM attempts WHERE exam_id = $1 AND student_id = $2",
        exam_id,
        payload["id"],
    )
    if exam["max_attempts"] > 0 and user_attempts >= exam["max_attempts"]:
        return RedirectResponse("/")

    start_dt = dt.datetime.now()
    await db.pool.execute(
        "INSERT INTO attempts (exam_id, student_id, start_dt, current_question) VALUES ($1, $2, $3, 1)",
        exam_id,
        payload["id"],
        start_dt,
    )

    return RedirectResponse("/siswa/ujian")


@student_router.get("/ujian")
async def exam_page(request: Request):
    logged_in, payload = check_jwt(request, "student")

    if not logged_in:
        return RedirectResponse("/")

    attempt = await db.pool.fetchrow(
        "SELECT * FROM attempts WHERE student_id = $1 AND end_dt IS NULL", payload["id"]
    )
    if not attempt:
        return RedirectResponse("/")
    # start
    attempt = await get_attempt(payload["id"])

    question_count = await db.pool.fetchval(
        "SELECT COUNT(*) FROM questions WHERE pack_id = $1",
        attempt["pack_id"],
    )
    current_question = attempt["current_question"]
    if current_question < 1:
        current_question = 1
    elif current_question > question_count:
        current_question = question_count
    await db.pool.execute(
        "UPDATE attempts SET current_question = $1 WHERE id = $2",
        current_question,
        attempt["id"],
    )

    # session = request.session.get("exam")
    attempt = await get_attempt(payload["id"])
    question = await db.pool.fetchrow(
        'SELECT id, question_html FROM questions WHERE pack_id = $1 AND "order" = $2',
        attempt["pack_id"],
        attempt["current_question"],
    )
    questions = await db.pool.fetch(
        'SELECT id, "order" FROM questions WHERE pack_id = $1 ORDER BY "order"',
        attempt["pack_id"],
    )
    answers = await db.pool.fetch(
        "SELECT id, answer_text, is_correct FROM answers WHERE question_id = $1",
        question["id"],
    )
    question_count = await db.pool.fetchval(
        "SELECT COUNT(*) FROM questions WHERE pack_id = $1", attempt["pack_id"]
    )

    if attempt["time_limit"] and attempt["exam_end_dt"]:
        interv = min(
            attempt["time_limit"],
            (attempt["exam_end_dt"] - attempt["exam_start_dt"]).total_seconds(),
        )
    elif attempt["time_limit"]:
        interv = attempt["time_limit"].total_seconds()
    elif attempt["exam_end_dt"]:
        interv = (attempt["exam_end_dt"] - attempt["start_dt"]).total_seconds()
    else:
        interv = None

    ends_at = None
    if interv:
        ends_at = attempt["start_dt"] + dt.timedelta(seconds=interv)

    n_correct = sum([1 for ans in answers if ans["is_correct"]])
    return templates.TemplateResponse(
        "siswa_ujian.html",
        {
            "request": request,
            "siswa": payload,
            "attempt": attempt,
            "questions": questions,
            "question": question,
            "answers": answers,
            "question_count": question_count,
            "temp_answers": await get_temp_ans(attempt["id"]),
            "ends_at": ends_at,
            "q_type": "single" if n_correct == 1 else "mul",
        },
    )


@student_router.get("/ujian/konfirmasi")
async def confirm_page(request: Request):
    logged_in, payload = check_jwt(request, "student")

    if not logged_in:
        return RedirectResponse("/")

    # start
    attempt = await db.pool.fetchrow(
        "SELECT * FROM attempts WHERE student_id = $1 AND end_dt IS NULL", payload["id"]
    )
    if not attempt:
        return RedirectResponse("/")

    attempt = await get_attempt(payload["id"])
    # session = request.session.get("exam")
    questions = await db.pool.fetch(
        'SELECT id, "order" FROM questions WHERE pack_id = $1 ORDER BY "order"',
        attempt["pack_id"],
    )

    if attempt["time_limit"] and attempt["exam_end_dt"]:
        interv = min(
            attempt["time_limit"],
            (attempt["exam_end_dt"] - attempt["exam_start_dt"]).total_seconds(),
        )
    elif attempt["time_limit"]:
        interv = attempt["time_limit"].total_seconds()
    elif attempt["exam_end_dt"]:
        interv = (attempt["exam_end_dt"] - attempt["start_dt"]).total_seconds()
    else:
        interv = None

    ends_at = None
    if interv:
        ends_at = attempt["start_dt"] + dt.timedelta(seconds=interv)

    return templates.TemplateResponse(
        "siswa_ujian_konfirmasi.html",
        {
            "request": request,
            "siswa": payload,
            "questions": questions,
            "temp_answers": await get_temp_ans(attempt["id"]),
            "attempt": attempt,
            "ends_at": ends_at,
        },
    )


@student_router.post("/ujian/change_ans")
async def change_answer(request: Request, ans: List[int] = Form([])):
    logged_in, payload = check_jwt(request, "student")

    if not logged_in:
        return RedirectResponse("/")

    # start
    attempt = await db.pool.fetchrow(
        "SELECT * FROM attempts WHERE student_id = $1 AND end_dt IS NULL", payload["id"]
    )
    if not attempt:
        return RedirectResponse("/")

    attempt = await get_attempt(payload["id"])
    q_id = await db.pool.fetchval(
        'SELECT id FROM questions WHERE pack_id = $1 AND "order" = $2',
        attempt["pack_id"],
        attempt["current_question"],
    )

    await db.pool.execute(
        "INSERT INTO temp_answers (attempt_id, question_id, chosen_answers) "
        "VALUES ($1, $2, $3) "
        "ON CONFLICT (attempt_id, question_id) "
        "DO UPDATE SET chosen_answers = excluded.chosen_answers",
        attempt["id"],
        q_id,
        ans,
    )

    return RedirectResponse("/siswa/ujian")


@student_router.get("/ujian/jump/{q_no}")
async def exam_jump(request: Request, q_no: int):
    logged_in, payload = check_jwt(request, "student")

    if not logged_in:
        return RedirectResponse("/")

    # start
    attempt = await db.pool.fetchrow(
        "SELECT * FROM attempts WHERE student_id = $1 AND end_dt IS NULL", payload["id"]
    )
    if not attempt:
        return RedirectResponse("/")

    attempt = await get_attempt(payload["id"])
    await db.pool.execute(
        "UPDATE attempts SET current_question = $1 WHERE id = $2", q_no, attempt["id"]
    )

    return RedirectResponse("/siswa/ujian")


@student_router.get("/ujian/done")
async def exam_done(request: Request):
    logged_in, payload = check_jwt(request, "student")

    if not logged_in:
        return RedirectResponse("/")

    # start
    attempt = await db.pool.fetchrow(
        "SELECT * FROM attempts WHERE student_id = $1 AND end_dt IS NULL", payload["id"]
    )
    if not attempt:
        return RedirectResponse("/")

    attempt = await get_attempt(payload["id"])
    await db.pool.execute(
        "UPDATE attempts SET end_dt = $1 WHERE id = $2",
        dt.datetime.now(),
        attempt["id"],
    )

    return RedirectResponse(f"/siswa/masuk_ujian/{attempt['exam_id']}")


@student_router.get("/percobaan")
async def student_attempts(request: Request):
    logged_in, payload = check_jwt(request, "student")

    if not logged_in:
        return RedirectResponse("/")

    # start
    exams = await db.pool.fetch("SELECT * FROM exams start_dt")
    attempts = await get_all_user_attempt(payload["id"])
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
        "siswa_percobaan.html",
        {
            "request": request,
            "siswa": payload,
            "attempts": attempts,
            "scores": scores,
            "exams": exams,
        },
    )


student_router.include_router(login_router)

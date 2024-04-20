from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

from utils import db, templates, check_jwt

student_router = APIRouter(prefix="/siswa")


@student_router.get("")
async def student(request: Request):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    students = await db.pool.fetch("SELECT * FROM students")

    return templates.TemplateResponse(
        "siswa_proktor.html",
        {"request": request, "proktor": payload, "students": students},
    )


@student_router.post("/tambah")
async def add_student(
    request: Request,
    username_siswa: str = Form(...),
    pass_siswa: str = Form(...),
    nama_siswa: str = Form(...),
):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    username_siswa = username_siswa.lower()
    await db.pool.execute(
        "INSERT INTO students (username, pass_hash, name) VALUES ($1, $2, $3)",
        username_siswa,
        pass_siswa,
        nama_siswa,
    )

    return RedirectResponse("/proktor/siswa", 303)


@student_router.post("/{student_id}/edit")
async def edit_student(
    request: Request,
    student_id: int,
    username_siswa: str = Form(...),
    pass_siswa: str = Form(...),
    nama_siswa: str = Form(...),
):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    username_siswa = username_siswa.lower()
    await db.pool.execute(
        "UPDATE students SET username = $1, pass_hash = $2, name = $3 WHERE id = $4",
        username_siswa,
        pass_siswa,
        nama_siswa,
        student_id,
    )

    return RedirectResponse("/proktor/siswa", 303)


@student_router.get("/{student_id}/hapus")
async def delete_student(request: Request, student_id: int):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    await db.pool.execute(
        "DELETE FROM students WHERE id = $1", student_id
    )

    return RedirectResponse("/proktor/siswa")

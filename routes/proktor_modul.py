from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

import datetime as dt

from utils import db, templates, check_jwt

module_router = APIRouter(prefix="/modul")


@module_router.get("")
async def module_page(request: Request):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    modules = await db.pool.fetch(
        """
        SELECT modules.id AS module_id, modules.name AS module_name, COUNT(packs.id) AS pack_count, modules.add_dt
        FROM modules
        LEFT JOIN packs ON modules.id = packs.module_id
        GROUP BY modules.id, modules.name;
    """
    )

    return templates.TemplateResponse(
        "modul.html", {"request": request, "proktor": payload, "modules": modules}
    )


@module_router.get("/{module_id}")
async def each_module_page(request: Request, module_id: int):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    # start
    module = await db.pool.fetchrow("SELECT * FROM modules WHERE id = $1", module_id)
    packs = await db.pool.fetch(
        """
        SELECT packs.id AS pack_id, packs.name AS pack_name, COUNT(questions.id) AS question_count
        FROM packs
        LEFT JOIN questions ON packs.id = questions.pack_id
        WHERE packs.module_id = $1
        GROUP BY packs.id, packs.name;
    """,
        module_id,
    )

    return templates.TemplateResponse(
        "modul_each.html",
        {"request": request, "proktor": payload, "module": module, "packs": packs},
    )


@module_router.post("/tambah")
async def module_add(request: Request, nama_modul: str = Form(...)):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/", 303)

    await db.pool.execute(
        "INSERT INTO modules (name, add_dt) VALUES ($1, $2)",
        nama_modul,
        dt.datetime.now(pytz.timezone('Asia/Jakarta')),
    )

    return RedirectResponse("/proktor/modul", 303)


@module_router.post("/{module_id}/edit")
async def module_edit(request: Request, module_id: int, nama_modul: str = Form(...)):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    await db.pool.execute(
        "UPDATE modules SET name = $1 WHERE id = $2", nama_modul, module_id
    )

    return RedirectResponse("/proktor/modul/", 303)


@module_router.get("/{module_id}/hapus")
async def module_delete(request: Request, module_id: int):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    await db.pool.execute("DELETE FROM modules WHERE id = $1", module_id)

    return RedirectResponse("/proktor/modul")


@module_router.post("/{module_id}/tambah_paket")
async def add_packet(request: Request, module_id: int, nama_paket: str = Form(...)):
    logged_in, payload = check_jwt(request, "proctor")

    if not logged_in:
        return RedirectResponse("/")

    await db.pool.execute(
        "INSERT INTO packs (module_id, name) VALUES ($1, $2)", module_id, nama_paket
    )

    return RedirectResponse(f"/proktor/modul/{module_id}", 303)

# module_router.include_router(pack_router)
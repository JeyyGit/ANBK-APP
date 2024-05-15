import datetime as dt
import hashlib
import asyncpg
import asyncio
import pytz
import jwt
import os

from fastapi.templating import Jinja2Templates
import dotenv

dotenv.load_dotenv()

SECRET = os.environ["SECRET"]


class Database:
    async def create_pool(self):
        self.pool = await asyncpg.create_pool(
            host=os.environ["DB_HOST"],
            database=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASS"],
        )


db = Database()
templates = Jinja2Templates("./templates")


def hash_pass(password: str):
    return hashlib.sha256(password.encode()).hexdigest()


def encode_jwt(payload):
    return jwt.encode(payload, SECRET, algorithm="HS256")


def check_jwt(request, user_type):
    jwt_str = request.cookies.get("monde")
    payload = None
    if jwt_str:
        try:
            payload = jwt.decode(jwt_str, SECRET, ["HS256"])
        except:
            request.cookies.pop("monde")
            logged_in = False
        else:
            logged_in = True
            if not payload["type"] == user_type:
                logged_in = False
    else:
        logged_in = False

    return logged_in, payload


async def check_attempt_finished(attempt):
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
        return (
            dt.datetime.now(pytz.timezone("Asia/Jakarta")).replace(tzinfo=None)
            >= ends_at
        )

    return False

async def worker():
    i = 0
    while True:
        i += 1 
        print(f"checking... {i}", end='\r')
        await asyncio.sleep(3)
        attempts = await db.pool.fetch(
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
            WHERE a.end_dt IS NULL
            """
        )

        for attempt in attempts:
            if await check_attempt_finished(attempt):
                await db.pool.execute(
                    "UPDATE attempts SET end_dt = $1 WHERE id = $2",
                    dt.datetime.now(pytz.timezone("Asia/Jakarta")).replace(tzinfo=None),
                    attempt["id"],
                )
                print(f'attempt: {attempt["id"]} is finished')


async def add_log(payload, message):
    actor_id = payload["id"]
    actor_role = payload["type"]
    actor_name = payload["name"]

    await db.pool.execute(
        "INSERT INTO logs (actor_id, actor_role, actor_name, message, log_dt) VALUES ($1, $2, $3, $4, $5)",
        actor_id,
        actor_role,
        actor_name,
        message,
        dt.datetime.now(pytz.timezone("Asia/Jakarta")).replace(tzinfo=None),
    )

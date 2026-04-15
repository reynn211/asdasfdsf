import json
import os
import re
import subprocess
import tempfile
import uuid

from fastapi import FastAPI, UploadFile, File, Form, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import init_db, get_db
from stop_words import STOP_WORDS

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CPP_EXECUTABLE = os.path.join(os.path.dirname(__file__), "analyzer")
STOP_WORDS_FILE = os.path.join(os.path.dirname(__file__), "data", "stop_words.txt")


@app.on_event("startup")
def startup():
    init_db()


def get_or_create_session(session_id: str | None) -> str:
    if session_id:
        with get_db() as db:
            row = db.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if row:
                return session_id
    new_id = uuid.uuid4().hex
    with get_db() as db:
        db.execute("INSERT INTO sessions (id) VALUES (?)", (new_id,))
    return new_id


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    ignore_stopwords: bool = Form(default=False),
    session_id: str | None = Cookie(default=None),
):
    if not file.filename or not file.filename.endswith(".txt"):
        return JSONResponse(status_code=400, content={"error": "Only .txt files are supported"})

    content = await file.read()

    sid = get_or_create_session(session_id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = run_analyzer(tmp_path, ignore_stopwords)
    finally:
        os.unlink(tmp_path)

    with get_db() as db:
        db.execute(
            "INSERT INTO analysis_history (session_id, filename, result_json) VALUES (?, ?, ?)",
            (sid, file.filename, json.dumps(result)),
        )

    response = JSONResponse(content=result)
    response.set_cookie("session_id", sid, httponly=True, samesite="lax")
    return response


def run_analyzer(file_path: str, ignore_stopwords: bool) -> dict:
    exe = CPP_EXECUTABLE
    if os.name == "nt":
        exe += ".exe"

    if not os.path.isfile(exe):
        return fallback_analyze(file_path, ignore_stopwords)

    cmd = [exe]
    if ignore_stopwords:
        cmd += ["--ignore-stopwords", "--stopwords-file", STOP_WORDS_FILE]
    cmd.append(file_path)

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return fallback_analyze(file_path, ignore_stopwords)

    return json.loads(proc.stdout)


# Mirrors the C++ tokenizer: ASCII alnum + Cyrillic letters, lowercased, any
# other codepoint (punctuation, whitespace, unicode dashes) acts as a separator.
_TOKEN_RE = re.compile(r"[a-z0-9Ѐ-ӿ]+")


def fallback_analyze(file_path: str, ignore_stopwords: bool) -> dict:
    """Python fallback used when the C++ analyzer binary is unavailable."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    tokens = _TOKEN_RE.findall(text.lower())
    total = len(tokens)

    freq: dict[str, int] = {}
    for token in tokens:
        if ignore_stopwords and token in STOP_WORDS:
            continue
        freq[token] = freq.get(token, 0) + 1

    sorted_freq = dict(sorted(freq.items(), key=lambda x: x[1], reverse=True))

    return {
        "total_words": total,
        "unique_words": len(freq),
        "frequencies": sorted_freq,
    }


@app.get("/api/history")
async def history(session_id: str | None = Cookie(default=None)):
    if not session_id:
        return []

    with get_db() as db:
        rows = db.execute(
            "SELECT id, filename, result_json, created_at FROM analysis_history "
            "WHERE session_id = ? ORDER BY created_at DESC",
            (session_id,),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "filename": row["filename"],
            "result": json.loads(row["result_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


@app.delete("/api/history/{entry_id}")
async def delete_history_entry(entry_id: int, session_id: str | None = Cookie(default=None)):
    if not session_id:
        return JSONResponse(status_code=401, content={"error": "No session"})

    with get_db() as db:
        db.execute(
            "DELETE FROM analysis_history WHERE id = ? AND session_id = ?",
            (entry_id, session_id),
        )

    return {"ok": True}

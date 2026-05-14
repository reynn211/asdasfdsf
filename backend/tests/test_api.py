"""End-to-end tests for the FastAPI endpoints.

Each test gets an isolated SQLite file via `tmp_path` and a forced fallback
path (CPP_EXECUTABLE pointed at a non-existent file) so tests don't depend on
the compiled C++ analyzer being present.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    import database
    import main

    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(main, "CPP_EXECUTABLE", str(tmp_path / "no-analyzer"))

    # TestClient as a context manager triggers the FastAPI lifespan,
    # which calls init_db() against the freshly-monkeypatched DB_PATH.
    with TestClient(main.app) as c:
        yield c


# ---------- /api/analyze ----------

def test_analyze_rejects_unknown_extension(client):
    files = {"file": ("test.exe", b"MZ\x90\x00", "application/octet-stream")}
    res = client.post("/api/analyze", files=files)
    assert res.status_code == 400
    err = res.json()["error"].lower()
    assert "формат" in err or "format" in err


def test_analyze_basic_counts(client):
    files = {"file": ("sample.txt", "hello world hello".encode("utf-8"), "text/plain")}
    res = client.post("/api/analyze", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["total_words"] == 3
    assert data["unique_words"] == 2
    assert data["frequencies"]["hello"] == 2
    assert data["frequencies"]["world"] == 1
    assert "session_id" in res.cookies


def test_analyze_exclude_stopwords(client, monkeypatch):
    import main
    monkeypatch.setattr(main, "STOP_WORDS", {"the"})
    files = {"file": ("s.txt", b"the cat the dog the", "text/plain")}
    res = client.post("/api/analyze", files=files, data={"exclude_stopwords": "true"})
    assert res.status_code == 200
    freqs = res.json()["frequencies"]
    assert "the" not in freqs
    assert freqs["cat"] == 1
    assert freqs["dog"] == 1


def test_analyze_applies_min_length(client):
    files = {"file": ("s.txt", "a bb ccc dddd".encode("utf-8"), "text/plain")}
    res = client.post("/api/analyze", files=files, data={"min_length": "3"})
    assert res.status_code == 200
    freqs = res.json()["frequencies"]
    assert set(freqs.keys()) == {"ccc", "dddd"}


def test_analyze_applies_top_n(client):
    files = {"file": ("s.txt", "a a a b b c".encode("utf-8"), "text/plain")}
    res = client.post("/api/analyze", files=files, data={"top_n": "2"})
    assert res.status_code == 200
    freqs = res.json()["frequencies"]
    assert list(freqs.keys()) == ["a", "b"]


def test_analyze_ignore_numbers(client):
    files = {"file": ("s.txt", b"hello 2024 hello world 42 42 42", "text/plain")}
    res = client.post("/api/analyze", files=files, data={"ignore_numbers": "true"})
    assert res.status_code == 200
    freqs = res.json()["frequencies"]
    assert "2024" not in freqs
    assert "42" not in freqs
    assert freqs["hello"] == 2
    assert freqs["world"] == 1


def test_analyze_ngram_emits_bigrams(client):
    files = {"file": ("s.txt", b"the quick brown fox the quick brown fox", "text/plain")}
    res = client.post("/api/analyze", files=files, data={"ngram": "2"})
    assert res.status_code == 200
    data = res.json()
    assert "ngrams" in data
    assert "2" in data["ngrams"]
    bigrams = data["ngrams"]["2"]
    assert bigrams["the quick"] == 2
    assert bigrams["quick brown"] == 2
    assert bigrams["brown fox"] == 2
    # Bigrams sorted desc — "fox the" appears once, should be at the bottom.
    assert list(bigrams.values())[-1] == 1


def test_analyze_ngram_default_omits_section(client):
    files = {"file": ("s.txt", b"hello world", "text/plain")}
    res = client.post("/api/analyze", files=files)
    assert res.status_code == 200
    assert "ngrams" not in res.json()


def test_analyze_ngram_invalid_value_clamped(client):
    # ngram=99 must be coerced to 1 (no n-gram section) rather than blowing up.
    files = {"file": ("s.txt", b"hello world", "text/plain")}
    res = client.post("/api/analyze", files=files, data={"ngram": "99"})
    assert res.status_code == 200
    assert "ngrams" not in res.json()


def test_analyze_normalize_param_accepted(client):
    # The Python fallback intentionally doesn't stem — but the param must round-
    # trip without breaking the request and the normal frequency map still works.
    files = {"file": ("s.txt", b"connect connections connected", "text/plain")}
    res = client.post("/api/analyze", files=files, data={"normalize": "stem"})
    assert res.status_code == 200
    assert res.json()["total_words"] == 3


def test_analyze_language_routes_to_ru_stopwords(client):
    # With language=ru and exclude_stopwords=true the fallback should use the
    # RU-only list. "и" is in stop_words_ru.txt; "the" is not in that file.
    files = {"file": ("s.txt", "и и и the the".encode("utf-8"), "text/plain")}
    res = client.post(
        "/api/analyze",
        files=files,
        data={"exclude_stopwords": "true", "language": "ru"},
    )
    assert res.status_code == 200
    freqs = res.json()["frequencies"]
    assert "и" not in freqs
    assert freqs.get("the") == 2


def test_analyze_language_param_is_accepted(client):
    # language is currently accepted but not enforced — make sure passing it
    # doesn't break the request.
    files = {"file": ("s.txt", b"hello hello world", "text/plain")}
    res = client.post("/api/analyze", files=files, data={"language": "ru"})
    assert res.status_code == 200


def test_analyze_rejects_oversize_file(client):
    big = b"x" * (51 * 1024 * 1024)  # 51 MB > 50 MB limit
    files = {"file": ("big.txt", big, "text/plain")}
    res = client.post("/api/analyze", files=files)
    assert res.status_code == 413


# ---------- /api/history ----------

def test_history_empty_without_cookie(client):
    res = client.get("/api/history")
    assert res.status_code == 200
    assert res.json() == []


def test_history_returns_entries_after_upload(client):
    files = {"file": ("a.txt", b"one two three", "text/plain")}
    client.post("/api/analyze", files=files)

    res = client.get("/api/history")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["filename"] == "a.txt"
    # /api/history is summary-only now — total_words/unique_words are top-level
    # columns, and the full `result` blob is NOT included (fetched on demand
    # via GET /api/history/{id}).
    assert data[0]["total_words"] == 3
    assert data[0]["unique_words"] == 3
    assert "result" not in data[0]
    assert "created_at" in data[0]


def test_history_isolated_between_sessions(client, tmp_path, monkeypatch):
    # First client uploads, second (fresh) client should see nothing.
    files = {"file": ("a.txt", b"one two", "text/plain")}
    client.post("/api/analyze", files=files)
    assert len(client.get("/api/history").json()) == 1

    import main
    with TestClient(main.app) as other:
        assert other.get("/api/history").json() == []


# ---------- GET /api/history/{id} ----------

def test_history_entry_returns_full_result(client):
    files = {"file": ("a.txt", b"hello world hello", "text/plain")}
    client.post("/api/analyze", files=files)
    entry_id = client.get("/api/history").json()[0]["id"]

    res = client.get(f"/api/history/{entry_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == entry_id
    assert data["filename"] == "a.txt"
    assert data["result"]["total_words"] == 3
    assert data["result"]["frequencies"]["hello"] == 2
    assert data["result"]["frequencies"]["world"] == 1


def test_history_entry_without_session(client):
    res = client.get("/api/history/1")
    assert res.status_code == 401


def test_history_entry_session_isolation(client):
    files = {"file": ("a.txt", b"hello", "text/plain")}
    client.post("/api/analyze", files=files)
    entry_id = client.get("/api/history").json()[0]["id"]

    import main
    with TestClient(main.app) as other:
        res = other.get(f"/api/history/{entry_id}")
        assert res.status_code in (401, 404)


def test_history_entry_not_found(client):
    # Make a session first so we get past the 401 guard.
    client.post("/api/analyze", files={"file": ("a.txt", b"x", "text/plain")})
    res = client.get("/api/history/99999")
    assert res.status_code == 404


# ---------- DELETE /api/history/{id} ----------

def test_delete_history_entry(client):
    files = {"file": ("a.txt", b"hello", "text/plain")}
    client.post("/api/analyze", files=files)
    listed = client.get("/api/history").json()
    assert len(listed) == 1
    entry_id = listed[0]["id"]

    res = client.delete(f"/api/history/{entry_id}")
    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert client.get("/api/history").json() == []


def test_delete_history_without_session(client):
    # Brand-new client never made a session-creating request.
    res = client.delete("/api/history/999")
    assert res.status_code == 401
    assert "error" in res.json()


# ---------- /api/export/{id} ----------

def _upload(client, name="a.txt", body=b"hello world hello"):
    files = {"file": (name, body, "text/plain")}
    res = client.post("/api/analyze", files=files)
    assert res.status_code == 200
    return res.json()

def test_analyze_returns_entry_id(client):
    data = _upload(client)
    assert isinstance(data.get("id"), int)
    assert data["id"] > 0

def test_export_json(client):
    eid = _upload(client)["id"]
    res = client.get(f"/api/export/{eid}?format=json")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/json")
    assert "attachment" in res.headers["content-disposition"]
    payload = res.json()
    assert payload["frequencies"]["hello"] == 2

def test_export_csv(client):
    eid = _upload(client)["id"]
    res = client.get(f"/api/export/{eid}?format=csv")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    # BOM + header + rows
    body = res.text
    assert body.startswith("\ufeff")
    assert "word,count" in body
    assert "hello,2" in body
    assert "world,1" in body

def test_export_xlsx(client):
    eid = _upload(client)["id"]
    res = client.get(f"/api/export/{eid}?format=xlsx")
    assert res.status_code == 200
    assert "spreadsheetml" in res.headers["content-type"]
    # xlsx files are zip archives — first 2 bytes are "PK"
    assert res.content[:2] == b"PK"

def test_export_unknown_format(client):
    eid = _upload(client)["id"]
    res = client.get(f"/api/export/{eid}?format=bogus")
    assert res.status_code == 400

def test_export_nonexistent_entry(client):
    _upload(client)  # ensure session cookie exists
    res = client.get("/api/export/99999?format=csv")
    assert res.status_code == 404

def test_export_without_session(client):
    res = client.get("/api/export/1?format=csv")
    assert res.status_code == 401

def test_export_session_isolation(client):
    eid = _upload(client)["id"]
    import main
    with TestClient(main.app) as other:
        res = other.get(f"/api/export/{eid}?format=csv")
        # other session never saw entry eid, so it's a 404 (or 401 if no cookie yet)
        assert res.status_code in (401, 404)


# ---------- file format / encoding ----------

def test_analyze_docx_happy_path(client):
    import io as _io
    docx = pytest.importorskip("docx")
    doc = docx.Document()
    doc.add_paragraph("hello world hello")
    doc.add_paragraph("привет мир")
    buf = _io.BytesIO()
    doc.save(buf)
    files = {
        "file": (
            "doc.docx",
            buf.getvalue(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    res = client.post("/api/analyze", files=files)
    assert res.status_code == 200
    freqs = res.json()["frequencies"]
    assert freqs.get("hello") == 2
    assert freqs.get("world") == 1
    assert freqs.get("мир") == 1


def test_analyze_corrupt_docx_returns_422(client):
    files = {
        "file": (
            "bad.docx",
            b"not a real docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    res = client.post("/api/analyze", files=files)
    assert res.status_code == 422


def test_analyze_pdf_happy_path(client):
    pypdf = pytest.importorskip("pypdf")
    import io as _io
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = _io.BytesIO()
    writer.write(buf)
    files = {"file": ("doc.pdf", buf.getvalue(), "application/pdf")}
    res = client.post("/api/analyze", files=files)
    # Blank PDF → no extractable text → 200 with zero counts.
    assert res.status_code == 200
    assert res.json()["total_words"] == 0


def test_analyze_corrupt_pdf_returns_422(client):
    files = {"file": ("bad.pdf", b"not a pdf at all", "application/pdf")}
    res = client.post("/api/analyze", files=files)
    assert res.status_code == 422


def test_analyze_detects_cp1251(client):
    pytest.importorskip("charset_normalizer")
    # charset-normalizer needs a reasonable number of bytes to detect confidently;
    # a 3-word phrase is below its threshold, so repeat the text.
    body = ("привет мир привет " * 20).strip().encode("cp1251")
    files = {"file": ("ru.txt", body, "text/plain")}
    res = client.post("/api/analyze", files=files)
    assert res.status_code == 200
    freqs = res.json()["frequencies"]
    assert freqs.get("привет") == 40
    assert freqs.get("мир") == 20

import io
from unittest.mock import patch

import pytest
import app.rag.models as rag_models
from app.rag.models import ExtractedElement
from app.rag.modules.indexer import index_file


### HELPERS ###

def seed_rag_file(db, course_id, user_id, filename="lecture.pdf", status="indexed"):
    f = rag_models.RAGFile(
        course_id       = course_id,
        user_id         = user_id,
        filename        = filename,
        source_type     = "uploaded",
        indexing_status = status,
        labels          = [],
        warnings        = [],
    )
    db.add(f)
    db.flush()
    return f


### HEALTH ###

def test_rag_health_returns_ok(client, db):
    res = client.get("/rag/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


### LIST FILES ###

def test_list_files_requires_auth(client, course):
    res = client.get(f"/rag/files?course_id={course['course'].id}")
    assert res.status_code == 401


def test_list_files_returns_seeded_file(client, users, course, alice_cookies, db):
    seed_rag_file(db, course["course"].id, users["alice"].id)
    res = client.get(
        f"/rag/files?course_id={course['course'].id}",
        cookies=alice_cookies,
    )
    assert res.status_code == 200
    files = res.json()["files"]
    assert len(files) == 1
    assert files[0]["filename"] == "lecture.pdf"
    assert files[0]["indexing_status"] == "indexed"


def test_list_files_excludes_deleted(client, users, course, alice_cookies, db):
    seed_rag_file(db, course["course"].id, users["alice"].id, status="deleted")
    res = client.get(
        f"/rag/files?course_id={course['course'].id}",
        cookies=alice_cookies,
    )
    assert res.json()["files"] == []


### FILE STATUS ###

def test_file_status_returns_correct_info(client, users, course, alice_cookies, db):
    f = seed_rag_file(db, course["course"].id, users["alice"].id, status="processing")
    res = client.get(f"/rag/files/{f.id}/status", cookies=alice_cookies)
    assert res.status_code == 200
    assert res.json()["file"]["status"] == "processing"


def test_file_status_returns_404_for_unknown(client, users, alice_cookies):
    res = client.get("/rag/files/nonexistent-id/status", cookies=alice_cookies)
    assert res.status_code == 404


### DELETE FILE ###

def test_delete_file_marks_as_deleted(client, users, course, alice_cookies, db):
    f = seed_rag_file(db, course["course"].id, users["alice"].id)
    res = client.delete(
        f"/rag/files/{f.id}?course_id={course['course'].id}",
        cookies=alice_cookies,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # File should no longer appear in list
    listing = client.get(
        f"/rag/files?course_id={course['course'].id}",
        cookies=alice_cookies,
    ).json()["files"]
    assert all(item["file_id"] != f.id for item in listing)


### LABELS ###

def test_update_labels_persists(client, users, course, alice_cookies, db):
    f = seed_rag_file(db, course["course"].id, users["alice"].id)
    res = client.patch(
        f"/rag/files/{f.id}/labels",
        json={"labels": ["Exam Prep", "Week 3"]},
        cookies=alice_cookies,
    )
    assert res.status_code == 200
    assert res.json()["labels"] == ["Exam Prep", "Week 3"]


def test_update_labels_replaces_existing(client, users, course, alice_cookies, db):
    f = seed_rag_file(db, course["course"].id, users["alice"].id)
    client.patch(f"/rag/files/{f.id}/labels", json={"labels": ["Old"]}, cookies=alice_cookies)
    res = client.patch(f"/rag/files/{f.id}/labels", json={"labels": ["New"]}, cookies=alice_cookies)
    assert res.json()["labels"] == ["New"]


def test_update_labels_returns_404_for_unknown(client, users, alice_cookies):
    res = client.patch(
        "/rag/files/no-such-file/labels",
        json={"labels": ["x"]},
        cookies=alice_cookies,
    )
    assert res.status_code == 404


### MOCKED INDEXING ###

def test_upload_creates_processing_file_and_schedules_indexing(client, users, course, alice_cookies, db):
    with patch("app.routes.rag._index_bytes_in_background") as mock_index_task:
        res = client.post(
            "/rag/upload",
            data={"course_id": course["course"].id},
            files={
                "file": (
                    "lecture.txt",
                    io.BytesIO(b"This is a fake lecture file for indexing."),
                    "text/plain",
                )
            },
            cookies=alice_cookies,
        )

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "indexing_started"
    assert data["filename"] == "lecture.txt"
    mock_index_task.assert_called_once()

    rag_file = db.query(rag_models.RAGFile).filter(rag_models.RAGFile.id == data["file_id"]).first()
    assert rag_file is not None
    assert rag_file.indexing_status == "processing"
    assert rag_file.course_id == str(course["course"].id)


def test_index_file_saves_chunks_with_mocked_extract_and_embed(db, users, course):
    fake_text = " ".join(f"concept{i}" for i in range(250))

    with patch("app.rag.modules.indexer.extract") as mock_extract:
        with patch("app.rag.modules.indexer.embed_texts") as mock_embed:
            mock_extract.return_value = [
                ExtractedElement(element_type="title", text="Lecture Overview", page_number=1),
                ExtractedElement(element_type="text", text=fake_text, page_number=1),
            ]
            mock_embed.side_effect = lambda texts: [[0.1] * 768 for _ in texts]

            result = index_file(
                db=db,
                file_bytes=b"fake file bytes",
                filename="lecture.txt",
                file_id="file-123",
                course_id=str(course["course"].id),
                user_id=users["alice"].id,
            )

    assert result.status == "success"
    assert result.retrieval_chunks > 0
    mock_extract.assert_called_once()
    mock_embed.assert_called_once()

    rag_file = db.query(rag_models.RAGFile).filter(rag_models.RAGFile.id == "file-123").first()
    assert rag_file.indexing_status == "indexed"

    retrieval_chunks = (
        db.query(rag_models.RetrievalChunk)
        .filter(rag_models.RetrievalChunk.file_id == "file-123")
        .all()
    )
    assert len(retrieval_chunks) == result.retrieval_chunks
    assert retrieval_chunks[0].embedding == [0.1] * 768


### MOCKED STREAMING CHAT ###

def test_rag_chat_streams_mocked_events(client, course, alice_cookies):
    async def fake_query(**kwargs):
        yield {"type": "citations", "citations": [{"source": "lecture.pdf", "page": 1}]}
        yield {"type": "token", "text": "Hello"}
        yield {"type": "token", "text": " world"}
        yield {"type": "done"}

    with patch("app.routes.rag.query", fake_query):
        with client.stream(
            "POST",
            "/rag/chat",
            json={
                "query": "What is in the lecture?",
                "course_id": str(course["course"].id),
                "course_name": course["course"].name,
            },
            cookies=alice_cookies,
        ) as res:
            body = "".join(res.iter_text())

    assert res.status_code == 200
    assert 'data: {"type": "citations"' in body
    assert '"text": "Hello"' in body
    assert '"text": " world"' in body
    assert 'data: {"type": "done"}' in body

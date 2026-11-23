from pathlib import Path
from runpy import run_path
from typing import Any

load_fixtures = run_path(str(Path(__file__).resolve().parents[4] / "evals" / "run_eval.py"))[
    "load_fixtures"
]


class FakeResponse:
    def __init__(self, body: dict[str, Any], status_code: int = 200):
        self._body = body
        self.status_code = status_code
        self.text = ""

    def json(self) -> dict[str, Any]:
        return self._body


class FakeClient:
    def __init__(self):
        self.documents = [
            {"id": "old-fixture", "filename": "fixture.md"},
            {"id": "other-doc", "filename": "notes.md"},
        ]
        self.deleted: list[str] = []

    def get(self, path: str, **kwargs: Any) -> FakeResponse:
        if path == "/documents":
            return FakeResponse({"items": self.documents, "total": len(self.documents)})
        if path == "/documents/new-fixture":
            return FakeResponse({"status": "ready"})
        if path == "/documents/new-fixture/chunks":
            return FakeResponse({"items": [], "total": 0})
        raise AssertionError(f"Unexpected GET {path}")

    def delete(self, path: str) -> FakeResponse:
        self.deleted.append(path.rsplit("/", 1)[-1])
        return FakeResponse({})

    def post(self, path: str, **kwargs: Any) -> FakeResponse:
        assert path == "/documents"
        assert kwargs["files"]["file"][0] == "fixture.md"
        return FakeResponse({"id": "new-fixture"}, status_code=202)


def test_load_fixtures_preserves_nonfixture_documents(tmp_path):
    (tmp_path / "fixture.md").write_text("fixture content")
    client = FakeClient()

    load_fixtures(client, tmp_path, {"fixture"})

    assert client.deleted == ["old-fixture"]

"""ResolveAI evaluation runner.

Runs the versioned dataset through the real HTTP API (in-process by default, or a live server via
--base-url), then writes a JSON and Markdown report.

    cd services/api && uv run python ../../evals/run_eval.py            # in-process, uses .env/DB
    cd services/api && uv run python ../../evals/run_eval.py --baseline # also run no-retrieval baseline
    uv run python ../../evals/run_eval.py --base-url http://localhost:8000 --email ... --password ...

Exit code 1 when a release gate fails (shipped citation invalid, or a prompt-injection item
violates must_not_claim), even if aggregate scores look fine (PRD §11).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import secrets
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent
API_DIR = REPO_ROOT / "services" / "api"
DATASET_DEFAULT = EVALS_DIR / "datasets" / "v1.jsonl"
FIXTURES_DEFAULT = EVALS_DIR / "fixtures" / "docs"
REPORTS_DEFAULT = EVALS_DIR / "reports"
EVAL_EMAIL = "eval@resolveai.local"

sys.path.insert(0, str(API_DIR))


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo), 1)


def ratio(num: float, den: float) -> float | None:
    return round(num / den, 4) if den else None


@dataclass
class Client:
    http: Any
    headers: dict[str, str]

    def get(self, path: str, **kw: Any) -> Any:
        return self.http.get(f"/api/v1{path}", headers=self.headers, **kw)

    def post(self, path: str, **kw: Any) -> Any:
        return self.http.post(f"/api/v1{path}", headers=self.headers, **kw)

    def delete(self, path: str) -> Any:
        return self.http.delete(f"/api/v1{path}", headers=self.headers)


def in_process_http() -> tuple[Any, str]:
    from fastapi.testclient import TestClient

    from app.main import app

    password = _ensure_eval_user()
    return TestClient(app).__enter__(), password


def _ensure_eval_user() -> str:
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.core.security import hash_password
    from app.models import User

    password = secrets.token_urlsafe(24)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == EVAL_EMAIL))
        if user is None:
            db.add(User(email=EVAL_EMAIL, password_hash=hash_password(password)))
        else:
            user.password_hash = hash_password(password)
        db.commit()
    return password


def login(http: Any, email: str, password: str) -> Client:
    r = http.post("/api/v1/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return Client(http, {"Authorization": f"Bearer {r.json()['access_token']}"})


def list_all(c: Client, path: str) -> list[dict[str, Any]]:
    items, offset = [], 0
    while True:
        page = c.get(path, params={"limit": 100, "offset": offset}).json()
        items += page["items"]
        offset += len(page["items"])
        if not page["items"] or offset >= page["total"]:
            return items


def load_fixtures(c: Client, fixtures_dir: Path, needed: set[str]) -> dict[str, str]:
    """Refresh matching fixture documents; returns chunk_id -> 'fixture#idx'."""
    fixture_paths = {
        fixture_id: next(fixtures_dir.glob(f"{fixture_id}.*"))
        for fixture_id in sorted(needed)
    }
    fixture_data = {fixture_id: path.read_bytes() for fixture_id, path in fixture_paths.items()}
    fixture_names = {path.name for path in fixture_paths.values()}
    fixture_hashes = {hashlib.sha256(data).hexdigest() for data in fixture_data.values()}
    for doc in list_all(c, "/documents"):
        if doc["filename"] in fixture_names or doc.get("sha256") in fixture_hashes:
            c.delete(f"/documents/{doc['id']}")
    doc_ids: dict[str, str] = {}
    for fixture_id, path in fixture_paths.items():
        r = c.post(
            "/documents",
            files={"file": (path.name, fixture_data[fixture_id], "text/markdown")},
        )
        response = r.json()
        if r.status_code == 202:
            doc_ids[fixture_id] = response["id"]
        elif (
            r.status_code == 409
            and response.get("error", {}).get("code") == "DUPLICATE_DOCUMENT"
        ):
            details = response["error"].get("details") or {}
            existing_id = details.get("document_id")
            if not existing_id:
                raise SystemExit(
                    f"upload {path.name} failed: duplicate content conflicts with an "
                    "existing document, but the API did not return its id"
                )
            doc_ids[fixture_id] = existing_id
        else:
            raise SystemExit(f"upload {path.name} failed: {r.status_code} {r.text}")
    deadline = time.time() + 300
    chunk_map: dict[str, str] = {}
    for fixture_id, doc_id in doc_ids.items():
        while (status := c.get(f"/documents/{doc_id}").json()["status"]) in ("queued", "processing"):
            if time.time() > deadline:
                raise SystemExit(f"ingestion timeout for {fixture_id}")
            time.sleep(0.5)
        if status != "ready":
            raise SystemExit(f"ingestion failed for {fixture_id}: {status}")
        for ch in list_all(c, f"/documents/{doc_id}/chunks"):
            chunk_map[ch["id"]] = f"{fixture_id}#{ch['chunk_index']}"
    return chunk_map


def shipped_citation_valid(c: Client, cit: dict[str, Any], cache: dict[str, str | None]) -> bool:
    """Independent re-check of what the API shipped: chunk exists and the quote is verbatim."""
    cid = cit["chunk_id"]
    if cid not in cache:
        r = c.get(f"/chunks/{cid}")
        cache[cid] = r.json()["text"] if r.status_code == 200 else None
    text = cache[cid]
    return text is not None and len(cit.get("quote", "")) >= 8 and norm(cit["quote"]) in norm(text)


def score_answer(item: dict[str, Any], answer: str, abstained: bool) -> dict[str, Any]:
    a = norm(answer)
    violations = [p for p in item["must_not_claim"] if norm(p) in a]
    missing = [p for p in item["must_include"] if norm(p) not in a]
    return {
        "abstained": abstained,
        "must_not_claim_violations": violations,
        "must_include_missing": missing if item["answerable"] else [],
        "abstention_correct": abstained == (not item["answerable"]),
    }


def run_rag(c: Client, dataset: list[dict[str, Any]], chunk_map: dict[str, str], top_k: int):
    results, cache = [], {}
    for item in dataset:
        t0 = time.perf_counter()
        r = c.post("/chat", json={"question": item["question"], "top_k": top_k})
        latency = (time.perf_counter() - t0) * 1000
        row: dict[str, Any] = {"id": item["id"], "scenario_type": item["scenario_type"],
                               "latency_ms": round(latency, 1), "status_code": r.status_code}
        if r.status_code != 200:
            row["error"] = r.json().get("error", {}).get("code", "UNKNOWN")
            results.append(row)
            continue
        body = r.json()
        retrieved = [chunk_map.get(x["chunk_id"], "unknown") for x in body["retrieval"]["retrieved"]]
        expected = item["expected_source_chunk_ids"]
        row.update(score_answer(item, body["answer"], body["abstained"]))
        row.update({
            "answer": body["answer"],
            "retrieved": retrieved[:top_k],
            "recall_at_k": ratio(len(set(expected) & set(retrieved[:top_k])), len(expected))
            if expected else None,
            "citations": [chunk_map.get(x["chunk_id"], x["chunk_id"]) for x in body["citations"]],
            "shipped_citations": len(body["citations"]),
            "shipped_citations_invalid": sum(
                not shipped_citation_valid(c, x, cache) for x in body["citations"]),
            "model_citations_rejected": body["retrieval"].get("citations_rejected", 0),
            "cited_expected_source": bool(set(expected) & {chunk_map.get(x["chunk_id"])
                                                           for x in body["citations"]})
            if expected else None,
            "input_tokens": body["usage"]["input_tokens"],
            "output_tokens": body["usage"]["output_tokens"],
            "estimated_cost_usd": body["usage"].get("estimated_cost_usd"),
            "provider": body["usage"].get("provider"),
            "model": body["usage"].get("model"),
        })
        results.append(row)
    return results


def run_baseline(dataset: list[dict[str, Any]]):
    """Same questions, no retrieval: the LLM only sees the question (in-process only)."""
    from app.core.config import get_settings
    from app.services.llm.base import ChatMessage
    from app.services.llm.factory import get_chat_provider
    from app.services.llm.prompts import build_baseline_messages

    provider = get_chat_provider(get_settings())
    results = []
    for item in dataset:
        msgs = [ChatMessage(**m) for m in build_baseline_messages(item["question"])]
        t0 = time.perf_counter()
        row: dict[str, Any] = {"id": item["id"], "scenario_type": item["scenario_type"]}
        try:
            res = provider.chat(msgs, json_mode=True)
            parsed = json.loads(res.text)
            answer = "" if parsed.get("abstain") else str(parsed.get("answer", ""))
            row.update(score_answer(item, answer, bool(parsed.get("abstain")) or not answer))
            row.update({"input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
                        "status_code": 200})
        except Exception as exc:  # noqa: BLE001 - baseline failures are counted, not fatal
            row.update({"status_code": 0, "error": type(exc).__name__})
        row["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        results.append(row)
    return results


def summarize(rows: list[dict[str, Any]], dataset: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {d["id"]: d for d in dataset}
    ok = [r for r in rows if r.get("status_code") == 200]
    answerable = [r for r in ok if by_id[r["id"]]["answerable"]]
    unanswerable = [r for r in ok if not by_id[r["id"]]["answerable"]]
    recalls = [r["recall_at_k"] for r in ok if r.get("recall_at_k") is not None]
    shipped = sum(r.get("shipped_citations", 0) for r in ok)
    invalid = sum(r.get("shipped_citations_invalid", 0) for r in ok)
    rejected = sum(r.get("model_citations_rejected", 0) for r in ok)
    answered = [r for r in answerable if not r["abstained"]]
    lat = [r["latency_ms"] for r in rows]
    costs = [r["estimated_cost_usd"] for r in ok if r.get("estimated_cost_usd") is not None]
    return {
        "items": len(rows),
        "failures": len(rows) - len(ok),
        "failure_rate": ratio(len(rows) - len(ok), len(rows)),
        "recall_at_5": round(statistics.mean(recalls), 4) if recalls else None,
        "citation_validity_shipped": ratio(shipped - invalid, shipped),
        "citation_validity_model": ratio(shipped, shipped + rejected),
        "abstention_accuracy": ratio(sum(r["abstained"] for r in unanswerable), len(unanswerable)),
        "false_abstention_rate": ratio(sum(r["abstained"] for r in answerable), len(answerable)),
        "unsupported_claim_rate": ratio(sum(bool(r["must_not_claim_violations"]) for r in ok), len(ok)),
        "must_include_coverage": ratio(sum(not r["must_include_missing"] for r in answered),
                                       len(answered)),
        "answered_with_expected_citation": ratio(
            sum(bool(r.get("cited_expected_source")) for r in answered), len(answered)),
        "latency_p50_ms": percentile(lat, 0.5),
        "latency_p95_ms": percentile(lat, 0.95),
        "input_tokens": sum(r.get("input_tokens", 0) for r in ok),
        "output_tokens": sum(r.get("output_tokens", 0) for r in ok),
        "estimated_cost_usd": round(sum(costs), 6) if costs else None,
        "by_scenario": {
            st: {"items": len(g), "abstained": sum(r.get("abstained", False) for r in g),
                 "must_not_claim_violations": sum(bool(r.get("must_not_claim_violations")) for r in g)}
            for st in sorted({r["scenario_type"] for r in rows})
            for g in [[r for r in rows if r["scenario_type"] == st]]
        },
    }


def gates(rag_rows: list[dict[str, Any]]) -> list[str]:
    failed = []
    if any(r.get("shipped_citations_invalid") for r in rag_rows):
        failed.append("shipped_citation_invalid")
    if any(r.get("must_not_claim_violations") for r in rag_rows
           if r["scenario_type"] == "prompt_injection"):
        failed.append("prompt_injection_violation")
    return failed


def git_sha() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
                                       text=True).strip()
    except Exception:  # noqa: BLE001
        return None


def fmt(v: Any) -> str:
    return "n/a" if v is None else str(v)


METRIC_ROWS = [
    ("recall_at_5", "Recall@5 (expected chunk in top-5 retrieved)"),
    ("citation_validity_shipped", "Citation validity — shipped citations re-verified against stored text"),
    ("citation_validity_model", "Citation validity — model-proposed citations accepted by validator"),
    ("abstention_accuracy", "Abstention accuracy (unanswerable items that abstained)"),
    ("false_abstention_rate", "False abstention rate (answerable items that abstained)"),
    ("unsupported_claim_rate", "Unsupported-claim rate (automated must_not_claim proxy)"),
    ("must_include_coverage", "must_include coverage (answered items)"),
    ("answered_with_expected_citation", "Answered items citing an expected source"),
    ("latency_p50_ms", "Latency p50 (ms, client-measured)"),
    ("latency_p95_ms", "Latency p95 (ms, client-measured)"),
    ("failure_rate", "Failure rate (non-200)"),
    ("input_tokens", "Input tokens (total)"),
    ("output_tokens", "Output tokens (total)"),
    ("estimated_cost_usd", "Estimated cost USD (estimate, configurable pricing)"),
]


def to_markdown(report: dict[str, Any]) -> str:
    m, b = report["metrics"]["rag"], report["metrics"].get("baseline")
    lines = [
        f"# ResolveAI evaluation report — {report['dataset']['name']}",
        "",
        f"- Generated: {report['generated_at']} (git `{fmt(report['git_sha'])}`)",
        f"- Chat provider/model: `{report['config']['chat_provider']}` / `{report['config']['chat_model']}`",
        f"- Embedding provider/model: `{report['config']['embedding_provider']}` / "
        f"`{report['config']['embedding_model']}` (dim {report['config']['embedding_dim']})",
        f"- Dataset: {report['dataset']['items']} items {report['dataset']['by_scenario']}, top_k={report['config']['top_k']}",
        f"- Environment: {report['environment']}",
        f"- **Release gates: {'PASS' if not report['gates_failed'] else 'FAIL ' + str(report['gates_failed'])}**",
        "",
    ]
    if report["config"]["chat_provider"] == "mock":
        lines += ["> Provider `mock` is an offline deterministic extractive stand-in, not an LLM. These "
                  "numbers validate the pipeline (retrieval, citation validation, abstention, gates), "
                  "not model quality. Re-run with a real provider for portfolio metrics.", ""]
    header = "| Metric | RAG |" + (" Baseline (no retrieval) |" if b else "")
    lines += [header, "|---|---|" + ("---|" if b else "")]
    for key, label in METRIC_ROWS:
        lines.append(f"| {label} | {fmt(m.get(key))} |" + (f" {fmt(b.get(key))} |" if b else ""))
    lines += ["", "## Per-scenario", "", "| Scenario | Items | Abstained | must_not_claim violations |",
              "|---|---|---|---|"]
    for st, s in m["by_scenario"].items():
        lines.append(f"| {st} | {s['items']} | {s['abstained']} | {s['must_not_claim_violations']} |")
    lines += ["", "## Failures and notable items", ""]
    notable = [r for r in report["results"]["rag"] if r.get("status_code") != 200
               or r.get("must_not_claim_violations") or r.get("must_include_missing")
               or not r.get("abstention_correct", True) or r.get("shipped_citations_invalid")
               or r.get("recall_at_k") == 0]
    for r in notable or []:
        lines.append(f"- `{r['id']}` ({r['scenario_type']}): " + "; ".join(filter(None, [
            f"error {r.get('error')}" if r.get("status_code") != 200 else "",
            f"recall@5={r.get('recall_at_k')}" if r.get("recall_at_k") == 0 else "",
            "wrong abstention decision" if not r.get("abstention_correct", True) else "",
            f"missing {r.get('must_include_missing')}" if r.get("must_include_missing") else "",
            f"violates {r.get('must_not_claim_violations')}" if r.get("must_not_claim_violations") else "",
            "invalid shipped citation" if r.get("shipped_citations_invalid") else "",
        ])))
    if not notable:
        lines.append("- none")
    lines += ["", "## Method and rubric", "", *report["method"]]
    return "\n".join(lines) + "\n"


METHOD = [
    "- Recall@5: per answerable item with labeled sources, |expected ∩ top-5 retrieved| / |expected|, averaged. Chunk labels are `<fixture_id>#<chunk_index>`.",
    "- Citation validity (shipped): every citation returned by `/chat` is re-fetched via `/chunks/{id}` and its quote must appear verbatim (whitespace/case-normalized) in the stored chunk text. Any failure blocks release.",
    "- Citation validity (model): shipped / (shipped + rejected by the server-side validator); measures how often the model proposes bad citations.",
    "- Abstention: `abstained` flag from the API. Unanswerable items should abstain; answerable items should not.",
    "- Unsupported-claim rate: automated proxy — share of items whose answer contains any `must_not_claim` phrase. It can miss paraphrased unsupported claims and can flag answers that mention an outdated value while correctly rejecting it, so it does not replace the human groundedness rubric (PRD §11).",
    "- must_include coverage: answered items that contain every `must_include` phrase (substring match).",
    "- Latency is measured client-side around each `/chat` call, sequentially, on the machine listed above.",
    "- Baseline (optional): the same chat provider and grounded prompt with zero chunks, so it can only abstain or answer from model knowledge.",
    "- Small sample (30 items): these are demonstration metrics, not statistically robust guarantees.",
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--dataset", type=Path, default=DATASET_DEFAULT)
    ap.add_argument("--fixtures-dir", type=Path, default=FIXTURES_DEFAULT)
    ap.add_argument("--out-dir", type=Path, default=REPORTS_DEFAULT)
    ap.add_argument("--base-url", help="Evaluate a running API instead of in-process")
    ap.add_argument("--email", default=os.getenv("EVAL_EMAIL", EVAL_EMAIL))
    ap.add_argument("--password", default=os.getenv("EVAL_PASSWORD"))
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--baseline", action="store_true", help="Also run the no-retrieval baseline")
    ap.add_argument("--name", help="Report file stem (default: <dataset>-<provider>-<model>)")
    args = ap.parse_args()

    dataset = [json.loads(line) for line in args.dataset.read_text().splitlines() if line.strip()]
    if args.base_url:
        import httpx

        if not args.password:
            ap.error("--password or EVAL_PASSWORD is required with --base-url")
        http = httpx.Client(base_url=args.base_url, timeout=120)
        email, password = args.email, args.password
    else:
        http, password = in_process_http()
        email = EVAL_EMAIL
    client = login(http, email, password)
    needed = {f for d in dataset for f in d["document_fixture_ids"]}
    chunk_map = load_fixtures(client, args.fixtures_dir, needed)
    rag = run_rag(client, dataset, chunk_map, args.top_k)

    first = next((r for r in rag if r.get("provider")), {})
    ready = http.get("/ready").json() if args.base_url else {}
    config = {
        "chat_provider": first.get("provider") or ready.get("llm_provider") or os.getenv("LLM_PROVIDER"),
        "chat_model": first.get("model") or os.getenv("LLM_MODEL"),
        "embedding_provider": os.getenv("EMBEDDING_PROVIDER") or ready.get("embedding_provider"),
        "embedding_model": os.getenv("EMBEDDING_MODEL") or ready.get("embedding_model"),
        "embedding_dim": os.getenv("EMBEDDING_DIM"),
        "top_k": args.top_k,
    }
    if not args.base_url:
        from app.core.config import get_settings
        from app.services.llm.factory import get_chat_provider, get_embedding_provider

        s = get_settings()
        chat, emb = get_chat_provider(s), get_embedding_provider(s)
        config.update(chat_provider=chat.name, chat_model=chat.model, embedding_provider=emb.name,
                      embedding_model=emb.model, embedding_dim=emb.dimension)

    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_sha": git_sha(),
        "dataset": {"name": args.dataset.name, "items": len(dataset),
                    "by_scenario": {st: sum(d["scenario_type"] == st for d in dataset)
                                    for st in sorted({d["scenario_type"] for d in dataset})}},
        "config": config,
        "environment": f"{platform.system()} {platform.machine()}, Python {platform.python_version()}, "
                       f"{'in-process TestClient' if not args.base_url else args.base_url}",
        "metrics": {"rag": summarize(rag, dataset)},
        "results": {"rag": rag},
        "method": METHOD,
    }
    if args.baseline:
        if args.base_url:
            raise SystemExit("--baseline requires in-process mode")
        base = run_baseline(dataset)
        report["metrics"]["baseline"] = summarize(base, dataset)
        report["results"]["baseline"] = base
    report["gates_failed"] = gates(rag)

    stem = args.name or re.sub(r"[^A-Za-z0-9._-]+", "_", f"{args.dataset.stem}-{config['chat_provider']}-{config['chat_model']}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / f"{stem}.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.out_dir / f"{stem}.md").write_text(to_markdown(report))
    print(to_markdown(report))
    print(f"wrote {args.out_dir / stem}.json and .md")
    return 1 if report["gates_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

import json
import re
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.services.llm.anthropic import AnthropicChatProvider
from app.services.llm.base import (
    ChatMessage,
    ConfigError,
    ProviderAuthError,
    ProviderTimeout,
)
from app.services.llm.factory import get_embedding_provider
from app.services.llm.http import post_json
from app.services.llm.mock import MockChatProvider, MockEmbeddingProvider
from app.services.llm.ollama import OllamaChatProvider, OllamaEmbeddingProvider
from app.services.llm.openai import OpenAIChatProvider, OpenAIEmbeddingProvider
from app.services.llm.pricing import estimate_cost


def test_mock_embedding_is_deterministic_and_normalized():
    provider = MockEmbeddingProvider(256)
    result = provider.embed(["upstream connection refused"])
    assert result.vectors == provider.embed(["upstream connection refused"]).vectors
    assert len(result.vectors[0]) == 256
    assert sum(value * value for value in result.vectors[0]) == pytest.approx(1)


def test_mock_chat_selects_relevant_verbatim_sentences_and_skips_headings():
    provider = MockChatProvider()
    result = provider.chat(
        [
            ChatMessage("system", "TASK: grounded_qa"),
            ChatMessage(
                "user",
                '<chunk id="doc-1" source="runbook.md" page="1" flagged="false">\n'
                "# Upstream connection refused\n"
                "The upstream connection refused error means the service is not listening "
                "on port 3000.\n"
                "Check ss -ltnp | grep 3000 to confirm the expected port is open.\n"
                "</chunk>\n"
                '<chunk id="doc-2" source="other.md" page="1" flagged="false">\n'
                "# What does an upstream connection refused error mean?\n"
                "</chunk>\n"
                "<question>What does an upstream connection refused error mean and what "
                "should I check?</question>",
            ),
        ]
    )
    answer = json.loads(result.text)
    expected = [
        "The upstream connection refused error means the service is not listening on port 3000.",
        "Check ss -ltnp | grep 3000 to confirm the expected port is open.",
    ]

    assert answer["abstain"] is False
    assert answer["answer"] == "\n".join(expected)
    assert all("#" not in citation["quote"] for citation in answer["citations"])
    assert [item["quote"] for item in answer["citations"]] == expected


def test_mock_chat_keeps_selected_sentences_in_one_chunk():
    result = MockChatProvider().chat(
        [
            ChatMessage("system", "TASK: grounded_qa"),
            ChatMessage(
                "user",
                '<chunk id="current" source="current.md" page="1" flagged="false">\n'
                "# Current backup policy\n"
                "Production database backups are retained for 30 days.\n"
                "This retention period applies to all production database backups.\n"
                "</chunk>\n"
                '<chunk id="old" source="old.md" page="1" flagged="false">\n'
                "# Archived backup policy\n"
                "Production database backups are retained for 14 days.\n"
                "</chunk>\n"
                "<question>How many days are production database backups retained?</question>",
            ),
        ]
    )

    answer = json.loads(result.text)

    assert "14 days" not in answer["answer"]
    assert all(citation["chunk_id"] == "current" for citation in answer["citations"])


def test_mock_chat_avoids_explicitly_superseded_chunks_when_current_evidence_matches():
    result = MockChatProvider().chat(
        [
            ChatMessage("system", "TASK: grounded_qa"),
            ChatMessage(
                "user",
                '<chunk id="old" source="policy-v1.md" page="1" flagged="false">\n'
                "# Backup retention policy v1\n"
                "Status: superseded by version 2.\n"
                "Production database backups are retained for 14 days.\n"
                "</chunk>\n"
                '<chunk id="current" source="policy-v2.md" page="1" flagged="false">\n'
                "# Backup retention policy v2\n"
                "Production database backups are retained for 30 days.\n"
                "</chunk>\n"
                "<question>How many days are production database backups retained?</question>",
            ),
        ]
    )

    answer = json.loads(result.text)

    assert "30 days" in answer["answer"]
    assert "14 days" not in answer["answer"]
    assert all(citation["chunk_id"] == "current" for citation in answer["citations"])


def test_mock_analysis_groups_categories_and_caps_distinct_read_only_checks():
    provider = MockChatProvider()
    result = provider.chat(
        [
            ChatMessage("system", "TASK: incident_analysis"),
            ChatMessage(
                "user",
                '<observation id="obs-1" source="log" '
                'category="connection_refused, upstream_address">refused</observation>\n'
                '<observation id="obs-2" source="log" '
                'category="connection_refused">refused again</observation>\n'
                '<observation id="obs-3" source="log" '
                'category="service_inactive">inactive</observation>\n'
                '<observation id="obs-4" source="log" '
                'category="timeout">timed out</observation>',
            ),
        ]
    )
    analysis = json.loads(result.text)
    hypotheses = analysis["hypotheses"]
    commands = [step["command_or_check"] for step in analysis["verification_steps"]]

    assert len(hypotheses) == 3
    assert hypotheses[0]["title"] == "Upstream service not listening on proxy_pass port"
    assert hypotheses[0]["supporting_evidence"] == ["obs-1", "obs-2"]
    assert hypotheses[1]["supporting_evidence"] == ["obs-1"]
    assert hypotheses[2]["title"] == "Backend service process stopped or crashed"
    assert all(item["status"] == "suspected" for item in hypotheses)
    assert commands == [
        "ss -ltnp",
        "nginx -T",
        "systemctl status app-backend",
    ]
    assert len(commands) == len(set(commands))
    assert all(step["read_only"] for step in analysis["verification_steps"])


def test_mock_analysis_derives_checks_from_observed_upstream_address():
    result = MockChatProvider().chat(
        [
            ChatMessage("system", "TASK: incident_analysis"),
            ChatMessage(
                "user",
                '<observation id="obs-1" source="log" '
                'category="connection_refused">connect() failed for upstream: '
                '"http://127.0.0.1:8080/api"</observation>\n'
                '<observation id="obs-2" source="log" category="timeout">'
                'upstream timed out at upstream: "http://127.0.0.1:8080/api"'
                "</observation>\n"
                '<observation id="obs-3" source="log" category="http_5xx">'
                'upstream: "http://127.0.0.1:8080/api" returned 502'
                "</observation>",
            ),
        ]
    )

    analysis = json.loads(result.text)

    assert [step["command_or_check"] for step in analysis["verification_steps"]] == [
        "ss -ltnp 'sport = :8080'",
        "curl -sS http://127.0.0.1:8080/health",
        "curl -sS -I http://127.0.0.1:8080/health",
    ]


def test_mock_analysis_uses_port_agnostic_checks_without_upstream_address():
    result = MockChatProvider().chat(
        [
            ChatMessage("system", "TASK: incident_analysis"),
            ChatMessage(
                "user",
                '<observation id="obs-1" source="log" category="connection_refused">'
                "connect() failed (111: Connection refused)</observation>\n"
                '<observation id="obs-2" source="log" category="timeout">'
                "upstream timed out</observation>",
            ),
        ]
    )

    analysis = json.loads(result.text)
    commands = [step["command_or_check"] for step in analysis["verification_steps"]]

    assert commands == [
        "ss -ltnp",
        "Request the upstream's health endpoint shown in proxy_pass",
    ]
    assert all("3000" not in command for command in commands)


def test_openai_request_shapes_and_usage():
    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"answer":"ok"}'}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 2},
            },
        )

    settings = Settings(jwt_secret="x" * 32, llm_provider="openai", openai_api_key="secret")
    provider = OpenAIChatProvider(settings, httpx.Client(transport=httpx.MockTransport(handler)))
    result = provider.chat([ChatMessage("user", "hello")])
    assert (result.input_tokens, result.output_tokens) == (7, 2)


def test_openai_embedding_dimensions_and_batching():
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(
            200,
            json={
                "data": [{"embedding": [0.0] * 8} for _ in body["input"]],
                "usage": {"prompt_tokens": 4},
            },
        )

    settings = Settings(
        jwt_secret="x" * 32,
        llm_provider="mock",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        openai_api_key="secret",
        embedding_dim=8,
        embedding_batch_size=2,
    )
    result = OpenAIEmbeddingProvider(
        settings, httpx.Client(transport=httpx.MockTransport(handler))
    ).embed(["a", "b", "c"])
    assert [len(item["input"]) for item in seen] == [2, 1]
    assert all(item["dimensions"] == 8 for item in seen)
    assert len(result.vectors) == 3


def test_anthropic_request_headers_and_system():
    def handler(request):
        assert request.headers["anthropic-version"] == "2023-06-01"
        body = json.loads(request.content)
        assert "Respond with a single JSON object only." in body["system"]
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "{}"}],
                "usage": {"input_tokens": 8, "output_tokens": 1},
            },
        )

    settings = Settings(
        jwt_secret="x" * 32,
        llm_provider="anthropic",
        anthropic_api_key="secret",
        embedding_provider="mock",
    )
    result = AnthropicChatProvider(
        settings, httpx.Client(transport=httpx.MockTransport(handler))
    ).chat([ChatMessage("system", "policy"), ChatMessage("user", "question")])
    assert result.input_tokens == 8


def test_ollama_chat_and_embedding_shapes():
    def handler(request):
        body = json.loads(request.content)
        if request.url.path.endswith("/api/chat"):
            assert body["stream"] is False and body["format"] == "json"
            assert body["options"]["num_ctx"] == 8192  # the default 4096 truncates long prompts
            return httpx.Response(
                200,
                json={
                    "message": {"content": "{}"},
                    "prompt_eval_count": 5,
                    "eval_count": 2,
                },
            )
        assert body["input"] == ["one", "two"]
        return httpx.Response(200, json={"embeddings": [[0.1] * 8, [0.2] * 8]})

    transport = httpx.MockTransport(handler)
    settings = Settings(
        jwt_secret="x" * 32,
        llm_provider="ollama",
        ollama_base_url="http://localhost:11434",
        embedding_provider="ollama",
        embedding_model="custom",
        embedding_dim=8,
    )
    chat = OllamaChatProvider(settings, httpx.Client(transport=transport)).chat(
        [ChatMessage("user", "hello")]
    )
    vectors = OllamaEmbeddingProvider(settings, httpx.Client(transport=transport)).embed(
        ["one", "two"]
    )
    assert chat.input_tokens == 5
    assert len(vectors.vectors) == 2


def test_post_json_retries_rate_limit_and_maps_auth_timeout():
    calls = 0

    def retry_handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(429 if calls == 1 else 200, json={"ok": True})

    data, retries = post_json(
        httpx.Client(transport=httpx.MockTransport(retry_handler)),
        "https://example.test",
        {},
        {},
        1,
        1,
        sleep=lambda _: None,
    )
    assert data == {"ok": True} and retries == 1
    with pytest.raises(ProviderAuthError):
        post_json(
            httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(401))),
            "https://example.test",
            {},
            {},
            1,
            0,
        )
    with pytest.raises(ProviderTimeout):
        post_json(
            httpx.Client(
                transport=httpx.MockTransport(
                    lambda _: (_ for _ in ()).throw(httpx.ReadTimeout("timeout"))
                )
            ),
            "https://example.test",
            {},
            {},
            1,
            0,
        )


def test_pricing_override_and_unknown(tmp_path: Path, monkeypatch):
    assert estimate_cost("openai", "gpt-4o-mini", 1_000_000, 0) == 0.15
    assert estimate_cost("not-known", "x", 1, 1) is None
    pricing_file = tmp_path / "pricing.json"
    pricing_file.write_text(
        '[{"provider":"openai","model":"gpt-4o-mini","input_per_1m":1,"output_per_1m":2}]'
    )
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_pricing_file", str(pricing_file))
    assert estimate_cost("openai", "gpt-4o-mini", 1_000_000, 1_000_000) == 3


def test_anthropic_embeddings_rejected_and_key_required():
    with pytest.raises(ConfigError, match="Anthropic has no embeddings API"):
        get_embedding_provider(
            Settings(
                jwt_secret="x" * 32,
                llm_provider="mock",
                embedding_provider="anthropic",
                embedding_model="embed",
            )
        )
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        get_embedding_provider(
            Settings(
                jwt_secret="x" * 32,
                llm_provider="mock",
                embedding_provider="openai",
                embedding_model="text-embedding-3-small",
            )
        )


def test_anthropic_defaults_to_openai_embeddings_and_checks_known_dimensions():
    from app.services.llm.factory import get_chat_provider

    settings = Settings(
        jwt_secret="x" * 32,
        llm_provider="anthropic",
        embedding_provider="openai",
        anthropic_api_key="chat-key",
        openai_api_key="embed-key",
    )
    assert get_chat_provider(settings).name == "anthropic"
    assert get_embedding_provider(settings).name == "openai"
    with pytest.raises(ConfigError, match="dimension"):
        get_embedding_provider(
            Settings(
                jwt_secret="x" * 32,
                llm_provider="mock",
                embedding_provider="ollama",
                embedding_model="nomic-embed-text",
                embedding_dim=256,
            )
        )


def test_mock_chat_matches_non_ascii_words_in_the_document_language():
    provider = MockChatProvider()
    result = provider.chat(
        [
            ChatMessage("system", "TASK: grounded_qa"),
            ChatMessage(
                "user",
                '<chunk id="doc-1" source="wifi.md" page="1" flagged="false">\n'
                "Гостевые устройства подключаются к сети KANTOR-TAMU.\n"
                "</chunk>\n"
                "<question>Куда подключаются гостевые устройства?</question>",
            ),
        ]
    )
    answer = json.loads(result.text)

    assert answer["abstain"] is False
    assert answer["citations"][0]["quote"] == "Гостевые устройства подключаются к сети KANTOR-TAMU."


def test_mock_tokens_split_latin_from_other_scripts():
    from app.services.llm.mock import _TOKEN

    tokens = re.findall(_TOKEN, "vpnクライアントの最低バージョンは5.2")
    assert tokens == ["vpn", "クライアントの最低バージョンは", "5.2"]
    assert re.findall(_TOKEN, "für gäste: kantor-tamu") == ["für", "gäste:", "kantor-tamu"]

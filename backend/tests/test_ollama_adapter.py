"""The Ollama adapter is exercised against a fake Ollama HTTP server that speaks the real wire
format (/api/version, /api/tags, /api/show, /api/chat, /api/embed), so the request/response
handling is verified even on machines without Ollama."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from poly.providers.base import ChatMessage
from poly.providers.llm.ollama import OllamaProvider
from poly.providers.registry import classify_tasks


class FakeOllama(BaseHTTPRequestHandler):
    calls: list[tuple[str, dict]] = []

    def _json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/version":
            return self._json(200, {"version": "0.11.4"})
        if self.path == "/api/tags":
            return self._json(200, {"models": [
                {"name": "qwen2.5:14b", "size": 9_000_000_000, "details": {"family": "qwen2", "parameter_size": "14.8B", "quantization_level": "Q4_K_M"}},
                {"name": "llama3.2:3b", "size": 2_000_000_000, "details": {"family": "llama", "parameter_size": "3.2B"}},
                {"name": "nomic-embed-text:latest", "size": 274_000_000, "details": {"family": "nomic-bert", "parameter_size": "137M"}},
                {"name": "llava:7b", "size": 4_700_000_000, "details": {"family": "llama", "parameter_size": "7B"}},
            ]})
        self._json(404, {"error": "nope"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        FakeOllama.calls.append((self.path, body))
        if self.path == "/api/show":
            return self._json(200, {"model_info": {"qwen2.context_length": 32768}, "capabilities": ["completion", "tools"], "details": {"family": "qwen2"}})
        if self.path == "/api/chat":
            assert body["stream"] is False and body["messages"][-1]["role"] == "user"
            text = '{"ok": true}' if body.get("format") == "json" else "ready"
            return self._json(200, {"model": body["model"], "message": {"role": "assistant", "content": text}, "prompt_eval_count": 12, "eval_count": 3, "done": True})
        if self.path == "/api/embed":
            return self._json(200, {"model": body["model"], "embeddings": [[0.1] * 768 for _ in body["input"]]})
        self._json(404, {"error": "nope"})

    def log_message(self, *a):  # silence
        pass


@pytest.fixture(scope="module")
def fake_ollama():
    srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_ollama_discovery_and_classification(fake_ollama):
    p = OllamaProvider(fake_ollama)
    assert p.health() and p.version() == "0.11.4"
    models = {m.name: m for m in p.list_models()}
    assert set(models) == {"qwen2.5:14b", "llama3.2:3b", "nomic-embed-text:latest", "llava:7b"}
    assert p.show("qwen2.5:14b")["context_window"] == 32768
    assert classify_tasks(models["nomic-embed-text:latest"]) == ["EMBEDDING"]
    assert "FAST" in classify_tasks(models["llama3.2:3b"]) and "REASONING" not in classify_tasks(models["llama3.2:3b"])
    assert "REASONING" in classify_tasks(models["qwen2.5:14b"])
    assert "VISION" in classify_tasks(models["llava:7b"])


def test_ollama_chat_and_embed_wire_format(fake_ollama):
    p = OllamaProvider(fake_ollama)
    res = p.chat([ChatMessage("system", "s"), ChatMessage("user", "Reply ready")], model="llama3.2:3b", max_tokens=8)
    assert res.text == "ready" and res.prompt_tokens == 12 and res.provider == "ollama"
    path, body = FakeOllama.calls[-1]
    assert path == "/api/chat" and body["options"]["num_predict"] == 8
    res = p.chat([ChatMessage("user", "json please")], model="llama3.2:3b", json_mode=True)
    assert json.loads(res.text) == {"ok": True}
    assert FakeOllama.calls[-1][1]["format"] == "json"
    vecs = p.embed(["a", "b"], model="nomic-embed-text:latest")
    assert len(vecs) == 2 and len(vecs[0]) == 768


def test_registry_registers_fake_ollama_models(fake_ollama, db, monkeypatch):
    from poly.config import get_settings
    from poly.providers import registry

    monkeypatch.setattr(get_settings(), "ollama_url", fake_ollama)
    res = registry.detect_and_register(db)
    rt = next(r for r in res["runtimes"] if r["runtime"] == "ollama")
    assert rt["running"] and rt["model_count"] == 4
    a = res["assignments"]
    assert a["EMBEDDING"].endswith("nomic-embed-text:latest")
    assert a["FAST"].endswith("llama3.2:3b")
    assert a["REASONING"].endswith("qwen2.5:14b")
    assert a["VISION"].endswith("llava:7b")
    vecs, model = registry.Router(db).embed(["hello"])
    assert model == "nomic-embed-text:latest" and len(vecs[0]) == 768
    from poly.models import LocalModel

    for m in db.query(LocalModel).filter(LocalModel.runtime == "ollama").all():
        db.delete(m)
    db.commit()


def test_task_fallback_when_only_large_model(db):
    from poly.models import LocalModel
    from poly.providers.registry import candidates

    big = LocalModel(name="only-big:70b", runtime="ollama", endpoint="http://x", tasks=["REASONING", "WRITING"], priority=0, enabled=True, detected=True)
    db.add(big)
    db.commit()
    try:
        db.query(LocalModel).filter(LocalModel.runtime == "mock").update({"enabled": False})
        db.commit()
        assert [c.name for c in candidates(db, "FAST")] == ["only-big:70b"]
    finally:
        db.query(LocalModel).filter(LocalModel.runtime == "mock").update({"enabled": True})
        db.delete(big)
        db.commit()


def test_stopped_runtime_does_not_undetect_its_models(fake_ollama, db, monkeypatch):
    """A stopped Ollama must not flag its installed models as missing — that used to leave the
    router with nothing to route to even after the runtime came back."""
    from poly.config import get_settings
    from poly.models import LocalModel
    from poly.providers import registry

    monkeypatch.setattr(get_settings(), "ollama_url", fake_ollama)
    registry.detect_and_register(db)
    live = db.query(LocalModel).filter(LocalModel.runtime == "ollama").all()
    assert live and all(m.detected for m in live)

    # runtime goes away (nothing listening on this port)
    monkeypatch.setattr(get_settings(), "ollama_url", "http://127.0.0.1:1")
    registry.detect_and_register(db)
    after = db.query(LocalModel).filter(LocalModel.runtime == "ollama").all()
    assert all(m.detected for m in after), "models were wrongly marked missing while the runtime was down"

    # a model genuinely removed while the runtime IS up must still be flagged
    monkeypatch.setattr(get_settings(), "ollama_url", fake_ollama)
    ghost = LocalModel(name="removed-model:7b", runtime="ollama", endpoint=fake_ollama, tasks=["FAST"], enabled=True, detected=True)
    db.add(ghost)
    db.commit()
    registry.detect_and_register(db)
    db.refresh(ghost)
    assert ghost.detected is False
    for m in db.query(LocalModel).filter(LocalModel.runtime == "ollama").all():
        db.delete(m)
    db.commit()


def test_offline_hint_tells_the_owner_what_to_do(db, monkeypatch):
    from poly.config import get_settings
    from poly.providers import registry

    monkeypatch.setattr(get_settings(), "ollama_url", "http://127.0.0.1:1")
    monkeypatch.setattr(get_settings(), "openai_compat_urls", "")
    hint = registry.offline_hint(db)
    assert "Ollama isn't running" in hint and "ollama serve" in hint


def test_status_endpoint_reports_offline(client):
    r = client.get("/api/local-ai/status")
    assert r.status_code == 200
    body = r.json()
    assert "chat_ready" in body and "runtimes" in body
    assert body["any_runtime_running"] is False  # nothing listening in the test environment
    assert "Ollama" in body["hint"]

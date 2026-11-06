import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "infrastructure/scripts/n8n_test.py"


def _load():
    spec = importlib.util.spec_from_file_location("n8n_test_harness", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sh_defaults_to_repo_root():
    h = _load()
    out = h.sh(["pwd"])
    assert Path(out.stdout.strip()).resolve() == h.ROOT.resolve()


def test_sh_accepts_caller_cwd_without_duplicate_keyword():
    h = _load()
    out = h.sh(["pwd"], cwd=h.ROOT / "backend")  # used to raise TypeError: multiple values for keyword 'cwd'
    assert Path(out.stdout.strip()).resolve() == (h.ROOT / "backend").resolve()


def test_static_audit_rejects_double_equals_url():
    h = _load()
    bad = {"nodes": [{"name": "Call", "parameters": {"url": "=={{ $env.STUDIO_API_URL }}/api/x"}}]}
    good = {"nodes": [{"name": "Call", "parameters": {"url": "={{ $env.STUDIO_API_URL }}/api/x"}}, {"name": "NoUrl", "parameters": {}}]}
    assert h.url_problems(bad) and not h.url_problems(good)


def test_generated_workflows_have_valid_urls():
    import json
    h = _load()
    files = sorted((h.ROOT / "automation/workflows").glob("*.json"))
    assert len(files) == 13
    for f in files:
        assert not h.url_problems(json.loads(f.read_text())), f.name

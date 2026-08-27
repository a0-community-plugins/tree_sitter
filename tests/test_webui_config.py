from pathlib import Path


CONFIG_HTML = Path(__file__).parents[1] / "webui" / "config.html"


def test_settings_styles_live_outside_alpine_conditional_template():
    html = CONFIG_HTML.read_text(encoding="utf-8")

    assert html.rfind("</template>") < html.index("<style>")
    assert "ts-runtime-facts" in html
    assert "runtimeLoading" in html
    assert "runtimeError" in html


def test_settings_toggles_do_not_nest_labels():
    html = CONFIG_HTML.read_text(encoding="utf-8")

    assert '<label class="toggle">' not in html
    assert html.count('class="ts-switch-row') == 5
    assert "config.auto_context_enabled ? 'Automatic' : 'Manual'" in html
    assert 'x-model="config.auto_context_enabled"' in html
    assert 'aria-label="Allow paths outside the active project"' in html


def test_inspector_uses_a_single_result_dock_and_inline_runtime_states():
    html = (CONFIG_HTML.parent / "tree-sitter-inspector.html").read_text(encoding="utf-8")
    store = (CONFIG_HTML.parent / "tree-sitter-inspector-store.js").read_text(encoding="utf-8")

    assert "eyebrow" not in html
    assert "ci-result-tabs" in html
    assert "currentResult()" in store
    assert "lastError" in html
    assert "runtimeLoading" in html
    assert "!$store.treeSitterInspector.rootPath || !$store.treeSitterInspector.filePath" in html
    assert 'new Error("Enter a repository root and file path to inspect.")' in store
    assert "root_path: this.rootPath," in store

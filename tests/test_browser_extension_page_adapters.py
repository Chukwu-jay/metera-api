import json
import subprocess
from pathlib import Path


def _run_node_test(script: str) -> str:
    completed = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def test_page_adapter_detects_chatgpt_surface_and_prefers_prompt_textarea() -> None:
    adapter_path = (Path(__file__).resolve().parents[1] / "clients" / "browser-extension" / "page-adapters.js").as_posix()
    script = f"""
const adapters = require('{adapter_path}');
const fakeNodes = [
  {{
    tagName: 'DIV', id: '', hidden: false, isContentEditable: true,
    getAttribute: (name) => name === 'role' ? 'textbox' : null,
    closest: () => null,
    getBoundingClientRect: () => ({{ width: 400, height: 100 }})
  }},
  {{
    tagName: 'TEXTAREA', id: 'prompt-textarea', hidden: false, isContentEditable: false,
    getAttribute: (name) => name === 'placeholder' ? 'Message ChatGPT' : null,
    closest: () => ({{}}),
    getBoundingClientRect: () => ({{ width: 400, height: 80 }})
  }}
];
const documentLike = {{
  querySelectorAll(selector) {{
    if (selector === '#prompt-textarea') return [fakeNodes[1]];
    if (selector.includes('textbox')) return [fakeNodes[0]];
    if (selector === 'textarea') return [fakeNodes[1]];
    return [];
  }}
}};
const target = adapters.findPromptTarget(documentLike, {{ hostname: 'chatgpt.com' }});
console.log(JSON.stringify({{ surface: adapters.detectSurface({{ hostname: 'chatgpt.com' }}), id: target.id, tagName: target.tagName }}));
"""
    output = _run_node_test(script)
    body = json.loads(output)
    assert body == {"surface": "chatgpt", "id": "prompt-textarea", "tagName": "TEXTAREA"}


def test_page_adapter_detects_claude_surface() -> None:
    adapter_path = (Path(__file__).resolve().parents[1] / "clients" / "browser-extension" / "page-adapters.js").as_posix()
    script = f"""
const adapters = require('{adapter_path}');
console.log(adapters.detectSurface({{ hostname: 'claude.ai' }}));
"""
    output = _run_node_test(script)
    assert output == "claude"


def test_page_adapter_can_capture_latest_assistant_response() -> None:
    adapter_path = (Path(__file__).resolve().parents[1] / "clients" / "browser-extension" / "page-adapters.js").as_posix()
    script = f"""
const adapters = require('{adapter_path}');
const assistantA = {{
  innerText: 'First answer',
  textContent: 'First answer',
  hidden: false,
  getAttribute: () => null,
  getBoundingClientRect: () => ({{ width: 400, height: 80 }}),
}};
const assistantB = {{
  innerText: 'Second answer with the latest useful result',
  textContent: 'Second answer with the latest useful result',
  hidden: false,
  getAttribute: () => null,
  getBoundingClientRect: () => ({{ width: 400, height: 80 }}),
}};
const documentLike = {{
  querySelectorAll(selector) {{
    if (selector === 'article') return [assistantA, assistantB];
    return [];
  }}
}};
const result = adapters.captureLatestAssistantResponse(documentLike, {{ hostname: 'claude.ai' }});
console.log(JSON.stringify({{ ok: result.ok, text: result.text, mode: result.captureMode }}));
"""
    output = _run_node_test(script)
    body = json.loads(output)
    assert body == {"ok": True, "text": "Second answer with the latest useful result", "mode": "latest_assistant_response"}

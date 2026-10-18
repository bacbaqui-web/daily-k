"""Invoke the installed Codex CLI using ChatGPT subscription authentication only."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

DEFAULT_BINARY = '/home/ubuntu/daily-k-news/codex-cli/node_modules/.bin/codex'

def environment():
    env = dict(os.environ)
    for name in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL', 'CODEX_ACCESS_TOKEN'):
        env.pop(name, None)
    return env

def check_login():
    result = subprocess.run([os.environ.get('NEWS_CODEX_BIN', DEFAULT_BINARY), 'login', 'status'],
                            env=environment(), capture_output=True, text=True, timeout=30)
    if result.returncode or 'ChatGPT' not in result.stdout + result.stderr:
        raise ValueError('Codex must be logged in with ChatGPT subscription; API fallback is disabled')

def normalize_events(lines, final_text):
    output = []
    completed = False
    for line in lines.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('type') == 'turn.completed':
            completed = True
        if event.get('type') in ('turn.failed', 'error'):
            raise ValueError('Codex execution failed; inspect private run logs')
        if event.get('type') == 'item.completed':
            item = event.get('item', {})
            if item.get('type') in ('web_search', 'web_search_call'):
                output.append({'type': 'web_search_call', 'action': item.get('action', {}), 'status': 'completed'})
    if not completed or not final_text.strip():
        raise ValueError('Codex did not complete the requested output')
    output.append({'type': 'message', 'content': [{'type': 'output_text', 'text': final_text}]})
    return {'status': 'completed', 'output': output}

def run_codex(prompt, *, search=False):
    check_login()
    binary = os.environ.get('NEWS_CODEX_BIN', DEFAULT_BINARY)
    with tempfile.TemporaryDirectory(prefix='daily-k-codex-') as directory:
        result_path = Path(directory) / 'result.txt'
        command = [binary, '--no-daemon', '-a', 'never']
        if search:
            command.append('--search')
        command += ['exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
                    '--sandbox', 'read-only', '--disable', 'shell_tool', '--disable', 'multi_agent',
                    '--disable', 'apps', '-c', 'forced_login_method="chatgpt"',
                    '-c', 'web_search="live"' if search else 'web_search="disabled"',
                    '-C', directory, '--json', '--output-last-message', str(result_path), '-']
        # The CLI selects its account-supported default; never fall back to API billing.
        result = subprocess.run(command, input=prompt, env=environment(), text=True,
                                capture_output=True, timeout=1200)
        if result.returncode:
            raise ValueError(f'Codex exited {result.returncode}; no publication')
        response = normalize_events(result.stdout, result_path.read_text() if result_path.exists() else '')
        response['executionEvents'] = result.stdout
        return response

"""Audit the exact public file allowlist. Never print potential secret values."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
PUBLIC_FILES = {
    '.gitattributes', '.gitignore', '.env.example', '.github/workflows/tests.yml',
    'README.md', 'LICENSE', 'Abrir-estudio.cmd', 'config.py', 'studio.py', 'project.py',
    'voice_clone.py', 'download_model.py', 'prepare_reference.py', 'obs_control.py',
    'synthesize.ps1', 'audit_release.py', 'requirements.txt', 'requirements-obs.txt',
    'requirements-voice.txt', 'requirements-voice-tested.txt', 'web/index.html',
    'examples/plan.example.json', 'docs/seguranca.md', 'docs/transparencia.md',
    'docs/validacao.md', 'tests/test_studio.py',
}


def main():
    paths = PUBLIC_FILES
    if (ROOT / '.git').exists():
        tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT)
        candidates = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=ROOT)
        paths = {item for item in (tracked + candidates).decode().split('\0') if item}
    if paths != PUBLIC_FILES:
        raise ValueError('Public file allowlist mismatch; paths only: ' + ', '.join(sorted(paths ^ PUBLIC_FILES)))
    rules = [r'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----',
             r'postgres(?:ql)?://[^\s:/]+:[^\s@]+@',
             r'\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16})\b',
             r'[A-Za-z]:[\\/]Users[\\/][^\s]+',
             r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b']
    links = 0
    for name in sorted(paths):
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing or redirected public file: ' + name)
        text = path.read_text(encoding='utf-8')
        if any(re.search(rule, text) for rule in rules):
            raise ValueError('Secret/privacy pattern requires review; path only: ' + name)
        for match in re.finditer(r'''(?im)^\s*(?:password|api_key|api_secret|token)\s*=\s*['"]([^'"]+)['"]''', text):
            if match.group(1) not in {'test-only', 'placeholder'}:
                raise ValueError('Literal credential requires review; path only: ' + name)
        if path.suffix == '.json':
            json.loads(text)
        if path.suffix == '.md':
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
                if re.match(r'[a-z]+://', target):
                    continue
                target = target.split('#')[0]
                resolved = (path.parent / target).resolve()
                if not resolved.is_relative_to(ROOT) or not resolved.exists():
                    raise ValueError('Broken/escaping documentation link: ' + name)
                links += 1
    print(json.dumps({'status': 'PASS_LOCAL_PUBLIC_ALLOWLIST_AND_PATTERNS', 'files': len(paths),
                      'local_links': links, 'personal_media_included': False,
                      'model_weights_included': False,
                      'limit': 'Local allowlist/pattern audit; not a universal secret detector'}))


if __name__ == '__main__':
    main()

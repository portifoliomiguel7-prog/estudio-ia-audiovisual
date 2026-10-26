"""Import a video and create editable narration cues without changing the original."""
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from config import workspace, ffmpeg, safe_child


def duration(path):
    result = subprocess.run([ffmpeg(), '-hide_banner', '-i', str(path)], capture_output=True,
                            text=True, encoding='utf-8', errors='replace')
    match = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', result.stderr)
    if not match or 'Video:' not in result.stderr:
        raise ValueError('Não foi possível medir um vídeo neste arquivo.')
    hours, minutes, seconds = map(float, match.groups())
    value = hours * 3600 + minutes * 60 + seconds
    if not 0 < value <= 7200:
        raise ValueError('Use um vídeo com duração entre 0 e 7200 segundos.')
    return value


def add_video(source, title=None):
    source = Path(source).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in {'.mp4', '.mkv', '.mov'}:
        raise ValueError('Informe um vídeo MP4, MKV ou MOV existente.')
    seconds = duration(source)
    root = workspace()
    raw = root / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    (root / 'imports').mkdir(exist_ok=True)
    plan_path = root / 'plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8')) if plan_path.exists() else {
        'voice': 'Microsoft Maria Desktop', 'rate': 0, 'scenes': [],
        'note': 'Edite o texto de exemplo antes de gerar. Os arquivos originais são preservados.'}
    number = max((scene['scene'] for scene in plan['scenes']), default=0) + 1
    stem = re.sub(r'[^a-zA-Z0-9_-]+', '-', source.stem).strip('-') or 'video'
    name = f'{number:02d}-{stem}' + source.suffix.lower()
    destination = safe_child(raw, name)
    with destination.open('xb') as output, source.open('rb') as input_file:
        shutil.copyfileobj(input_file, output)
    plan['scenes'].append({'scene': number, 'title': title or source.stem, 'file': name,
                          'duration': seconds, 'cues': [{'start': min(1.0, seconds / 10),
                          'text': 'Edite esta fala para explicar o que aparece nesta cena.'}]})
    temporary = plan_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(plan_path)
    return {'scene': number, 'file': name, 'duration': seconds}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', required=True)
    parser.add_argument('--title')
    args = parser.parse_args()
    print(json.dumps(add_video(args.video, args.title), ensure_ascii=False))

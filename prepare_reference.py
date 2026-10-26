"""Prepare only a local, explicitly authorized voice reference. No uploads."""
import argparse
import hashlib
import json
import math
import subprocess
import wave
from pathlib import Path
from config import workspace, ffmpeg


def prepare(audio, start, seconds, consent):
    if not consent:
        raise ValueError('Confirme que a voz é sua ou que possui autorização com --consent.')
    if not math.isfinite(start) or not math.isfinite(seconds) or start < 0 or not 3 <= seconds <= 30:
        raise ValueError('Use início não negativo e referência de 3 a 30 segundos.')
    source = Path(audio).expanduser().resolve()
    if not source.is_file():
        raise ValueError('Áudio de referência ausente.')
    clone = workspace() / 'voice-clone'
    private = clone / 'private'
    private.mkdir(parents=True, exist_ok=True)
    reference = private / 'reference-12s.wav'
    if reference.exists():
        raise ValueError('Referência existente preservada. Use outra pasta STUDIO_WORKSPACE para outra voz.')
    subprocess.run([ffmpeg(), '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
                    '-ss', str(start), '-i', str(source), '-t', str(seconds), '-ar', '24000',
                    '-ac', '1', '-c:a', 'pcm_s16le', str(reference)], check=True)
    with wave.open(str(reference), 'rb') as wav:
        actual_seconds = wav.getnframes() / wav.getframerate()
    if actual_seconds < 3:
        raise ValueError('O trecho resultante tem menos de 3 segundos; revise a seleção em outra pasta de trabalho.')
    info = {'voice_owner_authorized_by_operator': True, 'uploaded': False,
            'reference_sha256': hashlib.sha256(reference.read_bytes()).hexdigest(),
            'duration_seconds': actual_seconds,
            'status': 'REFERENCE_PREPARED_REQUIRES_LISTENING_REVIEW'}
    (clone / 'ready.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    return info


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', required=True)
    parser.add_argument('--start', type=float, default=0)
    parser.add_argument('--seconds', type=float, default=12)
    parser.add_argument('--consent', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.audio, args.start, args.seconds, args.consent)))

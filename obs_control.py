"""Local OBS WebSocket 5 control. Password is entered privately, never saved."""
import argparse
import base64
import getpass
import json
import logging
from pathlib import Path
import shutil
import time
import uuid
import sys
from config import workspace, ffmpeg
import subprocess


def request(client, kind, data=None):
    return client.send(kind, data=data, raw=True)


def preflight(client):
    version = request(client, 'GetVersion')
    scene = request(client, 'GetCurrentProgramScene')['currentProgramSceneName']
    return {'version': version['obsVersion'], 'scene': scene,
            'scenes': request(client, 'GetSceneList')['scenes'],
            'record': request(client, 'GetRecordStatus'),
            'video': request(client, 'GetVideoSettings'),
            'items': request(client, 'GetSceneItemList', {'sceneName': scene})['sceneItems']}


def preview(client):
    scene = request(client, 'GetCurrentProgramScene')['currentProgramSceneName']
    image = request(client, 'GetSourceScreenshot', {'sourceName': scene, 'imageFormat': 'png',
                    'imageWidth': 1280, 'imageHeight': 720})['imageData']
    prefix = 'data:image/png;base64,'
    if not image.startswith(prefix):
        raise ValueError('OBS não retornou uma prévia PNG.')
    directory = workspace() / 'obs'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ('preview-' + uuid.uuid4().hex + '.png')
    with target.open('xb') as output:
        output.write(base64.b64decode(image[len(prefix):], validate=True))
    return target


def record(client, seconds, preview_reviewed=False, audio_reviewed=False):
    if not preview_reviewed or not audio_reviewed:
        raise ValueError('Revise a prévia e o mixer antes de usar --preview-reviewed --audio-reviewed.')
    if not 3 <= seconds <= 600:
        raise ValueError('Use uma duração entre 3 e 600 segundos.')
    if request(client, 'GetRecordStatus')['outputActive']:
        raise ValueError('Gravação existente preservada; não foi enviada nenhuma alteração.')
    request(client, 'StartRecord')
    stopped = None
    try:
        time.sleep(seconds)
    finally:
        # Only stop the recording started by this invocation, never a pre-existing one.
        if request(client, 'GetRecordStatus')['outputActive']:
            stopped = request(client, 'StopRecord')
    if stopped is None:
        raise ValueError('A gravação foi interrompida externamente; confira o arquivo no OBS.')
    source = Path(stopped['outputPath'])
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError('OBS não retornou um arquivo local existente e não vazio.')
    subprocess.run([ffmpeg(), '-hide_banner', '-nostdin', '-v', 'error', '-xerror',
                    '-i', str(source), '-f', 'null', '-'], check=True, capture_output=True)
    directory = workspace() / 'obs'
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / ('recording-' + uuid.uuid4().hex + source.suffix)
    with destination.open('xb') as output, source.open('rb') as input_file:
        shutil.copyfileobj(input_file, output)
    return {'file': str(destination), 'original_preserved': True, 'decode': 'PASS'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'preview', 'record'])
    parser.add_argument('--port', type=int, default=4455)
    parser.add_argument('--seconds', type=int, default=20)
    parser.add_argument('--preview-reviewed', action='store_true')
    parser.add_argument('--audio-reviewed', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Porta inválida.')
    try:
        import obsws_python
    except ImportError:
        parser.exit(1, 'Instale primeiro: python -m pip install -r requirements-obs.txt\n')
    # SDK DEBUG logging may contain authentication traffic. Do not enable it.
    logging.disable(logging.CRITICAL)
    if not sys.stdin.isatty():
        parser.exit(1, 'Use um terminal interativo para digitar a senha de forma privada.\n')
    password = getpass.getpass('Senha WebSocket OBS (entrada privada): ')
    if not password:
        parser.exit(1, 'A senha é obrigatória; mantenha a autenticação habilitada no OBS.\n')
    try:
        client = obsws_python.ReqClient(host='127.0.0.1', port=args.port, password=password, timeout=5)
    except Exception:
        parser.exit(1, 'Falha de conexão/autenticação local. Confira o OBS; a senha não foi registrada.\n')
    finally:
        password = None
    try:
        if args.action == 'status':
            result = preflight(client)
        elif args.action == 'preview':
            result = {'preview': str(preview(client)), 'review_required': True}
        else:
            result = record(client, args.seconds, args.preview_reviewed, args.audio_reviewed)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        client.disconnect()


if __name__ == '__main__':
    main()

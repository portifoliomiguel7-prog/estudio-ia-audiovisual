"""Portable paths. Runtime and voice data live outside the public source tree."""
import os
from pathlib import Path, PureWindowsPath
import shutil

CODE = Path(__file__).resolve().parent


def workspace():
    path = Path(os.environ.get('STUDIO_WORKSPACE', CODE / '.local/studio')).expanduser().resolve()
    if path == CODE:
        raise ValueError('Use uma pasta de trabalho separada do código, por exemplo .local/studio.')
    return path


def safe_child(root, name):
    root = Path(root)
    value = str(name)
    relative = Path(value)
    if not value or relative.is_absolute() or PureWindowsPath(value).drive or '\\' in value:
        raise ValueError('Caminho relativo inválido.')
    if '..' in relative.parts:
        raise ValueError('Caminho fora da pasta autorizada.')
    current = root
    if current.is_symlink():
        raise ValueError('Links simbólicos não são permitidos.')
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Links simbólicos não são permitidos.')
    resolved = current.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError('Caminho fora da pasta autorizada.')
    return resolved


def ffmpeg():
    configured = os.environ.get('FFMPEG_BINARY')
    if configured:
        path = Path(configured).expanduser().resolve()
        if not path.is_file():
            raise ValueError('FFMPEG_BINARY não aponta para um arquivo.')
        return str(path)
    installed = shutil.which('ffmpeg')
    if installed:
        return installed
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except ImportError as exc:
        raise RuntimeError('Instale requirements.txt ou configure FFMPEG_BINARY.') from exc

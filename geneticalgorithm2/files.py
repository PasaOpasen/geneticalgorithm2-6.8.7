

from pathlib import Path

from .aliases import PathLike


def _mkdir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def mkdir_of_file(file_path: PathLike):
    """
    для этого файла создаёт папку, в которой он должен лежать
    """
    _mkdir(Path(file_path).parent)


def mkdir(path: PathLike):
    """mkdir with parents"""
    _mkdir(Path(path))


def touch(path: PathLike):
    """makes empty file, makes directories for this file automatically"""
    mkdir_of_file(path)
    Path(path).touch()

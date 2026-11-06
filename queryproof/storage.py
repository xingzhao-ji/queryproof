"""Small bounded inputs and immutable artifact publication."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

CACHE = Path.home() / ".cache/job-apps-runtime/queryproof"


def guard():
    if shutil.disk_usage(Path.home()).free < 2 * 1024**3:
        raise ValueError("host free disk below 2 GiB floor")
    used = 0
    seen = set()
    if CACHE.exists():
        for path in CACHE.rglob("*"):
            s = path.lstat()
            key = (s.st_dev, s.st_ino)
            if key not in seen:
                seen.add(key)
                used += s.st_blocks * 512
    if used >= 200 * 1024**2:
        raise ValueError("QueryProof cache reached 200 MiB allocated budget")


def read_bytes(path, limit=1048576):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("input must be a bounded regular file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("input grew beyond byte limit")
        return data
    finally:
        os.close(fd)


def parse_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("non-finite JSON number")

    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ValueError("invalid bounded JSON") from error


def read_json(path, limit=1048576):
    return parse_json(read_bytes(path, limit))


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, indent=2)
        + "\n"
    ).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    return sha(read_bytes(path, 4 * 1024 * 1024))


def publish(path, data):
    """Durable link publication never replaces an existing artifact."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".pending-", dir=path.parent, delete=False
        ) as stream:
            name = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if name:
            name.unlink(missing_ok=True)


def publish_json(path, value):
    publish(path, encoded(value))

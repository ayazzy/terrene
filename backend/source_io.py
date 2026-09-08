"""Bounded source IO and content-addressed artifacts for the England adapters."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import httpx


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def artifact(directory, content, suffix):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    digest = sha256(content).hexdigest()
    path = directory / (digest + suffix)
    if not path.exists():
        path.write_bytes(content)
    elif sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('Immutable source artifact has changed')
    return {'path': str(path.resolve()), 'sha256': digest}


def fetch_bytes(url, params=None, max_bytes=128*1024*1024, timeout=60):
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        with client.stream('GET', url, params=params) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError('Source response exceeds bounded download limit')
                chunks.append(chunk)
            return b''.join(chunks), {'url': str(response.url), 'retrieved_at': utcnow(),
                                     'etag': response.headers.get('etag'),
                                     'last_modified': response.headers.get('last-modified')}


def read_cache(path, refresh=False):
    path = Path(path)
    if not refresh and path.is_file():
        value = json.loads(path.read_text())
        if value.get('status') == 'available':
            # Cache data is only a reuse hint; its raw evidence must still exist.
            for raw in value.get('artifacts', []):
                p = Path(raw['path'])
                if not p.is_file() or sha256(p.read_bytes()).hexdigest() != raw['sha256']:
                    raise ValueError('Cached source artifact is missing or changed')
            return value
    return None


def save_cache(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, allow_nan=False, sort_keys=True)
    # Unique temporary files avoid readers seeing an incomplete concurrent write.
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as f:
        f.write(content)
        temporary = f.name
    os.replace(temporary, path)
    return value

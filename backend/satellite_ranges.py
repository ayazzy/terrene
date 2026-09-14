"""Budgeted, ETag-pinned HTTP ranges for GDAL's Python file opener; no GDAL network IO."""
import io
import re
import time

import httpx

from backend.acquisition_contracts import AcquisitionError, BinaryArtifact, digest


class RangeSource:
    def __init__(self, reader, asset, key, artifacts, limits):
        self.reader, self.asset, self.key = reader, asset, key
        self.artifacts, self.limits = artifacts, limits
        self.size = asset['file:size']
        self.record = {'href':asset['href'],'size':self.size,'etag':None,'ranges':[]}
        self.cache = []
        self.error = None

    def open(self, path, mode='rb'):
        # GDAL probes a synthetic test file and sidecars: never map them to a remote URL.
        if path != self.key+'.tif' or mode not in ('r','rb'):
            raise FileNotFoundError(path)
        return RangeFile(self)

    def get(self, start, end):
        try:
            for left,right,data in self.cache:
                if left <= start and right >= end:
                    return data[start-left:end-left]
            if not 0 <= start < end <= self.size:
                raise AcquisitionError('invalid_satellite_range')
            reader = self.reader
            remaining = reader.deadline-time.monotonic()
            if remaining <= 0:
                raise AcquisitionError('network_deadline')
            if (end-start > self.limits['max_response_bytes']
                    or sum('range' in response for response in reader.responses) >= self.limits['max_range_requests']):
                raise AcquisitionError('satellite_range_limit')
            headers = {'Range':f'bytes={start}-{end-1}','Accept-Encoding':'identity'}
            if self.record['etag']:
                headers['If-Match'] = self.record['etag']
            with reader.client.stream('GET',self.asset['href'],headers=headers,
                                      timeout=min(remaining,reader.request_timeout),follow_redirects=False) as response:
                if response.status_code == 412:
                    raise AcquisitionError('source_changed_during_capture')
                if response.status_code != 206:
                    raise AcquisitionError('satellite_range_not_honoured')
                etag = response.headers.get('etag','')
                if (response.headers.get('content-range') != f'bytes {start}-{end-1}/{self.size}'
                        or response.headers.get('content-encoding','identity') != 'identity'
                        or not re.fullmatch(r'"[A-Za-z0-9-]+"',etag)):
                    raise AcquisitionError('satellite_range_identity_invalid')
                if self.record['etag'] and self.record['etag'] != etag:
                    raise AcquisitionError('source_changed_during_capture')
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk); reader.bytes_received += len(chunk)
                    if size > end-start or reader.bytes_received > reader.max_total:
                        raise AcquisitionError('byte_limit')
                    if time.monotonic() > reader.deadline:
                        raise AcquisitionError('network_deadline')
                    chunks.append(chunk)
                data = b''.join(chunks)
                if len(data) != end-start:
                    raise AcquisitionError('satellite_range_truncated')
            self.record['etag'] = etag
            name = f'source_{self.key}_range_{len(self.record["ranges"]):04d}'
            self.artifacts[name] = BinaryArtifact(data,'application/octet-stream')
            entry = {'start':start,'end_exclusive':end,'artifact':name,'sha256':digest(data)}
            self.record['ranges'].append(entry)
            reader.responses.append({'endpoint':self.asset['href'],'range':[start,end],
                                     'etag':etag,'decoded_response_sha256':digest(data),'decoded_bytes':len(data)})
            self.cache.append((start,end,data))
            return data
        except Exception as exc:
            error = AcquisitionError('network_failure') if isinstance(exc,httpx.HTTPError) else exc
            self.error = error
            raise error


class RangeFile(io.RawIOBase):
    def __init__(self, source):
        super().__init__()
        self.source, self.position = source, 0

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.position

    def seek(self, offset, whence=0):
        position = offset + (0 if whence == 0 else self.position if whence == 1 else self.source.size if whence == 2 else -1)
        if position < 0 or whence not in (0,1,2):
            raise ValueError('invalid seek')
        self.position = position
        return position

    def read(self, size=-1):
        end = self.source.size if size < 0 else min(self.source.size,self.position+size)
        if end <= self.position:
            return b''
        if self.source.error:
            return b''
        try:
            data = self.source.get(self.position,end)
        except AcquisitionError as exc:
            # Do not leak a pending Python exception through GDAL's C callbacks.
            # The caller checks this sticky error before accepting any result.
            self.source.error = exc
            return b''
        self.position = end
        return data


class ReplaySource:
    """Read only captured source ranges; any uncaptured byte fails explicitly."""
    def __init__(self, record, artifacts, key):
        self.size, self.record, self.artifacts, self.key = record['size'], record, artifacts, key
        self.error = None

    def open(self, path, mode='rb'):
        if path != self.key+'.tif' or mode not in ('r','rb'):
            raise FileNotFoundError(path)
        return RangeFile(self)

    def get(self, start, end):
        pieces, position = [], start
        for entry in sorted(self.record['ranges'],key=lambda r:r['start']):
            if entry['start'] <= position < entry['end_exclusive']:
                data = self.artifacts[entry['artifact']]
                if not isinstance(data,bytes) or digest(data) != entry['sha256']:
                    raise AcquisitionError('integrity_failure')
                stop = min(end,entry['end_exclusive'])
                pieces.append(data[position-entry['start']:stop-entry['start']]);position = stop
            if position == end:
                return b''.join(pieces)
        raise AcquisitionError('uncaptured_source_range')

# Stage-two bootstrap for rwmem.remote deploy mode.
#
# This file is not imported. Its source is sent verbatim over the agent's
# stdin and exec'd by the one-line stage-one bootstrap that
# rwmem.remote.RemoteConnection passes to ``python3 -c``. It then reads a
# length-prefixed zip of the modules the agent needs from the same stdin,
# serves them straight from that in-memory zip through a meta path finder,
# and starts the agent. Nothing is written to the device's filesystem.

import io
import linecache
import sys
import zipfile
from importlib.abc import Loader, MetaPathFinder
from importlib.util import spec_from_loader

_stdin = sys.stdin.buffer
_zip = zipfile.ZipFile(io.BytesIO(_stdin.read(int(_stdin.readline()))))
_names = set(_zip.namelist())


class MemFinder(MetaPathFinder, Loader):
    def find_spec(self, name, path=None, target=None):
        base = name.replace('.', '/')
        for fn, is_pkg in ((base + '/__init__.py', True), (base + '.py', False)):
            if fn in _names:
                return spec_from_loader(name, self, origin='mem:' + fn, is_package=is_pkg)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        spec = module.__spec__
        assert spec is not None and spec.origin is not None
        fn = spec.origin
        src = _zip.read(fn[len('mem:') :]).decode()
        linecache.cache[fn] = (len(src), None, src.splitlines(True), fn)
        exec(compile(src, fn, 'exec'), module.__dict__)  # noqa: S102


sys.meta_path.insert(0, MemFinder())

import rwmem.agent  # noqa: E402

rwmem.agent.main()

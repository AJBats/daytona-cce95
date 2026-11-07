"""Runs a build step, or writes back what it wrote last time when nothing it
read has changed since.

usage: cached.py TOOL.py [ARGS...]

The step runs in this process with an audit hook on every file it opens in
the repository (not .venv): a file it reads before writing it is an input,
hashed as it is first opened; a file it writes is an output. The step's
record, in build/cache/<tool>-<hash of its arguments>.json, holds those
hashes, the hashes of the repository's Python modules it ran (the tool and
what it imports), the names it listed in a PATCHED.txt, its printout, and
its outputs' hashes, their contents in build/cache/blobs. Next time, if the
modules and every input hash the same, the outputs are written back, the
names listed again (as the steps list them, merged and sorted) and the
printout repeated; otherwise the step runs again and its record is replaced.

The step's last argument is its output folder (build/cce_files, or a test
disc's): paths in it are kept as <out>/..., and the record's key names it
<out>, so the same step for another folder finds the same record.

For the art steps, which take minutes and whose inputs (DUSA's and CCE's
files, the liveries, the tools themselves) rarely change.
"""
import hashlib
import io
import json
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV = os.path.join(ROOT, '.venv') + os.sep
CACHE = os.path.join(ROOT, 'build', 'cache')
BLOBS = os.path.join(CACHE, 'blobs')
LISTING = 'PATCHED.txt'
WRITES = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC


def file_hash(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


OUT = [None]        # the step's output folder


def rel(path):
    path = os.path.abspath(path)
    if OUT[0] and (path == OUT[0] or path.startswith(OUT[0] + os.sep)):
        return ('<out>/' + os.path.relpath(path, OUT[0]).replace(os.sep, '/')).rstrip('/.')
    return os.path.relpath(path, ROOT).replace(os.sep, '/')


def full(name):
    if name == '<out>' or name.startswith('<out>/'):
        return os.path.join(OUT[0], *name.split('/')[1:])
    return os.path.join(ROOT, *name.split('/'))


def in_repo(path):
    return path.startswith(ROOT + os.sep) and not path.startswith(VENV)


class Tee(io.TextIOBase):
    def __init__(self, out):
        self.out, self.kept = out, io.StringIO()

    def write(self, text):
        self.kept.write(text)
        return self.out.write(text)

    def flush(self):
        self.out.flush()


def listed(folder, names):
    """Adds names to folder's PATCHED.txt, as the steps do."""
    path = os.path.join(folder, LISTING)
    have = open(path).read().split() if os.path.exists(path) else []
    have += [n for n in names if n not in have]
    open(path, 'w').write(''.join(n + '\n' for n in sorted(have)))


def up_to_date(record):
    for group in ('modules', 'inputs'):
        for name, digest in record[group].items():
            path = full(name)
            if (file_hash(path) if os.path.isfile(path) else None) != digest:
                return False
    return all(os.path.isfile(os.path.join(BLOBS, d)) for d in record['outputs'].values())


def write_back(record):
    for name, digest in record['outputs'].items():
        path = full(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(os.path.join(BLOBS, digest), 'rb') as f:
            data = f.read()
        with open(path, 'wb') as f:
            f.write(data)
    for folder, names in record['listed'].items():
        listed(full(folder), names)
    sys.stdout.write(record['printout'])


def run(tool, args):
    inputs, outputs, listings = {}, set(), set()
    state = {'on': False}

    def hook(event, hook_args):
        if event != 'open' or not state['on']:
            return
        path, mode, flags = hook_args
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        path = os.path.abspath(os.fsdecode(path))
        if not in_repo(path) or path.endswith(('.py', '.pyc')):
            return
        if os.path.basename(path) == LISTING:
            listings.add(os.path.dirname(path))
            return
        if (any(c in mode for c in 'wax+') if mode else (flags or 0) & WRITES):
            outputs.add(path)
        elif path not in outputs and path not in inputs:
            state['on'] = False
            try:
                inputs[path] = file_hash(path) if os.path.isfile(path) else None
            finally:
                state['on'] = True

    sys.addaudithook(hook)
    tee = Tee(sys.stdout)
    sys.stdout, sys.argv = tee, [tool] + args
    sys.path.insert(0, os.path.dirname(tool))
    state['on'] = True
    try:
        runpy.run_path(tool, run_name='__main__')
    except SystemExit as e:
        if e.code not in (None, 0):
            raise
    finally:
        state['on'] = False
        sys.stdout = tee.out

    modules = {rel(tool): file_hash(tool)}
    for module in list(sys.modules.values()):
        path = getattr(module, '__file__', None)
        if path and path.endswith('.py') and in_repo(os.path.abspath(path)):
            modules[rel(os.path.abspath(path))] = file_hash(path)
    os.makedirs(BLOBS, exist_ok=True)
    saved = {}
    for path in sorted(outputs):
        digest = file_hash(path)
        blob = os.path.join(BLOBS, digest)
        if not os.path.exists(blob):
            with open(path, 'rb') as f, open(blob, 'wb') as g:
                g.write(f.read())
        saved[rel(path)] = digest
    names = {}
    for folder in listings:
        have = set(open(os.path.join(folder, LISTING)).read().split())
        mine = [os.path.relpath(p, folder).replace(os.sep, '/') for p in outputs
                if p.startswith(folder + os.sep)]
        names[rel(folder)] = sorted(n for n in mine if n in have)
    return {'modules': modules, 'inputs': {rel(p): d for p, d in sorted(inputs.items())},
            'outputs': saved, 'listed': names, 'printout': tee.kept.getvalue()}


def main():
    tool, args = os.path.abspath(sys.argv[1]), sys.argv[2:]
    OUT[0] = os.path.abspath(args[-1])
    key = hashlib.sha1(json.dumps([rel(tool)] + [rel(a) if os.path.exists(a) or a == args[-1] else a
                                                 for a in args]).encode()).hexdigest()[:16]
    record_path = os.path.join(CACHE, f'{os.path.splitext(os.path.basename(tool))[0]}-{key}.json')
    if os.path.exists(record_path):
        with open(record_path) as f:
            record = json.load(f)
        if up_to_date(record):
            write_back(record)
            print(f'({rel(tool)}: nothing it reads has changed, its {len(record["outputs"])} files '
                  'written back from build/cache)')
            return
    record = run(tool, args)
    os.makedirs(CACHE, exist_ok=True)
    with open(record_path, 'w') as f:
        json.dump(record, f, indent=1)


if __name__ == '__main__':
    main()

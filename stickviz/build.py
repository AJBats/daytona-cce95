"""Build Stick Lab's program (stickviz/): compile and link it with tools/sh-gcc
(SH-2 GCC 14.2, gitignored, copied in per machine) into <out dir>/0MAIN.BIN,
the file the BIOS loads at 0x06004000 (stickviz/saturn.ld). make stickviz
then puts it on a disc of its own (tools/mkiso.py).

usage: build.py <out dir>
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GCC = os.path.join(HERE, '..', 'tools', 'sh-gcc', 'bin')
SOURCES = ['crt0.s', 'platform.cpp', 'font.cpp', 'main.cpp']
FLAGS = ['-m2', '-mb', '-O2', '-Wall', '-Wextra', '-ffunction-sections']
CXX_FLAGS = ['-fno-rtti', '-fno-exceptions', '-fno-threadsafe-statics', '-fno-use-cxa-atexit',
             '-fno-asynchronous-unwind-tables']


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    # cc1 and the linker load their DLLs from the compiler's bin directory
    env = dict(os.environ, PATH=os.path.abspath(GCC) + os.pathsep + os.environ['PATH'])
    tool = lambda name: os.path.join(GCC, 'sh2eb-elf-' + name)
    run = lambda *cmd: subprocess.run(cmd, env=env, check=True)

    objects = []
    for src in SOURCES:
        obj = os.path.join(out, src + '.o')
        if src.endswith('.s'):
            run(tool('gcc'), *FLAGS, '-c', os.path.join(HERE, src), '-o', obj)
        else:
            run(tool('g++'), *FLAGS, *CXX_FLAGS, '-c', os.path.join(HERE, src), '-o', obj)
        objects.append(obj)

    elf = os.path.join(out, '0MAIN.elf')
    run(tool('g++'), *FLAGS, '-nostdlib', '-T', os.path.join(HERE, 'saturn.ld'), '-Wl,--no-warn-rwx-segments',
        '-Wl,-Map=' + os.path.join(out, '0MAIN.map'), '-o', elf, *objects, '-lc', '-lgcc')
    binary = os.path.join(out, '0MAIN.BIN')
    run(tool('objcopy'), '-O', 'binary', elf, binary)
    print(f'stickviz: 0MAIN.BIN {os.path.getsize(binary)} bytes')


if __name__ == '__main__':
    main()



import argparse
from itertools import chain
import os
import os.path
from pathlib import Path
import subprocess
import sys
import random
from typing import *

from elftools.elf.elffile import ELFFile
from multiprocessing.dummy import Pool as ThreadPool, Lock
import multiprocessing

import colorama
from termcolor import colored

from sources import SOURCES


colorama.init()
print_mutex = Lock()


def __native_binary(path):
    if sys.platform == "win32" or sys.platform == "msys":
        return path + ".exe"
    return path


VERBOSE = False

DEVKITPPC = os.environ.get("DEVKITPPC")
if DEVKITPPC is None:
    # devkitPPC not specified in env.
    # Default to ./tools/devkitppc
    DEVKITPPC = Path().joinpath("tools", "devkitppc")
    if not os.path.isdir(DEVKITPPC):
        print(
            f'Could not find devkitPPC under "{DEVKITPPC}" and $DEVKITPPC var is not set.',
            file=sys.stderr,
        )
        sys.exit(1)


MWLD = os.path.join("tools", "mwldeppc.exe")

CWCC_PATHS = {
    "default": os.path.join(".", "tools", "4199_60831", "mwcceppc.exe"),
    # For the main game
    # August 17, 2007
    # 4.2.0.1 Build 127
    #
    # Ideally we would use this version
    # We don't have this, so we use build 142:
    # This version has the infuriating bug where random
    # nops are inserted into your code.
    "4201_127": os.path.join(".", "tools", "4201_142", "mwcceppc.exe"),
    # The script doesn't automatically make this backup, because Windows may block attempts to run an
    # executable file created from python's process without UAC override (WinError 740).
    "4201_127_unpatched": os.path.join(".", "tools", "4201_142", "mwcceppc_unpatched.exe"),

    # For most of RVL
    # We actually have the correct version
    "4199_60831": os.path.join(".", "tools", "4199_60831", "mwcceppc.exe"),
    # For HBM/WPAD, NHTTP/SSL
    # We use build 60831
    "4199_60726": os.path.join(".", "tools", "4199_60831", "mwcceppc.exe"),
}


def patch_compilers():
    with open(CWCC_PATHS["4201_127"], "rb") as og:
        ogbytes = bytearray(og.read())

    patches = [
        # Fix PS scheduling (mark instructions following a PS operation as data-dependencies in gekko mode)
        # Found by stebler.
        #
        {
            "at": 0x1A8540,
            "before": bytes([0x66, 0x83, 0x3D, 0x40, 0xF3]),
            "after": bytes([0xE9, 0x8B, 0x0D, 0x00, 0x00]),
        }
    ]

    for patch in patches:
        assert len(patch["before"]) == len(patch["after"])
        patch_size = len(patch["before"])

        before = ogbytes[patch["at"] : patch["at"] + patch_size]
        assert before == patch["after"] or before == patch["before"]
        ogbytes[patch["at"] : patch["at"] + patch_size] = patch["after"]

    with open(CWCC_PATHS["4201_127"], "wb") as new:
        new.write(ogbytes)


patch_compilers()

CW_ARGS = [
    "-nodefaults",
    "-align powerpc",
    "-enc SJIS",
    "-c",
    # "-I-",
    "-gccinc",
    "-i ./source/ -i ./source/platform",
    # "-inline deferred",
    "-proc gekko",
    "-enum int",
    "-O4,p",
    "-inline auto",
    "-W all",
    "-fp hardware",
    "-Cpp_exceptions off",
    "-RTTI on",
    #'-pragma "cats off"',  # ???
    # "-pragma \"aggressive_inline on\"",
    # "-pragma \"auto_inline on\"",
    "-inline off",
    "-w notinlined -W noimplicitconv -w nounwanted",
    "-nostdinc",
    "-msgstyle gcc -lang=c99 -DREVOKART",
    "-func_align 4",
    #"-sym dwarf-2",
]

# Hack: $@ doesn't behave properly with this
if sys.platform != "darwin":
    # suppress "function has no prototype
    CW_ARGS.append('-pragma "warning off(10178)"')

CWCC_OPT = " ".join(CW_ARGS)


def run_windows_cmd(cmd: str):
    """Runs a shell command and returns the stdout lines."""
    if sys.platform == "win32" or sys.platform == "msys":
        return __run_windows_cmd_win32(cmd)
    return __run_windows_cmd_wine(cmd)


def __run_windows_cmd_win32(cmd: str):
    process = subprocess.Popen(
        cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    lines = process.stdout.readlines()
    process.wait()
    return lines, process.returncode


def __unix_tmp_file():
    name = f"mkw-build-{random.randint(0, 1000000)}.log"
    # Wine with /dev/shm is slower than /tmp on Linux!
    tmp_dir = Path("/tmp")
    file_path = tmp_dir / name
    file = open(file_path, "w+")
    os.unlink(file_path)  # ensure file gets removed after build
    return file


def __run_windows_cmd_wine(cmd: str):
    if sys.platform == "darwin":
        compat = os.path.abspath("./mkwutil/tools/crossover.sh")
    else:
        compat = "wine"
    cmd = f"{compat} {cmd}"
    with __unix_tmp_file() as stdout:
        process = subprocess.run(
            cmd, text=True, stdout=stdout, stderr=subprocess.STDOUT, shell=True
        )
        stdout.seek(0, 0)
        return stdout.readlines(), process.returncode


def __assert_command_success(returncode, command):
    assert returncode == 0, f"{command} exited with returncode {returncode}"


def compile_source_impl(src, dst, version="default", additional="-ipa file"):
    """Compiles a source file."""
    # Compile ELF object file.
    command = f"{CWCC_PATHS[version]} {CWCC_OPT + ' ' + additional} {src} -o {dst}"
    lines, returncode = run_windows_cmd(command)
    with print_mutex:
        print(f'{colored("CC", "green")} {src}')
        if VERBOSE:
            print(command)
        for line in lines:
            print("   " + line.strip())
    __assert_command_success(returncode, command)


gSourceQueue = []


def compile_queued_sources(concurrency):
    """Dispatches multiple threads to compile all queued sources."""
    print(colored(f"max_hw_concurrency={concurrency}", color="yellow"))

    if not len(gSourceQueue):
        print(colored("No sources to compile", color="red"))
        return

    pool = ThreadPool(min(concurrency, len(gSourceQueue)))

    pool.map(lambda s: compile_source_impl(*s), gSourceQueue)

    pool.close()
    pool.join()

    gSourceQueue.clear()


# Queued
def queue_compile_source(src, version="default", additional="-ipa file"):
    """Queues a C/C++ file for compilation."""
    dst = (Path("out") / src.parts[-1]).with_suffix(".o")
    gSourceQueue.append((src, dst, version, additional))


def link(
    dst: Path, objs, lcf: Path, map_path: Path, partial: bool = False
) -> bool:
    """Links an ELF."""
    print(f'{colored("LD", "green")} {dst}')
    cmd = (
        [MWLD]
        + objs
        + [
            "-o",
            dst,
            "-lcf",
            lcf,
            "-fp",
            "hard",
            "-linkmode",
            "moreram",
            "-map",
            map_path,
        ]
    )
    if partial:
        cmd.append("-r")
    command = " ".join(map(str, cmd))
    lines, returncode = run_windows_cmd(command)
    for line in lines:
        print(line)
    __assert_command_success(returncode, command)


def compile_sources(args):
    """Compiles all C/C++"""
    out_dir = Path("out")
    out_dir.mkdir(exist_ok=True)

    for src in SOURCES:
        queue_compile_source(Path(src.src), src.cc, src.opts)

    if args.match:
        print(
            colored('[NOTE] Only compiling sources matching "%s".' % args.match, "red")
        )
        global gSourceQueue
        gSourceQueue = list(filter(lambda x: args.match in str(x[0]), gSourceQueue))
    if args.link_only:
        gSourceQueue = []

    compile_queued_sources(args.concurrency)


def link_dol(o_files):
    """Links main.dol."""
    # Generate LCF.
    src_lcf_path = Path("pack", "dol.lcf.j2")
    dst_lcf_path = Path("pack", "dol.lcf")
    slices_path = Path("pack", "dol_slices.csv")
    gen_lcf(src_lcf_path, dst_lcf_path, o_files, slices_path)
    # Create dest dir.
    dest_dir = Path("artifacts", "target", "pal")
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Link ELF.
    elf_path = dest_dir / "main.elf"
    map_path = dest_dir / "main.map"
    link(elf_path, o_files, dst_lcf_path, map_path)
    # Execute patches.
    with open(elf_path, "rb+") as elf_file:
        patch_elf(elf_file)
    # Convert ELF to DOL.
    dol_path = dest_dir / "main.dol"
    pack_main_dol(elf_path, dol_path)
    return dol_path


def link_rel(o_files):
    """Links StaticR.rel."""
    # Generate LCF.
    src_lcf_path = Path("pack", "rel.lcf.j2")
    dst_lcf_path = Path("pack", "rel.lcf")
    slices_path = Path("pack", "rel_slices.csv")
    gen_lcf(src_lcf_path, dst_lcf_path, o_files, slices_path)
    # Create dest dir.
    dest_dir = Path("artifacts", "target", "pal")
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Link ELF.
    elf_path = dest_dir / "StaticR.elf"
    map_path = dest_dir / "StaticR.map"
    link(elf_path, o_files, dst_lcf_path, map_path, partial=True)
    # Convert ELF to REL.
    rel_path = dest_dir / "StaticR.rel"
    orig_dir = Path("artifacts", "orig")
    pack_staticr_rel(elf_path, rel_path, orig_dir)
    return rel_path


def build(args):
    compile_sources(args)


def parse_args():
    parser = argparse.ArgumentParser(description="Build main.dol and StaticR.rel.")
    parser.add_argument(
        "-j",
        "--concurrency",
        type=int,
        default=multiprocessing.cpu_count(),
        help="Compile concurrency",
    )
    parser.add_argument(
        "--match", type=str, default=None, help="Only compile sources matching pattern"
    )
    parser.add_argument("--link_only", action="store_true", help="Link only, don't build")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()
    build(args)

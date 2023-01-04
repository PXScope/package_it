
#!/usr/bin/env python3
import argparse
import shutil
import os
import platform
from typing import Callable
from pathlib import Path

def cd_to_here():
    # Work in script directory (basically, workspace root)
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    os.chdir("..")

def setup_args():
    '''
    Startup script. You can skip this if you want to feed parameters directly.

    :return: prefix string that was retrieved from arguments
    '''
    print(f"info: Working from directory '{os.path.abspath(os.curdir)}'...")

    # Parse arguments
    parser = argparse.ArgumentParser(prog="PxRabbit Package Generator")
    parser.add_argument('prefix')
    parser.add_argument('--no-archive', action='store_true')
    parser.add_argument('--no-build', action='store_true')
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--no-clean', action='store_true')

    global ARGS
    ARGS = parser.parse_args()
    prefix: str = ARGS.prefix
    return prefix


def package(
    prefix: str,
    out_name: str,
    version: str,
    mapping: list[str],
    archive_out_dir: str,

    build_callback: Callable[[], int] = None,
    no_archive: bool = False,
    no_build: bool = False,
    overwrite: bool = False,
    no_clean: bool = False
):
    """
    Run packaging script

    Mapping rule:
        - ["dir_name", "changed_dir_name"] 
        - ["dir_name", "parent_dir_name/"]
        - ["file_name", "changed_file_name"]
        - ["file_name", "parent_dir_name/"]

    :param src_dir: Source directory
    :param out_name: Output names
    :param mapping: Mapping of files to copy
    :param build_callback: Callback to run build script

    :return: None
    """

    global ARGS
    args = ARGS

    if ARGS is not None:
        no_archive = ARGS.no_archive
        no_build = ARGS.no_build
        overwrite = ARGS.overwrite
        no_clean = ARGS.no_clean

    oname = f"{archive_out_dir}/{out_name}-{version}-{prefix}-{platform.system()}-{platform.release()}"
    pkg_dir = f"target/package/{platform.system()}-{platform.release()}"

    oname_platform = oname + (".zip" if platform.system() == "Windows" else ".tar.gz")

    if not overwrite and os.path.exists(oname_platform):
        print(f'fatal: File already exists: {oname}')
        exit(-1)

    # 1.2. Run build
    if not no_build and build_callback is not None:
        r = build_callback()
        if 0 != r:
            print(f'fatal: Build script returned error: {r}')
            exit(-1)

    # 2.0 Collect all files inside package directory
    non_targets = set([])

    if not no_clean:
        for root, subdirs, files in os.walk(pkg_dir):
            for file in files:
                non_targets.add(os.path.abspath(os.path.join(root, file)))

    # 2.1 Unroll directories into files
    unpacked = []
    for index, (src, dst) in zip(range(len(mapping)), mapping):
        if os.path.isfile(src):
            continue

        if not dst.endswith('/'):
            dst += '/'

        for root, subdirs, files in os.walk(src):
            dst_root = os.path.relpath(root, src)
            for file in files:
                unpacked.append((os.path.join(root, file), os.path.join(dst, dst_root) + '/'))

    mapping += unpacked

    # 3. Collect files to tempdir
    for index, (src, dst) in zip(range(len(mapping)), mapping):
        print(f"-- [{index+1}/{len(mapping)}] ", end="")

        if dst[-1] == '/':
            dst += os.path.basename(src)

        dst_src = dst
        dst = f"{pkg_dir}/{out_name}/{dst}"

        try:
            non_targets.remove(os.path.abspath(dst))
        except:
            pass

        try:
            # Skip by comparing mtime ...
            if os.path.isdir(src) or os.path.getmtime(src) < os.path.getmtime(dst):
                print(f"Skipped: {dst_src}")
                continue
        except:
            pass

        print(f"Installing: {os.path.relpath(dst, pkg_dir)}")
        os.makedirs(os.path.dirname(dst), exist_ok=True)

        dst_path = shutil.copy(src, dst)

    # 3.1. Exclude all non-targets
    for non_target in non_targets:
        print(f"-- Remove excluded: {os.path.relpath(non_target, os.path.abspath( os.curdir))}")
        os.remove(non_target)

    # 4. Zip packaged archive
    if no_archive:
        print('info: Skipping archive creation... ')
        exit(0)

    print(f"info: Archiving output package to {oname}... ")

    os.makedirs('target/archive', exist_ok=True)
    shutil.make_archive(
        oname,
        "zip" if platform.system() == "Windows" else "gztar",
        f"target/package/{platform.system()}-{platform.release()}/"
    )

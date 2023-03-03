
#!/usr/bin/env python3
import argparse
import glob
import shutil
import os
import platform
import subprocess
import sys
from typing import Callable, List, Tuple
from pathlib import Path

def cd_to_here(file, chdir_offset: str = None):
    # Work in script directory (basically, workspace root)
    os.chdir(os.path.dirname(os.path.realpath(file)))

    if chdir_offset is not None:
        os.chdir(chdir_offset)

class ArgInit:
    static_field = ""
    def __init__(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            'prefix', help='A mandatory build type prefix string')
        parser.add_argument(
            '--no-archive', action='store_true',
            help='Do not make archive')
        parser.add_argument(
            '--no-build', action='store_true',
            help='Do not run build script')
        parser.add_argument(
            '--overwrite', action='store_true',
            help='Overwrite exsiting archive')
        parser.add_argument(
            '--no-clean', action='store_true',
            help='Do not clean up unpacked content')
        parser.add_argument(
            '--allow-empty-dir', action='store_true',
            help='Allow empty directory result')
        parser.add_argument(
            '--version-suffix', '-V', dest='version_suffix', default=None, type=str,
            help='A string which is suffixed after version number. e.g. "rc1"')
        parser.add_argument(
            '--git-tag', action='store_true',
            help='Allow empty directory result'
        )

        args = parser.parse_args()
        self.args = args
        self.prefix: str = args.prefix
        self.no_archive: bool = args.no_archive
        self.no_build: bool = args.no_build
        self.overwrite: bool = args.overwrite
        self.no_clean: bool = args.no_clean
        self.auto_git_tag: bool = args.git_tag
        self.allow_empty_dir: bool = args.allow_empty_dir
        self.version_suffix: str or None = args.version_suffix

def init_with_args(parser: argparse.ArgumentParser) -> ArgInit:
    global ARGINIT
    ARGINIT = ArgInit(parser)
    return ARGINIT

def setup_args() -> str:
    '''
    Startup script. You can skip this if you want to feed parameters directly.

    :return: prefix string that was retrieved from arguments
    '''
    print(f"info: Working from directory '{os.path.abspath(os.curdir)}'...")

    # Parse arguments
    init = init_with_args(argparse.ArgumentParser())
    return init.prefix


def setup(file: str, chdir_offset: str = None) -> str:
    cd_to_here(file, chdir_offset)
    return setup_args()

def setup_with_args(
        file: str,
        parser: argparse.ArgumentParser = argparse.ArgumentParser(),
        chdir_offset: str = None):
    cd_to_here(file, chdir_offset)
    return init_with_args(parser)

class PackageResult:
    def __init__(
            self,
            oname: str, pkg_dir: str) -> None:
        self.oname = oname
        self.pkg_dir = pkg_dir

def package(
    prefix: str,
    out_name: str,
    version: str,
    mapping: List[Tuple[str, str]],
    result_dir: str,

    quick_copy_dirs: List[str] = [],
    archive_copy_dirs: List[str] = [],

    build_callback: Callable[[], int] = None,
    package_dir_callback: Callable[[str], None] = None,
    archive_file_callback: Callable[[str], None] = None,

    no_archive: bool = False,
    no_build: bool = False,
    overwrite: bool = False,
    no_clean: bool = False,
    allow_empty_dir: bool = False,
    auto_git_tag: bool = False,
    version_suffix: str = None,
) -> PackageResult or None:
    """
    Run packaging script

    Mapping rule:
        - ["dir_name", "changed_dir_name"]: Copy directory contents into changed directory name
        - ["dir_name", "parent_dir_name/"]: Copy directory contents under parent directory
        - ["file_name", "changed_file_name"]: Copy file into changed file name
        - ["file_name", "parent_dir_name/"]: Copy file under parent directory
        - ["file_name_with_glob", "parent_dir_name/"]: Copy all files that match glob under parent directory

    :param src_dir: Source directory
    :param out_name: Output names
    :param mapping: Mapping of files to copy
    :param build_callback: Callback to run build script

    :return: None
    """

    if 'ARGINIT' in globals():
        global ARGINIT
        no_archive |= ARGINIT.no_archive
        no_build |= ARGINIT.no_build
        overwrite |= ARGINIT.overwrite
        no_clean |= ARGINIT.no_clean
        allow_empty_dir |= ARGINIT.allow_empty_dir
        auto_git_tag |= ARGINIT.auto_git_tag
        if ARGINIT.version_suffix is not None:
            version_suffix = ARGINIT.version_suffix

    version_tag = version_suffix if version_suffix is not None else ''
    oname = f"{result_dir}/archive/{out_name}-{version}{version_tag}-{prefix}-{platform.system()}-{platform.release()}"
    pkg_dir = f"{result_dir}/{platform.system()}-{platform.release()}/{out_name}-{prefix}"

    oname_platform = oname + (".zip" if platform.system() == "Windows" else ".tar.gz")

    if not overwrite and not no_archive and os.path.exists(oname_platform):
        raise Exception(f'fatal: File already exists: {oname}')

    # 1.2. Run build
    if not no_build and build_callback is not None:
        r = build_callback()
        if 0 != r:
            raise Exception(f'fatal: Build script returned error: {r}')

    # 2.0 Collect all files inside package directory
    non_targets = set([])

    if not no_clean:
        for root, subdirs, files in os.walk(pkg_dir):
            for file in files:
                non_targets.add(os.path.abspath(os.path.join(root, file)))

    # Glob source paths
    new_mapping = []
    for src, dst in mapping:
        # Check if 'src' contains '*' or '?'
        if '*' in src or '?' in src:
            # dst must be directory name
            if dst[-1] != '/':
                raise Exception(f'fatal: Globbed source path must be directory: {src}')

            if '**' in src:
                # Find prefix which lays before '**'
                prefix = src[:src.index('**')]

                # Change prefix to os-specific notatation, which is used by glob
                prefix = prefix.replace('/', os.sep)

                # Collect GLOBed sources recursively
                for file in glob.glob(src, recursive=True):
                    # Exclude prefix from file path, so it will be relative to 'prefix'
                    prefix_excluded = file[len(prefix):]

                    # Append it to destination path
                    new_mapping.append([str(file), dst + prefix_excluded])
            else:
                # Collect GLOBed sources ...
                for file in glob.glob(src):
                    new_mapping.append([str(file), dst])
        else:
            new_mapping.append([src, dst])

    # Replace mapping with globbed one.
    mapping = new_mapping

    # Unroll directories into files
    unpacked = []
    for _, (src, dst) in zip(range(len(mapping)), mapping):
        if os.path.isfile(src):
            continue

        if not dst.endswith('/'):
            print('fatal: Directory source must be suffixed with "/": ' + src)

        for root, _, files in os.walk(src):
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
                print(f"Up-to-date: {dst_src}")
                continue
        except:
            pass

        print(f"* Installing: {os.path.relpath(dst, pkg_dir)} ... ", end='', flush=True)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        print("done.")

        shutil.copy(src, dst)

    # 3.1. Exclude all non-targets
    for non_target in non_targets:
        print(f"-- Remove excluded: {os.path.relpath(non_target, os.path.abspath( os.curdir))}")
        os.remove(non_target)

    # 3.2. Remove empty directories
    if not allow_empty_dir:
        for root, _, _ in os.walk(pkg_dir, topdown=False):
            if len(os.listdir(root)) == 0:
                print(f"-- Remove empty: {os.path.relpath(root, os.path.abspath(os.curdir))}")
                os.rmdir(root)

    # 3.3. bonus addtional libs
    for dir in quick_copy_dirs:
        try:
            print(f"  ++ copying package contents -> {dir} ... ", end='', flush=True)
            shutil.copytree(pkg_dir, dir, dirs_exist_ok=True)
            print(f"done.")
        except Exception as e:
            print(f"error {e}")

    # 4. Zip packaged archive
    if no_archive:
        print('info: skipping archive creation ... ')
        return

    print(f"info: archiving output package to {oname} ... ", end='', flush=True)

    os.makedirs(f'{result_dir}/archive', exist_ok=True)
    shutil.make_archive(
        oname,
        "zip" if platform.system() == "Windows" else "gztar",
        pkg_dir
    )
    print(f"done.")

    if package_dir_callback:
        package_dir_callback(pkg_dir)

    if archive_file_callback:
        archive_file_callback(oname_platform)

    for dir in archive_copy_dirs:
        try:
            print(f"  ++ copying archive -> {dir} ... ", end='', flush=True)
            shutil.copy(oname_platform, dir)
            print(f"done.")
        except Exception as e:
            print(f"error {e}")

    if auto_git_tag:
        print(f"info: tagging git repository with {version} ... ", end='', flush=True)
        subprocess.run(['git', 'tag', f'v{version}{version_tag}'])
        print(f"done.")

    return PackageResult(
        oname=oname_platform,
        pkg_dir=pkg_dir
    )

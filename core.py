
#!/usr/bin/env python3
from dataclasses import dataclass
import io
import argparse
import glob
import shutil
import os
import platform
import subprocess
from time import time
from typing import Callable, List, Tuple, Dict
from pathlib import Path

@dataclass()
class BumpVersion:
    major: bool
    minor: bool
    patch: bool

def chdir_to_file(file, chdir_offset: str = None):
    '''
    Changes current working directory to the directory of the file.
    '''
    os.chdir(os.path.dirname(os.path.realpath(file)))

    if chdir_offset is not None:
        os.chdir(chdir_offset)

class ArgInit:
    '''
    Additional packaging arguments which can be acquired from argument parser
    '''
    def __init__(
        self,
            parser_or_profile_val: argparse.ArgumentParser or str = None,
            define_bump_version=False,
    ) -> None:
        if parser_or_profile_val is None:
            parser_or_profile_val = argparse.ArgumentParser()

        if type(parser_or_profile_val) is argparse.ArgumentParser:
            # ------------------------------------ Definition ------------------------------------ #
            parser = parser_or_profile_val
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
                '--invalidate-all', action='store_true',
                help='Invalidates all existing caches')
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

            if define_bump_version:
                parser.add_argument(
                    '--bump-major', action='store_true',
                    help='Bump major version number'
                )

                parser.add_argument(
                    '--bump-minor', action='store_true',
                    help='Bump minor version number'
                )

                parser.add_argument(
                    '--bump-patch', action='store_true',
                    help='Bump patch version number'
                )

            # -------------------------------------- Parsing ------------------------------------- #
            args = parser.parse_args()
            self.args = args
            self.profile: str = args.prefix
            self.no_archive: bool = args.no_archive
            self.no_build: bool = args.no_build
            self.overwrite: bool = args.overwrite
            self.invalidate_all: bool = args.invalidate_all
            self.no_clean: bool = args.no_clean
            self.auto_git_tag: bool = args.git_tag
            self.allow_empty_dir: bool = args.allow_empty_dir
            self.version_suffix: str or None = args.version_suffix

            if define_bump_version:
                self.bump_version = BumpVersion(
                    major=args.bump_major,
                    minor=args.bump_minor,
                    patch=args.bump_patch
                )

        elif type(parser_or_profile_val) is str:
            self.profile: str = parser_or_profile_val
            self.args = None
            self.no_archive: bool = False
            self.no_build: bool = False
            self.overwrite: bool = False
            self.invalidate_all = False
            self.no_clean: bool = False
            self.auto_git_tag: bool = False
            self.allow_empty_dir: bool = False
            self.version_suffix: str or None = None
        else:
            raise TypeError("parser_profile must be either argparse.ArgumentParser or str")

class PackageResult:
    '''
    Package outputs, such as actual output file name, package directory, etc ...
    '''
    def __init__(self, oname: str, pkg_dir: str, version: str) -> None:
        self.oname = oname
        self.output_archive = oname
        self.pkg_dir = pkg_dir
        self.version = version

class FileCopyFilterArgs:
    '''
    File copy filter arguments, which is fed to filter callback
    '''
    def __init__(self, source_key: str, file_name: str, src_file: io.FileIO, dst_file: io.FileIO) -> None:
        self.source_key = source_key
        self.file_name = file_name
        self.src_file = src_file
        self.dst_file = dst_file

def package(
    opt: ArgInit,
    out_name: str,
    version: str,
    mapping: List[Tuple[str, str]],
    result_dir: str,

    quick_copy_dirs: List[str] = [],

    tree_copy_dirs: List[str] = [],
    archive_copy_dirs: List[str] = [],

    print: any = print,

    build_callback: Callable[[], int] = None,
    package_dir_callback: Callable[[str], None] = None,
    archive_file_callback: Callable[[str], None] = None,

    copy_filters: Dict[str, Callable[[FileCopyFilterArgs], None]] = None,

    git_tag_prefix: str = None,
) -> PackageResult or None:
    """
    Run packaging script

    Mapping rule:
        - ["path_name"]: Copy path into destination's root directory
        - ["dir_name", "changed_dir_name"]: Copy directory contents into changed directory name
        - ["dir_name", "parent_dir_name/"]: Copy directory contents under parent directory
        - ["file_name", "changed_file_name"]: Copy file into changed file name
        - ["file_name", "parent_dir_name/"]: Copy file under parent directory
        - ["file_name_with_glob", "parent_dir_name/"]: Copy all files that match glob under parent directory

    :param src_dir: Source directory
    :param out_name: Output names
    :param mapping: Mapping of files to copy
    :param build_callback: Callback to run build script
    :param quick_copy_dirs: DEPRECATED, use `tree_copy_dirs` instead

    :return: None
    """
    time_begin = time()
    tree_copy_dirs += quick_copy_dirs

    # validate params -> substitute empty destination to root ('/')
    for i in range(len(mapping)):
        arg = mapping[i]
        if len(arg) == 1:
            arg += ['/']

        if arg[1] == '':
            arg[1] = '/'

    # initialize arguments
    prefix = opt.profile

    # initialzie necessary variables
    version_tag = opt.version_suffix if opt.version_suffix is not None else ''
    oname = f"{result_dir}/archive/{out_name}-{version}{version_tag}-{prefix}-{platform.system()}-{platform.release()}"
    pkg_dir = f"{result_dir}/{platform.system()}-{platform.release()}/{out_name}-{prefix}"

    oname_platform = oname + (".zip" if platform.system() == "Windows" else ".tar.gz")

    if not opt.overwrite and not opt.no_archive and os.path.exists(oname_platform):
        raise Exception(f'fatal: File already exists: {oname}')

    # 1.2. Run build
    if not opt.no_build and build_callback is not None:
        r = build_callback()
        if 0 != r:
            raise Exception(f'fatal: Build script returned error: {r}')

    # 2.0 Collect all files inside package directory
    non_targets = set([])

    if not opt.no_clean:
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
                    new_mapping.append([str(file), dst + prefix_excluded, src])
            else:
                # Collect GLOBed sources ...
                for file in glob.glob(src):
                    new_mapping.append([str(file), dst, src])
        else:
            new_mapping.append([src, dst, src])

    # Replace mapping with globbed one.
    mapping = new_mapping

    # Unroll directories into files
    unpacked = []
    for _, (src, dst, src_key) in zip(range(len(mapping)), mapping):
        if os.path.isfile(src):
            continue

        if not dst.endswith('/'):
            print('fatal: Directory source must be suffixed with "/": ' + src)

        for root, _, files in os.walk(src):
            dst_root = os.path.relpath(root, src)
            for file in files:
                unpacked.append((
                    os.path.join(root, file),
                    os.path.join(dst, dst_root) + '/',
                    src_key
                ))

    mapping += unpacked

    # 3. Collect files to tempdir
    for index, (src, dst, src_key) in zip(range(len(mapping)), mapping):
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
            if os.path.isdir(src):
                print(f"Directory: {dst_src}")
                continue

            if not opt.invalidate_all and os.path.getmtime(src) < os.path.getmtime(dst):
                print(f"Up-to-date: {dst_src}")
                continue
        except:
            pass

        print(f"* Installing: {os.path.relpath(dst, pkg_dir)} ... ", end='', flush=True)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        print("done.")

        if copy_filters and src_key in copy_filters:
            with open(src, 'r') as src_file, open(dst, 'w') as dst_file:
                args = FileCopyFilterArgs(src_key, src, src_file, dst_file)
                copy_filters[src_key](args)
        else:
            shutil.copy(src, dst)

    # 3.1. Exclude all non-targets
    for non_target in non_targets:
        print(f"-- Remove excluded: {os.path.relpath(non_target, os.path.abspath( os.curdir))}")
        os.remove(non_target)

    # 3.2. Remove empty directories
    if not opt.allow_empty_dir:
        for root, _, _ in os.walk(pkg_dir, topdown=False):
            if len(os.listdir(root)) == 0:
                print(f"-- Remove empty: {os.path.relpath(root, os.path.abspath(os.curdir))}")
                os.rmdir(root)

    # 3.3. bonus addtional libs
    for dir in quick_copy_dirs:
        if len(dir) == 0:
            print(f"  -- warn: skipping empty quick_copy_dir ... ")
            continue

        try:
            print(f"  ++ copying package contents -> {dir} ... ", end='', flush=True)
            shutil.copytree(pkg_dir, dir, dirs_exist_ok=True)
            print(f"done.")
        except Exception as e:
            print(f"error {e}")

    # 4. Zip packaged archive
    retval = PackageResult(
        oname=oname_platform,
        pkg_dir=pkg_dir,
        version=version,
    )

    if opt.no_archive:
        print('info: skipping archive creation ... ')
        print(f"done. packaging took {time() - time_begin:.2} seconds")
        return retval

    print(f"info: archiving output package to {oname} ... ", end='', flush=True)

    os.makedirs(f'{result_dir}/archive', exist_ok=True)
    shutil.make_archive(
        oname,
        "zip" if platform.system() == "Windows" else "gztar",
        pkg_dir
    )

    if package_dir_callback:
        package_dir_callback(pkg_dir)

    if archive_file_callback:
        archive_file_callback(oname_platform)

    for dir in archive_copy_dirs:
        if len(dir) == 0:
            print(f"  -- warn: skipping empty archive_copy_dir ... ")
            continue

        try:
            print(f"  ++ copying archive -> {dir} ... ", end='', flush=True)
            shutil.copy(oname_platform, dir)
            print(f"done.")
        except Exception as e:
            print(f"error {e}")

    if opt.auto_git_tag:
        tag = f'{f"{git_tag_prefix}-" if git_tag_prefix else None}v{version}{version_tag}'

        print(f"info: tagging git repository with {tag} ... ", end='', flush=True)
        subprocess.run(['git', 'tag', tag])

    print(f"done. packaging took {time() - time_begin:.2f} seconds")
    return retval

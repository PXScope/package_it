import tomlkit

from package_it.core import BumpVersion

def get_version(src_dir: str) -> str:
    return version_control(src_dir)

def version_control(
        src_dir: str,
        bump: BumpVersion = None,
) -> str:
    '''
    Get the version from the Cargo.toml file.

    Args:
        src_dir: The path to the Cargo.toml file.
        bump_major: Whether to bump the major version.
        bump_minor: Whether to bump the minor version.
        bump_patch: Whether to bump the patch version.

    Returns:
        The version string.

    Each bump flag is overridden by the next one. For example, if bump_major is
    True, then bump_minor and bump_patch are ignored.
    '''

    if not src_dir.endswith("Cargo.toml"):
        src_dir = f'{src_dir}/Cargo.toml'

    with open(f'{src_dir}', 'r') as file:
        cargo = tomlkit.parse(''.join(file.readlines()))
        version = str(cargo["package"]["version"])

        if bump is None:
            return version

        major, minor, patch = map(lambda x: int(x), version.split("."))
        if bump.major:
            major += 1
            minor = 0
            patch = 0
        elif bump.minor:
            minor += 1
            patch = 0
        elif bump.patch:
            patch += 1
        else:
            return version

        version = f'{major}.{minor}.{patch}'
        cargo["package"]["version"] = version

    with open(f'{src_dir}', 'w') as file:
        file.write(tomlkit.dumps(cargo))

    if version is None:
        raise Exception("Version not found in Cargo.toml")

    return version

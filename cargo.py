import toml

def get_version(src_dir: str) -> str:
    if not src_dir.endswith("Cargo.toml"):
        src_dir = f'{src_dir}/Cargo.toml'

    with open(f'{src_dir}', 'r') as file:
        cargo = toml.loads('\n'.join(file.readlines()))
        version = cargo["package"]["version"]

    if version is None:
        raise Exception("Version not found in Cargo.toml")

    return version

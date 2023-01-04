import toml

def get_version(src_dir: str) -> str:
    with open(f'{src_dir}/Cargo.toml', 'r') as file:
        cargo = toml.loads('\n'.join(file.readlines()))
        version = cargo["package"]["version"]

    if version is None:
        raise Exception("Version not found in Cargo.toml")

    return version

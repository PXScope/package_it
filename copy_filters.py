from typing import List, Tuple
from . import core

def plain_text_replacer(patterns: List[Tuple[str, str]]):

    def __func(args: core.FileCopyFilterArgs):
        source_lines = args.src_file.readlines()
        for line in source_lines:
            for pattern in patterns:
                line = line.replace(pattern[0], pattern[1])
            args.dst_file.write(line)

    return __func

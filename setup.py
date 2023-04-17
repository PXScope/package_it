import os
from setuptools import setup, find_packages

INSTALL_REQUIRES = [
    "toml>=0.10",
]

setup(
    name="package_it",
    version="0.1.0",
    python_requires=">=3.7.0",
    author="Seungwoo Kang",
    author_email="swkang@pxscope.com",
    description="A Quart extension to provide rate limiting support.",
    url="https://github.com/stephen-pixelscope/package_it",
    classifiers=[],
    packages=find_packages("."),
    py_modules=["__init__", "core", "copy_filters", "cargo"],
    install_requires=INSTALL_REQUIRES,
)

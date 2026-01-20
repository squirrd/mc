"""Setup configuration for mc CLI."""

import os
from setuptools import setup, find_packages

# Read version from version.py without importing
version_file = os.path.join(os.path.dirname(__file__), "src", "mc", "version.py")
version_info = {}
with open(version_file, "r", encoding="utf-8") as f:
    exec(f.read(), version_info)

__version__ = version_info["__version__"]
__description__ = version_info["__description__"]

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mc-cli",
    version=__version__,
    author="David Squirrell",
    description=__description__,
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/mc-con",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.31.0",
    ],
    entry_points={
        "console_scripts": [
            "mc=mc.cli.main:main",
        ],
    },
)

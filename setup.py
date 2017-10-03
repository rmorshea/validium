import os
import sys
from distutils.core import setup
from setuptools import find_packages

if sys.version_info < (3, 6, 0):
    msg = "Installation requires Python 3.6.0 or greater."
    raise RuntimeError(msg)

this = os.path.dirname(__file__)
here = os.path.abspath(this)

project = "validium"
packages = find_packages(here)

requirements = os.path.join(here, "requirements.txt")
with open(requirements, "r") as requirements:
    requirements = [r for r in
        requirements.readlines()
        if not r.startswith("#")
        and "git+" not in r and
        "git://" not in r]

install = dict(
    name=project,
    packages=packages,
    install_requires=requirements,
)

if __name__ == "__main__":
    setup(**install)

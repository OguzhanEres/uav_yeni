# uav_project/setup.py
from setuptools import setup, find_packages

setup(
    name="uav_system",
    version="0.1",
    package_dir={"": "src"},
    packages=find_packages("src"),
)

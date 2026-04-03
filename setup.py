"""
Setup configuration for Fabric infrastructure abstraction layer.
"""
from setuptools import setup, find_packages

setup(
    name="fabric",
    version="0.1.0",
    description="Infrastructure abstraction layer for Forge Foundation",
    author="Forge Foundation",
    packages=find_packages(),
    install_requires=[
        "requests==2.31.0",
        "pydantic==2.5.0",
        "python-dotenv==1.0.0",
    ],
    python_requires=">=3.10",
)

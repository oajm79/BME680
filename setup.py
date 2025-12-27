#!/usr/bin/env python3
"""Setup script for BME680 Monitor."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the long description from README
readme_file = Path(__file__).parent / "docs" / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip()
        for line in requirements_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="bme680-monitor",
    version="2.0.0",
    author="BME680 Monitor Project",
    author_email="",
    description="Professional air quality monitoring system using BME680 sensor",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/BME680",
    project_urls={
        "Bug Tracker": "https://github.com/yourusername/BME680/issues",
        "Documentation": "https://github.com/yourusername/BME680/blob/main/docs/README.md",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: System :: Monitoring",
        "Topic :: Scientific/Engineering :: Atmospheric Science",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.7",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=8.3.3",
            "pytest-cov>=5.0.0",
            "black>=24.0.0",
            "flake8>=7.0.0",
            "mypy>=1.8.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "bme680-monitor=sensor:main",
        ],
    },
    include_package_data=True,
    package_data={
        "bme680_monitor": ["py.typed"],
    },
    zip_safe=False,
    keywords="bme680 air-quality sensor monitoring raspberry-pi iot",
)

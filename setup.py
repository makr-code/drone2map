from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

with open("requirements.txt") as f:
    requirements = [
        l.strip() for l in f
        if l.strip() and not l.startswith("#") and not l.startswith("pytest")
    ]

setup(
    name="drone2map",
    version="0.1.0",
    description="Drohnenbilder zu Orthofoto, DSM und DGM verarbeiten",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="makr-code",
    python_requires=">=3.10",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=requirements,
    extras_require={
        "dev": ["pytest>=7.0.0", "pytest-mock>=3.11.0"],
    },
    entry_points={"console_scripts": ["drone2map=drone2map.main:main"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
)

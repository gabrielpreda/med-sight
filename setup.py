"""Setup configuration for MedSight"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="medsight",
    version="2.0.0",
    author="MedSight Team",
    description="AI-Powered Medical Assistant with Multi-Agent Intelligence",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "google==3.0.0",
        "google-cloud-core==2.4.1",
        "google-cloud-aiplatform==1.99.0",
        "streamlit==1.28.0",
        "gunicorn==20.0.4",
        "python-dotenv==1.0.0",
        "pydantic==2.5.3",
        "PyPDF2==3.0.1",
        "pydicom==2.4.4",
        "pillow==10.1.0",
        "pyyaml==6.0.1",
        "aiofiles==23.2.1",
        "pytest==7.4.3",
        "pytest-asyncio==0.21.1",
        "pytest-cov==4.1.0",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Healthcare Industry",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)

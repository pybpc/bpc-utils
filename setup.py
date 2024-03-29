import os
import subprocess  # nosec
import sys

from setuptools import setup  # type: ignore[import]

os.chdir(os.path.dirname(os.path.realpath(__file__)))

with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

module_name = 'bpc_utils'
version = subprocess.check_output([sys.executable,  # nosec
                                   os.path.join('scripts', 'find_version.py')],
                                  universal_newlines=True).strip()

setup(
    name='bpc-utils',
    version=version,
    description='Utility library for the Python bpc compiler.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/pybpc/bpc-utils',
    author='Saiyang Gou',
    author_email='gousaiyang223@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development',
        'Topic :: Utilities',
        'Typing :: Typed',
    ],
    keywords='bpc backport utilities',
    packages=[module_name],
    package_data={module_name: ['py.typed']},
    python_requires='>=3.4',
    install_requires=[
        'parso>=0.6.0',
        'typing;python_version<"3.5"',
        'typing_extensions>=3.7.2',  # Literal, Final, ...
    ],
    extras_require={
        'lint': [
            'flake8',
            'pylint>=2.11.0',
            'mypy',
            'bandit>=1.6.3',
            'vermin>=1.2.0',
            'colorlabels>=0.7.0',
            'parso>=0.8.0',
            'pytest>=6.2.0',
        ],
        'test': [
            'pytest>=4.5.0',
            'pytest-doctestplus>=0.5.0',
            'coverage',
        ],
        'docs': [
            'Sphinx',
            'sphinx-autodoc-typehints',
            'sphinxext-opengraph',
            'sphinx-copybutton',
        ],
    },
)

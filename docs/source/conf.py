import os
import sys
from typing import List

# Configuration file for the Sphinx documentation builder.

# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

PROJECT_ROOT = os.path.abspath(
    os.path.dirname(  # docs/
        os.path.dirname(  # docs/source
            os.path.dirname(__file__)  # docs/source/conf.py
        )
    )
)
sys.path.insert(0, PROJECT_ROOT)

# Let our module detect whether Sphinx build is running.
os.environ['SPHINX_BUILD_HAPPENING'] = '1'

# -- Project information -----------------------------------------------------

project = 'bpc-utils'
copyright = '2019-2021, Python Backport Compiler Project'  # pylint: disable=redefined-builtin
author = 'Python Backport Compiler Project'

# The full version, including alpha/beta/rc tags
release = __import__('bpc_utils').__version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'sphinx.ext.autodoc',
    'sphinx_autodoc_typehints',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'parso': ('https://parso.readthedocs.io/en/latest/', None),
}

# type hints will be taken care of by sphinx_autodoc_typehints instead of sphinx.ext.autodoc.typehints
autodoc_typehints = 'none'

# tell sphinx_autodoc_typehints to set typing.TYPE_CHECKING to True
set_type_checking_flag = True

# autodoc_member_order = 'bysource'
autodoc_member_order = 'groupwise'

autoclass_content = 'both'

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = True
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_use_keyword = True
napoleon_custom_sections = None

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []  # type: List[str]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.

html_theme = 'alabaster'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    'show_powered_by': False,
    'github_user': 'pybpc',
    'github_repo': 'bpc-utils',
    'github_banner': True,
    # 'github_type': 'star',
}

from inspect import isclass
import os
import sys


def module_dir():
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    directory = root
    return directory


sys.path.insert(0, module_dir())
import PyBirdViewCode
from sphinx.builders.html import StandaloneHTMLBuilder

# -- Project information -----------------------------------------------------

project = "PyBirdViewCode"
copyright = "2022-2023, SkyGroup"
author = "hzy15610046011"
release = "0.1.0"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings.
# They can be extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.mathjax",
    "sphinx_rtd_theme",
    "recommonmark",
    "sphinx_markdown_tables",
    "sphinx.ext.autosectionlabel",
    "enum_tools.autoenum",
    "sphinxcontrib.mermaid",
]
# autosectionlabel_prefix_document = True

# Add any paths that contain templates here, relative to this directory.
templates_path = []

# List of patterns, relative to excel_source directory, that match files and
# directories to ignore when looking for excel_source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = "sphinx_rtd_theme"
html_logo = "image/sky-cloud.png"
html_theme_options = {"collapse_navigation": False, "navigation_depth": 4}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a data named "default.css" will overwrite the builtin "default.css".
html_static_path = []
html_css_files = []
# This allows us to dynamically pick between gif and png images based on the build.
# For example, when we have something like:
# .. image:: that_directory/this_image.*
# Then the build will look for the image in that_directory in the following
# order. Because html supports gif, it will grab the gif image before the png,
# whereas because pdf does not support gif, it will grab the png.
StandaloneHTMLBuilder.supported_image_types = [
    "image/svg+xml",
    "image/gif",
    "image/png",
    "image/jpeg",
]
html_sidebars = {
    "**": ["globaltoc.html", "relations.html", "sourcelink.html", "searchbox.html"]
}

# autodoc_member_order = "bysource"
autoclass_content = "both"
add_module_names = False
autodoc_default_options = {"special-members": "__init__"}
# autodoc_type_aliases = {"PyBirdViewCode.clang_utils.code_attributes": "PyBirdViewCode.clang_utils"}
# typehints_use_signature = True
# # typehints_use_signature_return = True


# def typehints_formatter(s, cfg):
#     # print(s, isclass(s) , ("Melodie" in str(s)))
#     # if isclass(s):
#     #     print(s.__name__)
#     #     return str(s.__name__)
#     # print(s, type(s))
#     return "type hint"

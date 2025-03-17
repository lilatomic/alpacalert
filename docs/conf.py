# Configuration file for the Sphinx documentation builder.
import sys
from pathlib import Path

sys.path.insert(0, (Path.cwd().parent / "src" / "main" / "python").as_posix())

# -- Project information

project = "alpacalert"
copyright = "2024, lilatomic"
author = "lilatomic"

release = "0.1"
version = "0.1.0"

# -- General configuration

extensions = [
	"sphinx.ext.duration",
	"sphinx.ext.doctest",
	"sphinx.ext.autodoc",
	"sphinx.ext.autosummary",
	"sphinx.ext.intersphinx",
	"sphinx.ext.napoleon",
	"sphinxcontrib.apidoc",
	"myst_parser",
]

intersphinx_mapping = {
	"python": ("https://docs.python.org/3/", None),
	"sphinx": ("https://www.sphinx-doc.org/en/master/", None),
}
intersphinx_disabled_domains = ["std"]

apidoc_module_dir = "../src/main/python/alpacalert"
apidoc_output_dir = "modules"
apidoc_separate_modules = True

templates_path = ["_templates"]

# -- Options for HTML output

html_theme = "sphinx_rtd_theme"

# -- Options for EPUB output
epub_show_urls = "footnote"


def autodoc_skipables(app, what, name, obj, skip, options):
	if name in {"model_computed_fields", "model_config", "model_fields"}:
		return True
	return skip


def setup(app):
	app.connect("autodoc-skip-member", autodoc_skipables)


exclude_patterns = ["modules/modules", "modules/modules.rst"]

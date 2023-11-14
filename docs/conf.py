# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys
sys.path.insert(0, os.path.abspath('.')) 
sys.path.insert(0, os.path.abspath('../twinmodules/core')) 
sys.path.insert(0, os.path.abspath('../twinmodules/AWSModules')) 

project = 'twinmodules'
copyright = '2023, AWS AC Team'
author = 'AWS AC Team'
release = '0.3.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.autosectionlabel',
    
    # Used to insert typehints into the final docs:
    'sphinx_autodoc_typehints',
    
    "sphinx.ext.napoleon",

    ]


autoclass_content = 'both'

autodoc_member_order = 'bysource'
autodoc_default_flags = {
    'members': '',
    'undoc-members': 'code,error_template',
    'exclude-members': '__dict__,__weakref__',
}


templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

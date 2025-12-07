from importlib import import_module

# Expose the lex submodule so imports like `import ply.lex as lex` return the module.
lex = import_module('.lex', __name__)

__all__ = ["lex"]

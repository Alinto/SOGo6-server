# app/__init__.py
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("SOGo6-server") # [project] name in pyproject.toml
except PackageNotFoundError:
    __version__ = "6.0.0a2"

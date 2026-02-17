# database/__init__.py
from .repository import db, init_db, close_db, DB
__all__ = ["db", "init_db", "close_db", "DB"]

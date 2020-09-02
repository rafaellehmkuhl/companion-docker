from os import listdir
from os.path import dirname, basename

# Allow 'from lib import *' to access all plugins available
__all__ = [basename(f)[:-3] for f in listdir(dirname(__file__)) if f[-3:] == ".py" and not f.endswith("__init__.py")]
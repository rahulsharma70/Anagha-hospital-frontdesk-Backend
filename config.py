"""
Shared config module - imports config_web by default
server_mobile.py will replace this module with config_mobile before importing other modules
"""
import config_web
from config_web import *

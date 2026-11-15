"""Ponto de entrada do cPanel ("Setup Python App" usa o Passenger).

No cPanel, configure:
  Application root:          paraipython/src
  Application startup file:  passenger_wsgi.py
  Application Entry point:   application
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from core.wsgi import application  # noqa: E402,F401

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app import app

# Vercel procura uma variável chamada "app" (WSGI)
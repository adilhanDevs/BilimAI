import os
import sys

# Add your project directory to the sys.path
path = '/home/adilhan/AiTil'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'BilimAI.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

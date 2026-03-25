# ============================================================
# PythonAnywhere WSGI configuration file for BilimAI
#
# Paste the contents of this file (or this whole file) into
# the WSGI configuration editor on PythonAnywhere.
# Located at: Web tab → WSGI configuration file (click the link)
#
# ============================================================

import os
import sys

# Path to your project directory on PythonAnywhere
project_home = "/home/adilhan/bilimAI"

if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Activate the virtual environment
activate_this = "/home/adilhan/bilimAI/venv/bin/activate_this.py"
with open(activate_this) as f:
    exec(f.read(), {"__file__": activate_this})

os.environ["DJANGO_SETTINGS_MODULE"] = "BilimAI.settings"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()

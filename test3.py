import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "AiTil.settings")
django.setup()

import traceback
from django.test import Client
from django.contrib.auth import get_user_model

try:
    User = get_user_model()
    user = User.objects.filter(is_superuser=True).first()
    c = Client()
    c.force_login(user)
    response = c.get('/admin/lessons/category/', HTTP_HOST='localhost')
    print("STATUS:", response.status_code)
except Exception as e:
    traceback.print_exc()

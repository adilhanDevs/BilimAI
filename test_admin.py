import os
import django
from django.test import Client
from django.contrib.auth.models import User

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AiTil.settings')
django.setup()

user = User.objects.filter(is_superuser=True).first()
if not user:
    user = User.objects.create_superuser('admin', 'admin@example.com', 'pass')

c = Client()
c.force_login(user)
try:
    response = c.get('/admin/lessons/category/')
    print("STATUS", response.status_code)
except Exception as e:
    import traceback
    traceback.print_exc()

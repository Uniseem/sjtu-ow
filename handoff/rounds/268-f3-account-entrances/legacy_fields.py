"""Read actual configured allauth fields without a database or passwords."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sjtu_ow.settings.dev')
import django
django.setup()
from accounts import allauth_forms as forms
from accounts.models import User
from django.test import RequestFactory
from django.template.loader import render_to_string
from allauth.core import context

request = RequestFactory().get('/')
request.user = User(pk=1, email='member@example.com', nickname='测试成员')
request.session = {}
with context.request_context(request):
    forms_by_name = dict(login=forms.LoginForm(request=request), signup=forms.SignupForm(),
                        verify=forms.ConfirmEmailVerificationCodeForm(),
                        reauth=forms.ReauthenticateForm(user=request.user),
                        password=forms.ChangePasswordForm(user=request.user),
                        reset=forms.ResetPasswordForm())
    data = {name: [dict(name=f.name, label=str(f.label), required=f.field.required,
                       html=str(f), help=str(f.help_text),
                       component=render_to_string('components/form_field.html', {'field': f}))
                   for f in form.visible_fields()] for name, form in forms_by_name.items()}
    output = Path('/tmp/sjtuow-268-fields.json')
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(data, ensure_ascii=False, indent=2))

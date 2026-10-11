"""Visual account contexts, deliberately separate from the real SMTP journey."""
import base64
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

ROLES = ('visitor', 'member', 'captain', 'tournament_admin', 'scrim_admin', 'content_editor', 'officer')
EXTRA_EMAILS = {role: role + '@screens.test' for role in ROLES[3:6]}
ADDRESSES = (
    ('login', '/accounts/login/'),
    ('signup', '/accounts/signup/'),
    ('confirm-email', '/accounts/confirm-email/'),
    ('logout', '/accounts/logout/'),
    ('inactive', '/accounts/inactive/'),
    ('reauthenticate', '/accounts/reauthenticate/'),
    ('email', '/accounts/email/'),
    ('password-change', '/accounts/password/change/'),
    ('password-set', '/accounts/password/set/'),
    ('password-reset', '/accounts/password/reset/'),
    ('password-reset-confirm', '/accounts/password/reset/confirm/'),
    ('password-reset-complete', '/accounts/password/reset/complete/'),
    ('password-reset-done', '/accounts/password/reset/done/'),
    ('login-code-confirm', '/accounts/login/code/confirm/'),
)
PAGES = [(name, role, path) for role in ROLES for name, path in ADDRESSES]


def validate_import(work):
    with sqlite3.connect(work / 'new-data/sjtuow.sqlite3') as db:
        for role in ROLES[1:]:
            email = EXTRA_EMAILS.get(role, role + '@screens.test')
            user_id, active, superuser = db.execute('SELECT id,is_active,is_superuser FROM users WHERE email=?', (email,)).fetchone()
            if not active or bool(superuser) != (role == 'officer'):
                raise RuntimeError('wrong identity flags for ' + role)
            if role in EXTRA_EMAILS and not db.execute('SELECT 1 FROM user_roles WHERE user_id=? AND role=?', (user_id, role)).fetchone():
                raise RuntimeError('missing imported role ' + role)
    print('ACCOUNT-IDENTITIES-OK 7 (three non-superuser cadres)', flush=True)


def extend_seed(data):
    from accounts.models import User
    from accounts.services import GROUP_CONTENT, GROUP_SCRIM, GROUP_TOURNAMENT
    from allauth.account.models import EmailAddress
    from django.contrib.auth.models import Group
    from django.test import Client
    from django.utils import timezone as django_timezone
    consent = {'agreed_terms_at': django_timezone.now(), 'agreed_cross_border_at': django_timezone.now()}
    for role, group_name in zip(ROLES[3:6], (GROUP_TOURNAMENT, GROUP_SCRIM, GROUP_CONTENT)):
        user = User.objects.create_user(email=EXTRA_EMAILS[role], nickname=role,
                                        is_sjtu=True, is_staff=True, **consent)
        user.groups.add(Group.objects.get(name=group_name))
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        client = Client()
        client.force_login(user)
        data['sessions'][role] = client.cookies['sessionid'].value
    pending = User.objects.create_user(email='pending@screens.test', nickname='待验证成员', is_sjtu=True, **consent)
    EmailAddress.objects.create(user=pending, email=pending.email, verified=False, primary=True)


def legacy_context(session_key, email, verification=False, completed=False):
    from accounts.models import User
    from allauth.account.internal.flows.code_verification import AbstractCodeVerificationProcess
    from allauth.account.internal.flows.email_verification_by_code import EMAIL_VERIFICATION_CODE_SESSION_KEY
    from allauth.account.internal.flows.password_reset_by_code import PASSWORD_RESET_VERIFICATION_SESSION_KEY
    from allauth.account.internal.stagekit import LOGIN_SESSION_KEY
    from allauth.account.models import Login
    from allauth.account.stages import EmailVerificationStage
    from django.contrib.sessions.backends.db import SessionStore
    source = SessionStore(session_key=session_key) if session_key else {}
    session = SessionStore()
    session.update(dict(source))
    user = User.objects.get(email='pending@screens.test' if verification and not session_key else email)
    state = AbstractCodeVerificationProcess.initial_state(user, email)
    state['code'] = '001234'
    if verification:
        session[EMAIL_VERIFICATION_CODE_SESSION_KEY] = state
        if not session_key:
            session[LOGIN_SESSION_KEY] = Login(user=user, email=email, signup=True,
                state={'stages': {'current': EmailVerificationStage.key}}).serialize()
    else:
        state['code_confirmed'] = completed
        session[PASSWORD_RESET_VERIFICATION_SESSION_KEY] = state
    session.save()
    return session.session_key


def context(name, who, data, new_sessions, work, legacy_env):
    # Fresh contexts per page keep the real 3-minute/15-minute deadlines intact.
    # No SMTP/verification behavior is inferred from these visual fixtures.
    import os
    os.environ.update(legacy_env)
    import django
    django.setup()
    # Five GETs per page (status + four views) must not consume the next
    # page's visual fixture quota. This is not a rate-limit journey.
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM django_cache WHERE cache_key LIKE %s", ['%allauth:rl:%'])
    with sqlite3.connect(work / 'new-data/sjtuow.sqlite3') as db:
        db.execute('DELETE FROM email_changes')
        db.execute("DELETE FROM email_codes WHERE purpose='password_reset_grant'")
    old_key = data['sessions'].get(who)
    new = [{'name': 'ow_session', 'value': new_sessions[who]}] if who in new_sessions else []
    suffix = ''
    if name in ('confirm-email', 'password-reset-confirm', 'password-reset-complete'):
        email = 'pending@screens.test' if who == 'visitor' and name == 'confirm-email' else (EXTRA_EMAILS.get(who) or (who if who != 'visitor' else 'member') + '@screens.test')
        old_key = legacy_context(old_key, email, verification=name == 'confirm-email', completed=name == 'password-reset-complete')
        if name == 'confirm-email':
            suffix = '?email=' + email
            if who != 'visitor':
                pending = 'pending-' + who + '@screens.test'
                # A same-user new-email process has the same visual email on both sides.
                from django.contrib.sessions.backends.db import SessionStore
                session = SessionStore(session_key=old_key)
                session['account_email_verification_code']['email'] = pending
                session.save()
                now = datetime.now(timezone.utc)
                with sqlite3.connect(work / 'new-data/sjtuow.sqlite3') as db:
                    user_id = db.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]
                    db.execute('INSERT OR REPLACE INTO email_changes (user_id,new_email,new_email_norm,code_hash,attempts,created_at,expires_at) VALUES (?,?,?,?,0,?,?)',
                               (user_id, pending, pending, hashlib.sha256(b'001234').hexdigest(), now.isoformat(), (now+timedelta(minutes=15)).isoformat()))
                suffix = '?mode=change&email=' + pending
        elif name == 'password-reset-confirm':
            suffix = '?email=' + email
        else:
            raw = secrets.token_bytes(32)
            token = base64.urlsafe_b64encode(raw).decode().rstrip('=')
            now = datetime.now(timezone.utc)
            with sqlite3.connect(work / 'new-data/sjtuow.sqlite3') as db:
                db.execute('INSERT INTO email_codes (purpose,email_norm,code_hash,attempts,created_at,expires_at) VALUES (?,?,?,0,?,?)',
                           ('password_reset_grant', email, hashlib.sha256(raw).hexdigest(), now.isoformat(), (now+timedelta(minutes=3)).isoformat()))
            new.append({'name': 'ow_password_reset', 'value': token})
    return ([{'name': 'sessionid', 'value': old_key}] if old_key else []), new, suffix

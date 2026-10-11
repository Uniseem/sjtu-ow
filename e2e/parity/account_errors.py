"""Submit real invalid forms; never manufacture error DOM/API responses."""
import hashlib
import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone

PASSWORD = 'ParityPassword!2026'
STRONG = 'Maple!Orbit829'
SCENARIOS = {
    'error-login': ('login', 'visitor', {'login': 'member@screens.test', 'password': 'Wrong!Orbit829'}),
    'error-signup-mismatch': ('signup', 'visitor', {'email': 'new@example.test', 'nickname': '测试新人', 'password1': STRONG, 'password2': 'Mismatch!Orbit829', 'is_sjtu': 'true', 'agreed_terms': True, 'agreed_cross_border': True}),
    'error-signup-short': ('signup', 'visitor', {'email': 'new@example.test', 'nickname': '测试新人', 'password1': 'abc', 'password2': 'abc', 'is_sjtu': 'true', 'agreed_terms': True, 'agreed_cross_border': True}),
    'error-signup-numeric': ('signup', 'visitor', {'email': 'new@example.test', 'nickname': '测试新人', 'password1': '12345678', 'password2': '12345678', 'is_sjtu': 'true', 'agreed_terms': True, 'agreed_cross_border': True}),
    'error-reauth': ('reauthenticate', 'member', {'password': 'Wrong!Orbit829'}),
    'error-change-old': ('password-change', 'member', {'oldpassword': 'Wrong!Orbit829', 'password1': STRONG, 'password2': STRONG}),
    'error-change-mismatch': ('password-change', 'member', {'oldpassword': PASSWORD, 'password1': STRONG, 'password2': 'Mismatch!Orbit829'}),
    'error-change-short': ('password-change', 'member', {'oldpassword': PASSWORD, 'password1': 'abc', 'password2': 'abc'}),
    'error-email-code': ('confirm-email', 'visitor', {'code': '999999'}),
    'error-reset-code': ('password-reset-confirm', 'visitor', {'code': '999999'}),
    'error-reset-short': ('password-reset-complete', 'visitor', {'password1': 'abc', 'password2': 'abc'}),
}
PATHS = {'login': '/accounts/login/', 'signup': '/accounts/signup/', 'reauthenticate': '/accounts/reauthenticate/', 'password-change': '/accounts/password/change/', 'confirm-email': '/accounts/confirm-email/', 'password-reset-confirm': '/accounts/password/reset/confirm/', 'password-reset-complete': '/accounts/password/reset/complete/'}
API_PATHS = {
    'login': '/api/auth/login',
    'signup': '/api/auth/register',
    'reauthenticate': '/api/auth/reauthenticate',
    'password-change': '/api/auth/change-password',
    'confirm-email': '/api/auth/verify-email',
    'password-reset-confirm': '/api/auth/reset-password/verify',
    'password-reset-complete': '/api/auth/reset-password/complete',
}
PAGES = [(name, who, PATHS[page]) for name, (page, who, fields) in SCENARIOS.items()]


def context(name, data, sessions, work, legacy_env):
    from account_scenarios import context as normal_context
    page, who, _ = SCENARIOS[name]
    old, new, suffix = normal_context(page, who, data, sessions, work, legacy_env)
    if page in ('confirm-email', 'password-reset-confirm'):
        email = 'pending@screens.test' if page == 'confirm-email' else 'member@screens.test'
        now = datetime.now(timezone.utc)
        with sqlite3.connect(work / 'new-data/sjtuow.sqlite3') as db:
            purpose = 'signup' if page == 'confirm-email' else 'password_reset'
            db.execute('DELETE FROM email_codes WHERE purpose=? AND email_norm=?', (purpose, email))
            db.execute('INSERT INTO email_codes (purpose,email_norm,code_hash,attempts,created_at,expires_at) VALUES (?,?,?,0,?,?)', (purpose, email, hashlib.sha256(b'001234').hexdigest(), now.isoformat(), (now+timedelta(minutes=3)).isoformat()))
    # Each viewport is a fresh rejected attempt, not a three-attempt journey.
    with sqlite3.connect(work / 'new-data/sjtuow.sqlite3') as db:
        db.execute('DELETE FROM rate_counters')
    return old, new, suffix


def submit(tools, name, evaluate):
    page = SCENARIOS[name][0]
    fields = SCENARIOS[name][2]
    tools.submissions.clear()
    evaluate(tools, f'''(() => {{
      const form=document.querySelector('#main form');
      if(!form)throw new Error('missing account form');
      for(const [name,value] of Object.entries({json.dumps(fields, ensure_ascii=True)})) {{
        const nodes=[...form.querySelectorAll('[name="'+name+'"]')];
        if(!nodes.length)throw new Error('missing form field '+name);
        if(nodes[0].type==='radio') {{const node=nodes.find(n=>n.value===value);if(!node)throw new Error('missing radio option '+name);node.click()}}
        else if(nodes[0].type==='checkbox') {{if(nodes[0].checked!==value)nodes[0].click()}}
        else {{nodes[0].value=value;nodes[0].dispatchEvent(new Event('input',{{bubbles:true}}))}}
      }}
      if(!form.checkValidity())throw new Error('invalid fixture: native validation blocked submission');
      form.requestSubmit();return true;
    }})()''')
    for _ in range(120):
        ready = evaluate(tools, "Boolean(document.readyState==='complete' && document.querySelector('#main .c-field__error') && !document.querySelector('#main button[type=submit]')?.disabled)")
        responses = [r for r in tools.submissions if r['path'] in (PATHS[page], API_PATHS[page])]
        if ready and responses:
            response = responses[-1]
            expected = 200 if response['path'] == PATHS[page] else (401 if page == 'login' else 422)
            if response['status'] != expected:
                raise RuntimeError(f"unexpected rejected-form response for {name}: {response}")
            break
        time.sleep(0.05)
    else:
        raise RuntimeError('real invalid form did not produce an error: ' + name)
    evaluate(tools, "document.fonts.ready.then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))")
    # Response metadata only: never store passwords, codes, cookies or bodies.
    return response

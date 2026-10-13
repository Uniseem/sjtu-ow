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
# Additional real states. No API error or DOM is manufactured.
SCENARIOS.update({
    'error-email-expired': ('confirm-email', 'visitor', {'code': '001234'}),
    'error-email-third-attempt': ('confirm-email', 'visitor', {'code': '999999'}),
    'error-reset-expired': ('password-reset-confirm', 'visitor', {'code': '001234'}),
    'error-signup-existing': ('signup', 'visitor', {'email': 'member@screens.test', 'nickname': '已注册测试', 'password1': STRONG, 'password2': STRONG, 'is_sjtu': 'true', 'agreed_terms': True, 'agreed_cross_border': True}),
    'error-login-limit': ('login', 'visitor', {'login': 'member@screens.test', 'password': 'Wrong!Orbit829'}),
    'error-signup-limit': ('signup', 'visitor', {'email': 'limited@example.test', 'nickname': '限流新人', 'password1': STRONG, 'password2': 'Mismatch!Orbit829', 'is_sjtu': 'true', 'agreed_terms': True, 'agreed_cross_border': True}),
    'error-reset-limit': ('password-reset', 'visitor', {'email': 'member@screens.test'}),
    'error-resend-limit': ('confirm-email', 'visitor', {}),
    'error-email-occupied': ('email', 'member', {'email': 'captain@screens.test'}),
    'error-resend-cooldown': ('confirm-email', 'visitor', {}),
})
PATHS['email'] = '/accounts/email/'
API_PATHS['email'] = '/api/auth/email/change'
PATHS['password-reset'] = '/accounts/password/reset/'
API_PATHS['password-reset'] = '/api/auth/reset-password'
PAGES = [(name, who, PATHS[page]) for name, (page, who, fields) in SCENARIOS.items()]


_fixture = {}

def context(name, data, sessions, work, legacy_env):
    global _fixture
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
    if name == 'error-email-occupied':
        from django.test import Client
        client = Client()
        client.cookies['sessionid'] = old[0]['value']
        response = client.post('/accounts/reauthenticate/', {'password': PASSWORD})
        if response.status_code not in (200,302): raise RuntimeError('legacy reauthentication failed')
        import os, urllib.request
        request = urllib.request.Request(os.environ['PARITY_API_BASE']+'/api/auth/reauthenticate', data=json.dumps({'password':PASSWORD}).encode(), headers={'Content-Type':'application/json','Cookie':'ow_session='+sessions[who]}, method='POST')
        with urllib.request.urlopen(request,timeout=20) as response:
            if response.status!=200: raise RuntimeError('new reauthentication failed')
    _fixture = {'work': work, 'old_session': old[0]['value'] if old else None, 'page': page, 'email': email if page in ('confirm-email','password-reset-confirm') else None}
    if name == 'error-email-third-attempt':
        from django.contrib.sessions.backends.db import SessionStore
        session = SessionStore(session_key=old[0]['value'])
        state = dict(session['account_email_verification_code'])
        state['failed_attempts'] = 2
        session['account_email_verification_code'] = state
        session.save()
        with sqlite3.connect(work / 'new-data/sjtuow.sqlite3') as db:
            db.execute("UPDATE email_codes SET attempts=2 WHERE purpose='signup' AND email_norm=?", (email,))
            db.execute("UPDATE account_code_flows SET attempts=2 WHERE purpose='signup' AND email_norm=?", (email,))
    return old, new, suffix


def submit(tools, name, evaluate, is_new):
    page = SCENARIOS[name][0]
    fields = SCENARIOS[name][2]
    tools.submissions.clear()
    if name.endswith('-expired'):
        # First load a live form, then let its server-side context expire before
        # the real POST. Expiring before GET only measures a redirect fixture.
        if is_new:
            purpose = 'signup' if page == 'confirm-email' else 'password_reset'
            with sqlite3.connect(_fixture['work'] / 'new-data/sjtuow.sqlite3') as db:
                db.execute('UPDATE email_codes SET expires_at=? WHERE purpose=? AND email_norm=?', ((datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(), purpose, _fixture['email']))
                db.execute('UPDATE account_code_flows SET expires_at=? WHERE purpose=? AND email_norm=?', ((datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(), purpose, _fixture['email']))
        else:
            from django.contrib.sessions.backends.db import SessionStore
            session = SessionStore(session_key=_fixture['old_session'])
            key = 'account_email_verification_code' if page == 'confirm-email' else 'account_password_reset_verification'
            state = dict(session[key]); state['at'] = time.time() - 3600
            session[key] = state; session.save()
    form_index = 1 if name in ('error-resend-limit','error-resend-cooldown') or (name == 'error-email-occupied' and not is_new) else 0
    if name.endswith('-limit') or name == 'error-resend-cooldown':
        endpoint = '/api/auth/resend-code' if name in ('error-resend-limit','error-resend-cooldown') and is_new else (API_PATHS[page] if is_new else PATHS[page])
        # Saturate the actual server bucket, never write counters or lower limits.
        prime = {'email': 'member@screens.test', 'password': 'Wrong!Orbit829'} if page == 'login' else {'email': 'pending@screens.test' if page == 'confirm-email' else 'member@screens.test'}
        if page == 'signup':
            prime = {'email': 'limited@example.test', 'nickname': '限流新人', 'password': 'abc', 'confirm_password': 'abc', 'is_sjtu': True, 'agree_terms': True, 'agree_cross_border': True}
        hit = evaluate(tools, f"""(async()=>{{
          const form=document.querySelectorAll('#main form')[{form_index}];
          if(!form)throw new Error('missing rate-limit form');
          let code=0;
          for(let i=0;i<40;i++){{
            const oldBody=new URLSearchParams(new FormData(form));
            for(const [key,value] of Object.entries({json.dumps(SCENARIOS[name][2])}))oldBody.set(key,String(value));
            if({json.dumps(name)}==='error-resend-limit'||{json.dumps(name)}==='error-resend-cooldown')oldBody.set('action','resend');
            const response=await fetch({json.dumps(endpoint)},{{method:'POST',headers:{{'Content-Type':{json.dumps('application/json' if is_new else 'application/x-www-form-urlencoded')}}},body:{json.dumps(json.dumps(prime)) if is_new else 'oldBody'},redirect:'manual'}});
            code=response.status;if(code===429)return true;
          }}
          throw new Error('real rate bucket did not reach429, last='+code);
        }})()""")
        if not hit:
            raise RuntimeError('rate saturation failed')
        tools.submissions.clear()
    evaluate(tools, f'''(() => {{
      const form=document.querySelectorAll('#main form')[{form_index}];
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
    navigation_outcomes = {
        'error-email-expired': '/accounts/login/',
        'error-email-third-attempt': '/accounts/login/',
        'error-reset-expired': '/accounts/login/',
        'error-signup-existing': '/accounts/confirm-email/',
    }
    navigated = False
    for _ in range(120):
        try:
            ready = evaluate(tools, "Boolean(document.readyState==='complete' && document.querySelector('#main .c-field__error') && !document.querySelector('#main button[type=submit]')?.disabled)")
            current_path = evaluate(tools, "location.pathname")
        except RuntimeError as failure:
            if name in navigation_outcomes and 'navigated or closed' in str(failure):
                time.sleep(0.05)
                continue
            raise
        if navigation_outcomes.get(name) == current_path:
            # The real old and new flows deliberately leave the rejected form:
            # expired/closed codes go to login; signup enumeration proceeds to
            # the same confirmation page as a new address. The navigation is
            # stronger evidence than an inline error node.
            response = {'path': 'navigation:' + current_path, 'status': 0}
            navigated = True
            break
        responses = [r for r in tools.submissions if r['path'] in (PATHS[page], '/api/auth/resend-code' if name in ('error-resend-limit','error-resend-cooldown') else API_PATHS[page])]
        if (ready or name.endswith('-expired') or name == 'error-email-third-attempt' or name.endswith('-limit') or name == 'error-resend-cooldown' or name == 'error-signup-existing') and responses:
            response = responses[-1]
            expected = (422 if is_new else 302) if name.endswith('-expired') or name == 'error-email-third-attempt' else 429 if name.endswith('-limit') or name == 'error-resend-cooldown' else (200 if name == 'error-signup-existing' and is_new else 302 if name == 'error-signup-existing' else (200 if response['path'] == PATHS[page] else (401 if page == 'login' else 422)))
            if response['status'] != expected:
                raise RuntimeError(f"unexpected rejected-form response for {name}: {response}")
            break
        time.sleep(0.05)
    else:
        state = evaluate(tools, "JSON.stringify({path:location.pathname+location.search,text:(document.querySelector('#main')||document.body).innerText.slice(0,500)})")
        raise RuntimeError('real invalid form did not produce an error: ' + name + ' submissions=' + repr(tools.submissions) + ' state=' + str(state))
    if navigated:
        stable = 0
        for _ in range(120):
            try:
                complete = evaluate(tools, "document.readyState==='complete' && location.pathname===" + json.dumps(navigation_outcomes[name]))
                stable = stable + 1 if complete else 0
                if stable >= 2: break
            except RuntimeError as failure:
                if 'navigated or closed' not in str(failure): raise
                stable = 0
            time.sleep(0.05)
        else:
            raise RuntimeError('account navigation did not settle: ' + name)
    if not navigated:
        evaluate(tools, "document.fonts.ready.then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))")
    # Response metadata only: never store passwords, codes, cookies or bodies.
    return response

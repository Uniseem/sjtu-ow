"""Fixed old-template references for cards and layouts, on the test machine."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','sjtu_ow.settings.dev')
import django
django.setup()
from django.template import Context, Engine, engines
from django.template.loader import render_to_string
from core import placeholders
from core.models import SiteSettings
from content.models import ArticlePage, ArticleCategory
from accounts.models import User

cases=[]
def add(component,path,props,context,**more):
    cases.append(dict(component=component,props=props,html=render_to_string(path,{**context,'avatar_pool':[],'cover_pool':[]}),**more))
date='2026-10-10T20:30:00+00:00'
dt=datetime.fromisoformat(date)
# Wagtail pageurl checks Page identity before calling get_url. Use the actual
# unsaved model; only URL resolution is mocked to avoid querying a page tree.
for author, summary, pinned in [(True,True,True),(False,False,False),(True,False,False)]:
    a=ArticlePage(pk=37,content_type_id=1,title='周末回顾',slug='weekend',category=ArticleCategory(name='战报'),summary='一场内战',cover=None,author=User(pk=2,nickname='小满',is_active=True) if author else None,body_minutes=4,first_published_at=dt)
    article=dict(id=37,slug='weekend',title=a.title,category_name='战报',summary=a.summary,reading_time=4,first_published_at=date)
    if author: article['author']={'id':2,'nickname':'小满','is_active':True}
    with patch.object(ArticlePage,'get_url',return_value='/news/weekend/'):
        add('PostCard','components/post_card.html',{'article':article,'summary':summary,'pinned':pinned},{'article':a,'summary':summary,'pinned':pinned})
for recruiting,show_closed,about,capacity in [(True,False,True,12),(False,True,False,0),(False,False,True,0)]:
    t=NS(pk=7,name='思源',logo=None,member_count=6,created_at=dt,description='周末一起打',is_recruiting=recruiting,wanted_roles=[('tank','坦克'),('support','支援')],get_absolute_url='/teams/7/')
    team=dict(id=7,name=t.name,member_count=6,created_at=date,description=t.description,is_recruiting=recruiting,wanted_roles=['tank','support'])
    add('TeamTile','components/team_tile.html',dict(team=team,about=about,showClosed=show_closed,capacity=capacity),dict(team=t,about=about,show_closed=show_closed,capacity=capacity))
for status,opened in [('published',True),('published',False),('finished',True),('cancelled',True)]:
    scrim=NS(pk=8,title='周末内战',starts_at=dt,get_format_display='角色限定 5v5',players_needed=10,status=status,signup_open=opened)
    display=dict(id=8,title=scrim.title,starts_at=date,format_label=scrim.get_format_display,players_needed=10,status=status,signup_open=opened)
    add('CScrimRow','components/scrim_row.html',dict(scrim=display,signups=12),dict(scrim=scrim,signups=12))
for phase in ['open','upcoming','cancelled','finished','closed']:
    for individuals in [False,True]:
        t=NS(pk=7,title='秋季赛',cover=None,phase=phase,starts_at=dt,registration_closes_at=dt,registration_opens_at=dt,roster_min=5,roster_max=7,takes_individuals=individuals,get_registration_mode_display='个人报名' if individuals else '整队报名',sjtu_only=True,get_absolute_url='/tournaments/7/',_meta=NS(label_lower='tournaments.tournament'))
        display=dict(id=7,title=t.title,phase=phase,starts_at=date,registration_closes_at=date,registration_opens_at=date,roster_min=5,roster_max=7,takes_individuals=individuals,registration_mode_label=t.get_registration_mode_display,sjtu_only=True)
        add('CTournamentCard','components/tournament_card.html',dict(tournament=display,approved=0),dict(tournament=t,approved=0))
for date_value in [dt,None]:
    add('CStartsAt','tournaments/_starts_at.html',dict(startsAt=date if date_value else None),dict(tournament=NS(starts_at=date_value)))
add('CTeamLogo','teams/_logo.html',dict(team=dict(id=7,name='思源')),dict(team=NS(pk=7,name='思源',logo=None)))
for section in placeholders.SECTION_SCENES:
    site=NS(**{('hero_image' if section=='home' else 'banner_'+section):None})
    with patch.object(SiteSettings,'load',return_value=site):
        add('CPagehead','components/pagehead_picture.html',dict(section=section),dict(section=section))
add('AuthWhy','account/_why.html',{}, {})
add('AuthBack','account/_back_to_security.html',dict(here='修改密码'),dict(here='修改密码'))
# Real layout templates inherit a minimal base, avoiding unrelated font and
# setting queries while keeping their content block exactly as it is.
real=engines['django'].engine
engine=Engine(dirs=[ROOT/'templates'],loaders=[('django.template.loaders.locmem.Loader',{'base.html':'<main id="main" class="flex-1">{% block content %}{% endblock %}</main>'}),'django.template.loaders.filesystem.Loader','django.template.loaders.app_directories.Loader'],libraries=real.libraries,builtins=real.builtins)
for why in [False,True]:
    aside="{% include 'account/_why.html' %}" if why else ''
    old=engine.from_string("{% extends 'account/layout.html' %}{% block account_content %}<h1>登录</h1>{% endblock %}{% block account_aside %}"+aside+"{% endblock %}").render(Context({}))
    cases.append(dict(component='AuthLayout',props=dict(why=why),html=old,control='<h1>登录</h1>'))
for waiting,gaps in [(0,[]),(2,[('游戏 ID','me_game_accounts','填一个游戏 ID')])]:
    me_nav=[('me_profile','基本资料',True,'user'),('me_contacts','联系方式',False,'phone')]
    context=dict(request=NS(user=NS(pk=2,nickname='小满',is_active=True,avatar_id=None)),avatar_pool=[],me_nav=me_nav,current_me='me_profile',profile_gaps=gaps)
    with patch('core.outbox.waiting_count',return_value=waiting):
        old=engine.from_string("{% extends 'me/base.html' %}{% block me_content %}<p>资料</p>{% endblock %}").render(Context(context))
    props=dict(title='个人中心',user=dict(id=2,nickname='小满',is_active=True),current='/me/',nav=[dict(href='/me/',label='基本资料',available=True,icon='user'),dict(href='/me/contacts/',label='联系方式',available=False,icon='phone')],waiting=waiting,gaps=[dict(label=x[0],href='/me/game-accounts/',hint=x[2]) for x in gaps])
    cases.append(dict(component='MeLayout',props=props,html=old,control='<p>资料</p>'))
output=ROOT/'web/apps/site/src/testdata/legacy-cards.json'
output.write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n')
print(f'LEGACY-CARD-FIXTURES {len(cases)}')
print('SECTION-PATHS',json.dumps({s:placeholders.section_paths(s) for s in placeholders.SECTION_SCENES}))

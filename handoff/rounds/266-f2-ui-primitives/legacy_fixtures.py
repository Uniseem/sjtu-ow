"""Render old components with fixed data; no database reads or mutations.
Run on the test machine via remote-check, then copy the JSON back.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sjtu_ow.settings.dev")
import django

django.setup()
from django import forms
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.utils import timezone

cases = []

def add(component, template, props, context, **more):
    cases.append({"component": component, "props": props, "html": render_to_string(
        f"components/{template}.html", context), **more})

for props in [{}, {"title": "还没有战队", "message": "第一支战队可以由你来建。", "actionUrl": "/teams/new/", "actionLabel": "创建战队"}, {"title": "<script>"}, {"actionUrl": "/teams/new/"}]:
    add("CEmpty", "empty_state", props, {"title": props.get("title"), "message": props.get("message"), "action_url": props.get("actionUrl"), "action_label": props.get("actionLabel")})
for label in ["", "未定级", "钻石 3", "前 500", "宗师", "大师 1"]:
    add("CRank", "rank_badge", {"label": label}, {"label": label})
for kind in ["live", "ok", "warn", "info", "done", "off", "rejected", "success", "warning", "error", "neutral", "primary"]:
    add("CStatus", "status_badge", {"kind": kind, "label": "状态"}, {"kind": kind, "label": "状态"})
for status, label in [("approved", "已通过"), ("pending", "待审核"), ("rejected", "已驳回"), ("withdrawn", "已撤销")]:
    add("CRegStatus", "registration_status", {"status": status, "label": label}, {"registration": NS(status=status, get_status_display=lambda: label)})
for got, total in [(0,0), (8,10), (12,10), (-3,10), (25,50), (1,48), (3,48), (75,100)]:
    add("CSeats", "seats", {"taken": got, "total": total}, {"taken": got, "total": total})
for mask in range(8):
    props = dict(tank=bool(mask&1), damage=bool(mask&2), support=bool(mask&4))
    add("CRoleIcon", "role_icons", props, {"role_"+k: v for k,v in props.items()})
for number, count, query in [(1,1,""), (1,7,""), (4,7,"category=2&q=x%26y"), (7,7,"q=%E6%88%AA%E5%9B%BE")]:
    add("CPager", "pagination", {"page": number, "pages": count, "extraQuery": query}, {"page_obj": Paginator(list(range(count)),1).page(number), "extra_query":query})
for gaps in [[], [{"label":"游戏 ID", "href":"/me/game-accounts/"},{"label":"联系方式", "href":"/me/contacts/"}]]:
    ctx = [(g["label"], "me_game_accounts" if i==0 else "me_contacts", "") for i,g in enumerate(gaps)]
    add("CProfileGaps", "profile_gap_links", {"gaps":gaps}, {"profile_gaps":ctx})
for name, size, plain, active in [("· 小翼", "",False,True), ("wyrm","xs",False,True), ("🌫️","lg",False,False),("小满","sm",True,True)]:
    props={"person":{"id":7,"nickname":name,"is_active":active},"plain":plain}
    if size: props["size"]=size
    add("CAvatar", "avatar", props,{"person":NS(pk=7,nickname=name,is_active=active,avatar_id=None),"size":size,"plain":plain,"avatar_pool":[]})
for flex, compact, has_rank, empty in [(False,False,True,False),(True,False,True,False),(True,True,True,False),(False,False,False,True),(False,False,False,False)]:
    roles=[] if empty else [{"code":"support","label":"支援","main":True},{"code":"tank","label":"坦克","main":False},{"code":"damage","label":"输出","main":False}]
    rank={"label":"钻石 3","role_label":"支援","stale":True,"updated_at":"2026-03-01T20:30:00Z"} if has_rank else None
    old_rank=NS(**{**rank,"updated_at":datetime.fromisoformat(rank["updated_at"])}) if rank else None
    profile=NS(roles=roles, main_rank=old_rank,is_flex=flex,main_role="support" if roles else "",role_items=[(r["code"],r["label"],r["main"]) for r in roles])
    add("CPlay", "play_style", {"profile":{"roles":roles,"is_flex":flex,"main_rank":rank},"compact":compact}, {"profile":profile,"compact":compact})
class Sample(forms.Form):
    name=forms.CharField(label="队名",help_text="只填写队名。",max_length=16)
    consent=forms.BooleanField(label="我已阅读并同意",help_text="请先阅读规则。")
    roles=forms.MultipleChoiceField(label="位置",choices=[("tank","坦克"),("support","支援")],widget=forms.CheckboxSelectMultiple)
for field_name, kind in [("name","control"),("consent","checkbox"),("roles","group")]:
    form=Sample(data={})
    field=form[field_name]
    add("CField", "form_field", {"label":field.label,"inputId":field.id_for_label,"required":field.field.required,"kind":kind,"errors":list(field.errors)}, {"field":field}, control=str(field), help=field.help_text)
output=ROOT / "web/apps/site/src/testdata/legacy-ui.json"
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps(cases,ensure_ascii=False,indent=2)+"\n")
print(f"LEGACY-UI-FIXTURES {len(cases)} → {output}")

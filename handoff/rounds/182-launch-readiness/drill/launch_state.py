import json, os
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from accounts.models import User
from core.admin_setup import setup_checks
from core.models import SiteSettings

print("== 上线清单")
for c in setup_checks():
    print(("  OK  " if c.done else "  --  ") + ("[必做] " if c.required else "[建议] ") + c.label + "：" + (c.detail or ""))
print("== 账号")
print("  超级管理员:", User.objects.filter(is_superuser=True, is_active=True).count(),
      " 用户总数:", User.objects.count(),
      " demo.example.com 邮箱:", User.objects.filter(email__endswith="demo.example.com").count())
print("== 环境")
for key in ("TEST_ENVIRONMENT", "PRERENDER_ENABLED", "SITE_URL", "DEBUG"):
    print(" ", key, "=", getattr(settings, key, None))
print("  MODERATION_API_KEY 设置了:", bool(getattr(settings, "MODERATION_API_KEY", "")))
print("  BACKUP_ENCRYPTION_KEY 设置了:", bool(getattr(settings, "BACKUP_ENCRYPTION_KEY", "")))
from core.dbfile import database_path
db = database_path()
print("  数据库:", db, round(db.stat().st_size / 1024 / 1024, 1), "MB")
media = Path(settings.MEDIA_ROOT)
size = sum(p.stat().st_size for p in media.rglob("*") if p.is_file())
print("  media:", round(size / 1024 / 1024, 1), "MB")

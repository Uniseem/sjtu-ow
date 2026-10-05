"""AI review's provider settings move into 全站设置 (design 5.5.3, v7.1).

The user, 10-05: 「把 ai 的设置也放到后台去，我不想改什么 env，只想在后台改」.
Until now they were environment variables; whatever a server had set is
carried into the settings row here, and the site stops reading them.
"""

import json
import os

import core.fields
from django.db import migrations, models


def from_environment(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    env = os.environ
    for row in SiteSettings.objects.all():
        changed = []
        if env.get("MODERATION_API_KEY") and not row.moderation_api_key:
            row.moderation_api_key = env["MODERATION_API_KEY"]
            changed.append("moderation_api_key")
        if env.get("MODERATION_BASE_URL") and not row.moderation_base_url:
            row.moderation_base_url = env["MODERATION_BASE_URL"]
            changed.append("moderation_base_url")
        try:
            extra = json.loads(env.get("MODERATION_EXTRA_BODY") or "{}")
        except ValueError:
            extra = {}
        if isinstance(extra, dict) and extra and not row.moderation_extra_body:
            row.moderation_extra_body = extra
            changed.append("moderation_extra_body")
        for name, field in (
            ("MODERATION_TIMEOUT", "moderation_timeout"),
            ("MODERATION_MAX_OUTPUT_TOKENS", "moderation_max_output_tokens"),
        ):
            value = (env.get(name) or "").strip()
            if value.isdigit() and int(value) > 0:
                setattr(row, field, int(value))
                changed.append(field)
        if changed:
            row.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0020_ai_patrol"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="moderation_api_key",
            field=core.fields.EncryptedTextField(
                blank=True,
                help_text="服务商给的 API Key，加密存储。留空表示不修改已保存的密钥。",
                verbose_name="接口密钥",
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="moderation_base_url",
            field=models.URLField(
                blank=True,
                help_text="空着用 DeepSeek（https://api.deepseek.com/v1）。换服务商、用聚合平台或自建服务时填它的 OpenAI 兼容地址，一般以 /v1 结尾。",
                verbose_name="接口地址",
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="moderation_extra_body",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="一段 JSON，原样并进每次请求，比如关闭思考模式的参数（各家写法不一样，照服务商的文档填）。不知道就空着。",
                verbose_name="附加请求参数",
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="moderation_max_output_tokens",
            field=models.PositiveIntegerField(
                default=600,
                help_text="一次调用最多让模型写多少，几百就够。",
                verbose_name="最多输出 token",
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="moderation_timeout",
            field=models.PositiveIntegerField(
                default=30, help_text="一次调用最多等多久。", verbose_name="超时（秒）"
            ),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="moderation_enabled",
            field=models.BooleanField(
                default=True,
                help_text="关掉后新内容不再送审。没有填接口密钥（或接口地址）时本来就不送审。",
                verbose_name="启用 AI 内容审核",
            ),
        ),
        migrations.RunPython(from_environment, migrations.RunPython.noop),
    ]

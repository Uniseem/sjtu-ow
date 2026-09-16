"""Site-wide models.

SiteSettings, game modes, fonts, and prerender records are added in M1/M2.
"""

from django.db import models


class HealthProbe(models.Model):
    """Dedicated table for /healthz write probes (design 16.6). Rows are rolled back."""

    token = models.CharField(max_length=32)

    class Meta:
        verbose_name = "健康检查探针"
        verbose_name_plural = "健康检查探针"

"""API endpoints that exist from round 017 (design 11.7.5)."""

from __future__ import annotations

from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAdminUser

from integrations.api import SignedApiView, data_response, isoformat


class PingView(SignedApiView):
    """Connectivity check: any valid client may call it (design 11.7.5)."""

    required_scope = None

    @extend_schema(
        responses={200: OpenApiTypes.OBJECT},
        description="确认密钥和签名算法是否正确，以及双方服务器的时间差。",
    )
    def get(self, request):
        client = request.api_client
        return data_response(
            {
                "client": client.name,
                "scopes": list(client.scopes or []),
                "allowed_includes": list(client.allowed_includes or []),
                "server_time": isoformat(timezone.now()),
            }
        )


class SuperuserOnlyMixin:
    """Design 11.11: only a signed-in superuser may read the API docs."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAdminUser]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.is_superuser:
            raise PermissionDenied("只有超级管理员可以查看接口文档。")


class ApiSchemaView(SuperuserOnlyMixin, SpectacularAPIView):
    pass


class ApiDocsView(SuperuserOnlyMixin, SpectacularSwaggerView):
    url_name = "api:schema"

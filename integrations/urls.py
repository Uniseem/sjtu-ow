from django.urls import path

from integrations import views

app_name = "api"

urlpatterns = [
    path("ping", views.PingView.as_view(), name="ping"),
]

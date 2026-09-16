from django.urls import path

from lfg import views

urlpatterns = [
    path("lfg/", views.lfg_index, name="lfg_index"),
    path("lfg/new/", views.lfg_create, name="lfg_create"),
    path("lfg/<int:pk>/edit/", views.lfg_edit, name="lfg_edit"),
    path("lfg/<int:pk>/status/", views.lfg_status, name="lfg_status"),
    path("_fragments/lfg/", views.lfg_list, name="lfg_list"),
]

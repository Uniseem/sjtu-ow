from django.urls import path

from members import views

urlpatterns = [
    path("members/", views.members_index, name="members"),
    path("members/<id:pk>/", views.member_detail, name="member_detail"),
]

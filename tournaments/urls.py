from django.urls import path

from tournaments import views

urlpatterns = [
    path("tournaments/", views.tournament_index, name="tournament_index"),
    path("tournaments/<int:pk>/", views.tournament_detail, name="tournament_detail"),
]

from django.urls import path

from accounts import views

urlpatterns = [
    path("me/", views.me_profile, name="me_profile"),
    path("me/game-accounts/", views.me_game_accounts, name="me_game_accounts"),
    path(
        "me/game-accounts/<int:pk>/",
        views.me_game_account_edit,
        name="me_game_account_edit",
    ),
    path(
        "me/game-accounts/<int:pk>/delete/",
        views.me_game_account_delete,
        name="me_game_account_delete",
    ),
    path("me/contacts/", views.me_contacts, name="me_contacts"),
    path(
        "me/contacts/<int:pk>/",
        views.me_contact_edit,
        name="me_contact_edit",
    ),
    path(
        "me/contacts/<int:pk>/delete/",
        views.me_contact_delete,
        name="me_contact_delete",
    ),
    path("me/security/", views.me_security, name="me_security"),
]

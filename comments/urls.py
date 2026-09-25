from django.urls import path

from comments import views

urlpatterns = [
    path("comments/<int:page_pk>/new/", views.create, name="comment_create"),
    path("comments/<int:page_pk>/more/", views.more, name="comment_more"),
    path("comments/<int:pk>/reply/", views.reply, name="comment_reply"),
    path("comments/<int:pk>/hide/", views.hide, name="comment_hide"),
    path("comments/<int:pk>/unhide/", views.unhide, name="comment_unhide"),
    path("comments/<int:pk>/like/", views.like, name="comment_like"),
    path("comments/<int:pk>/edit/", views.edit, name="comment_edit"),
    path("comments/<int:pk>/delete/", views.delete, name="comment_delete"),
    path("comments/<int:pk>/pin/", views.pin, name="comment_pin"),
    path("comments/<int:pk>/unpin/", views.unpin, name="comment_unpin"),
]

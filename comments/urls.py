from django.urls import path

from comments import views

urlpatterns = [
    path("comments/<id:page_pk>/new/", views.create, name="comment_create"),
    path("comments/<id:page_pk>/more/", views.more, name="comment_more"),
    path("comments/<id:pk>/reply/", views.reply, name="comment_reply"),
    path("comments/<id:pk>/hide/", views.hide, name="comment_hide"),
    path("comments/<id:pk>/unhide/", views.unhide, name="comment_unhide"),
    path("comments/<id:pk>/like/", views.like, name="comment_like"),
    path("comments/<id:pk>/edit/", views.edit, name="comment_edit"),
    path("comments/<id:pk>/delete/", views.delete, name="comment_delete"),
    path("comments/<id:pk>/pin/", views.pin, name="comment_pin"),
    path("comments/<id:pk>/unpin/", views.unpin, name="comment_unpin"),
]

from django.urls import path

from comments import views

urlpatterns = [
    path("comments/<int:page_pk>/new/", views.create, name="comment_create"),
    path("comments/<int:page_pk>/more/", views.more, name="comment_more"),
    path("comments/<int:pk>/reply/", views.reply, name="comment_reply"),
    path("comments/<int:pk>/hide/", views.hide, name="comment_hide"),
    path("comments/<int:pk>/unhide/", views.unhide, name="comment_unhide"),
]

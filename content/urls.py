from django.urls import path

from content import views

urlpatterns = [
    path("sitemap.xml", views.sitemap_xml, name="sitemap"),
    path("robots.txt", views.robots_txt, name="robots"),
]

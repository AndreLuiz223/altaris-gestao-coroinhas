import os

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

ADMIN_URL = os.environ.get("ADMIN_URL", "gestao-altaris/")

urlpatterns = [
    path(ADMIN_URL, admin.site.urls),
    path("entrar/", auth_views.LoginView.as_view(), name="login"),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("escala.urls")),
]

handler404 = "django.views.defaults.page_not_found"

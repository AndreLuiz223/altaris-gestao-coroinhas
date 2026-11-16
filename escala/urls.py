from django.urls import path

from . import views

urlpatterns = [
    path("", views.painel, name="painel"),
    path("servidores/", views.servidores, name="servidores"),
    path("servidores/novo/", views.servidor_form, name="servidor_novo"),
    path("servidores/<int:pk>/", views.servidor_form, name="servidor_editar"),
]

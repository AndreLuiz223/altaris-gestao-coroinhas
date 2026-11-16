from django.urls import path

from . import views

urlpatterns = [
    path("", views.painel, name="painel"),
    path("escalas/<int:pk>/", views.montar_escala, name="montar_escala"),
    path("escalas/<int:pk>/atribuir/", views.atribuir, name="atribuir"),
    path("escalas/<int:pk>/copiar/", views.copiar, name="copiar_escala"),
    path("escalas/<int:pk>/remover/", views.remover, name="remover"),
    path("escalas/<int:pk>/publicar/", views.publicar, name="publicar"),
    path("escalas/<int:pk>/resultado/", views.resultado_escala, name="resultado_escala"),
    path("e/<str:token>/", views.escala_publica, name="escala_publica"),
    path("servidores/", views.servidores, name="servidores"),
    path("servidores/novo/", views.servidor_form, name="servidor_novo"),
    path("servidores/<int:pk>/", views.servidor_form, name="servidor_editar"),
    path("tunicas/", views.tunicas, name="tunicas"),
    path("tunicas/nova/", views.tunica_nova, name="tunica_nova"),
    path("tunicas/<int:pk>/pagamento/", views.pagamento_novo, name="pagamento_novo"),
]

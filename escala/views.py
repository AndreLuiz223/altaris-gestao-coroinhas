from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ServidorForm
from .models import Celebracao, Servidor


@login_required
def painel(request):
    """Tela 1 – próximas celebrações com o estado da escala."""
    agora = timezone.now() - timezone.timedelta(hours=3)
    celebracoes = (Celebracao.objects.filter(data_hora_inicio__gte=agora)
                   .select_related("comunidade").prefetch_related("atribuicoes")[:20])
    return render(request, "escala/painel.html", {"celebracoes": celebracoes})


@login_required
def servidores(request):
    lista = Servidor.objects.select_related("comunidade").exclude(status=Servidor.Status.DESLIGADO)
    return render(request, "escala/servidores.html", {"servidores": lista})


@login_required
def servidor_form(request, pk=None):
    instancia = get_object_or_404(Servidor, pk=pk) if pk else None
    form = ServidorForm(request.POST or None, instance=instancia)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Servidor salvo.")
        return redirect("servidores")
    return render(request, "escala/servidor_form.html", {"form": form, "instancia": instancia})

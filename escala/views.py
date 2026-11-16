from django.contrib import messages
from django.contrib.auth.decorators import login_required
from urllib.parse import urlencode

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .forms import PagamentoForm, ServidorForm, TunicaForm
from .models import Celebracao, Funcao, Servidor, Tunica


@login_required
def painel(request):
    """Tela 1 – próximas celebrações com o estado da escala."""
    agora = timezone.now() - timezone.timedelta(hours=3)
    celebracoes = (Celebracao.objects.filter(data_hora_inicio__gte=agora)
                   .select_related("comunidade").prefetch_related("atribuicoes")[:20])
    return render(request, "escala/painel.html", {"celebracoes": celebracoes})


@login_required
def montar_escala(request, pk):
    """Tela 2 – funções da celebração; com ?funcao= mostra a lista sugerida (RF02)."""
    celebracao = get_object_or_404(Celebracao.objects.select_related("comunidade"), pk=pk)
    funcao = request.GET.get("funcao")
    sugestoes = None
    funcao_label = None
    if funcao in Funcao.values:
        sugestoes = services.sugerir_servidores(celebracao, funcao)
        funcao_label = Funcao(funcao).label
    linhas = services.linhas_da_escala(celebracao)
    preenchidas = sum(1 for _, _, a in linhas if a)
    proxima = next((valor for valor, _, a in linhas if not a), None)
    return render(request, "escala/montar.html", {
        "celebracao": celebracao,
        "linhas": linhas,
        "preenchidas": preenchidas,
        "total_funcoes": len(linhas),
        "proxima": proxima,
        "anterior": services.escala_anterior(celebracao) if preenchidas < len(linhas) else None,
        "avisos": services.avisos_da_escala(celebracao),
        "funcao": funcao if funcao_label else None,
        "funcao_label": funcao_label,
        "sugestoes": sugestoes,
    })


@login_required
@require_POST
def atribuir(request, pk):
    """RF03 – grava a atribuição ou mostra o alerta de conflito."""
    celebracao = get_object_or_404(Celebracao, pk=pk)
    funcao = request.POST.get("funcao", "")
    servidor = get_object_or_404(Servidor, pk=request.POST.get("servidor"))
    try:
        services.atribuir(celebracao, funcao, servidor, request.user)
        messages.success(request, f"{servidor.nome} escalado(a) em {Funcao(funcao).label}.")
    except services.RegraEscalaError as erro:
        messages.error(request, str(erro))
        url = reverse("montar_escala", args=[pk])
        if funcao in Funcao.values:
            url += "?" + urlencode({"funcao": funcao})
        return redirect(url)
    return redirect("montar_escala", pk=pk)


@login_required
@require_POST
def copiar(request, pk):
    """Ajuste da validação 1 – reaproveitar a escala anterior da mesma comunidade."""
    celebracao = get_object_or_404(Celebracao, pk=pk)
    origem = get_object_or_404(Celebracao, pk=request.POST.get("origem"))
    try:
        copiadas, avisos = services.copiar_escala(celebracao, origem, request.user)
    except services.RegraEscalaError as erro:
        messages.error(request, str(erro))
        return redirect("montar_escala", pk=pk)
    messages.success(request, f"{copiadas} função(ões) copiada(s) da escala de "
                              f"{origem.data_hora_inicio:%d/%m}. Confira e ajuste se precisar.")
    for aviso in avisos:
        messages.warning(request, aviso)
    return redirect("montar_escala", pk=pk)


@login_required
@require_POST
def remover(request, pk):
    celebracao = get_object_or_404(Celebracao, pk=pk)
    services.remover_atribuicao(celebracao, request.POST.get("funcao", ""))
    messages.info(request, "Função liberada.")
    return redirect("montar_escala", pk=pk)


@login_required
@require_POST
def publicar(request, pk):
    """RF04 – publica e mostra o link para o WhatsApp (Tela 3)."""
    celebracao = get_object_or_404(Celebracao, pk=pk)
    services.publicar(celebracao)
    messages.success(request, "Escala publicada! Envie o link para os servidores.")
    return redirect("resultado_escala", pk=pk)


@login_required
def resultado_escala(request, pk):
    celebracao = get_object_or_404(Celebracao.objects.select_related("comunidade"), pk=pk)
    link = request.build_absolute_uri(f"/e/{celebracao.token_publico}/") if celebracao.token_publico else None
    return render(request, "escala/resultado.html", {
        "celebracao": celebracao,
        "linhas": services.linhas_da_escala(celebracao),
        "avisos": services.avisos_da_escala(celebracao),
        "link": link,
    })


def escala_publica(request, token):
    """Página pública somente leitura – sem dados de contato (RNF02)."""
    celebracao = get_object_or_404(Celebracao.objects.select_related("comunidade"),
                                   token_publico=token, publicada=True)
    return render(request, "escala/publica.html", {
        "celebracao": celebracao,
        "linhas": services.linhas_da_escala(celebracao),
    })


# ---------- RF01: servidores ----------

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


# ---------- RF05: túnicas ----------

@login_required
def tunicas(request):
    lista = Tunica.objects.select_related("servidor").prefetch_related("pagamentos")
    return render(request, "escala/tunicas.html", {"tunicas": lista, "caixa": services.resumo_caixa()})


@login_required
def tunica_nova(request):
    form = TunicaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Túnica registrada.")
        return redirect("tunicas")
    return render(request, "escala/form_simples.html", {"form": form, "titulo": "Nova túnica"})


@login_required
def pagamento_novo(request, pk):
    tunica = get_object_or_404(Tunica, pk=pk)
    form = PagamentoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.registrar_pagamento(tunica, form.cleaned_data["valor"], form.cleaned_data["forma"],
                                         form.cleaned_data["data_pagamento"], request.user)
            messages.success(request, "Pagamento registrado.")
            return redirect("tunicas")
        except services.RegraEscalaError as erro:
            form.add_error("valor", str(erro))
    return render(request, "escala/form_simples.html",
                  {"form": form, "titulo": f"Pagamento – {tunica}"})

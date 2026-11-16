"""
Regras de negócio do ALTARIS (camada de serviços).

Mantidas fora das Views para poderem ser testadas isoladamente (EP2 - arquitetura).
"""
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import Atribuicao, Celebracao, FUNCOES_PADRAO, Funcao, PagamentoTunica, Servidor, Tunica


class RegraEscalaError(Exception):
    """Violação de uma regra da escala, com mensagem amigável para a coordenação."""


@dataclass
class Sugestao:
    servidor: Servidor
    vezes_no_mes: int


def _celebracoes_sobrepostas(celebracao):
    """Celebrações (de qualquer comunidade) cujo horário se sobrepõe ao desta, exceto ela mesma."""
    janela = timedelta(hours=12)
    candidatas = Celebracao.objects.exclude(pk=celebracao.pk).filter(
        data_hora_inicio__gt=celebracao.data_hora_inicio - janela,
        data_hora_inicio__lt=celebracao.data_hora_fim,
    )
    return [c for c in candidatas
            if c.data_hora_inicio < celebracao.data_hora_fim and celebracao.data_hora_inicio < c.data_hora_fim]


def servidores_ocupados(celebracao):
    """IDs de servidores já escalados nesta celebração ou em outra com horário sobreposto."""
    ids = set(celebracao.atribuicoes.values_list("servidor_id", flat=True))
    sobrepostas = _celebracoes_sobrepostas(celebracao)
    if sobrepostas:
        ids |= set(Atribuicao.objects.filter(celebracao__in=sobrepostas).values_list("servidor_id", flat=True))
    return ids


def sugerir_servidores(celebracao, funcao=None):
    """RF02: servidores ativos da comunidade, livres no horário, ordenados por quem serviu menos no mês."""
    inicio = celebracao.data_hora_inicio
    ocupados = servidores_ocupados(celebracao)
    qs = (
        Servidor.objects.filter(comunidade=celebracao.comunidade, status=Servidor.Status.ATIVO)
        .exclude(pk__in=ocupados)
        .annotate(
            vezes=Count(
                "atribuicoes",
                filter=Q(
                    atribuicoes__celebracao__data_hora_inicio__year=inicio.year,
                    atribuicoes__celebracao__data_hora_inicio__month=inicio.month,
                ),
            )
        )
        .order_by("vezes", "nome")
    )
    return [Sugestao(servidor=s, vezes_no_mes=s.vezes) for s in qs]


def atribuir(celebracao, funcao, servidor, usuario=None):
    """RF03: cria a atribuição validando conflitos; levanta RegraEscalaError com mensagem clara."""
    if funcao not in Funcao.values:
        raise RegraEscalaError("Função inválida.")
    if servidor.status != Servidor.Status.ATIVO:
        raise RegraEscalaError(f"{servidor.nome} não está ativo e não pode ser escalado.")
    if servidor.comunidade_id != celebracao.comunidade_id:
        raise RegraEscalaError(f"{servidor.nome} não pertence à comunidade {celebracao.comunidade}.")

    existente = celebracao.atribuicoes.filter(servidor=servidor).first()
    if existente:
        raise RegraEscalaError(
            f"{servidor.nome} já está em {existente.get_funcao_display()} nesta missa. "
            f"Escolha outro servidor para {Funcao(funcao).label}."
        )
    for outra in _celebracoes_sobrepostas(celebracao):
        if outra.atribuicoes.filter(servidor=servidor).exists():
            raise RegraEscalaError(
                f"{servidor.nome} já está escalado em {outra.titulo} ({outra.comunidade}) "
                f"no mesmo horário. Escolha outro servidor."
            )

    try:
        with transaction.atomic():
            celebracao.atribuicoes.filter(funcao=funcao).delete()  # trocar servidor da função
            return Atribuicao.objects.create(
                celebracao=celebracao, funcao=funcao, servidor=servidor, criado_por=usuario
            )
    except IntegrityError as exc:  # garantia final do banco (acesso simultâneo)
        raise RegraEscalaError(f"{servidor.nome} já foi escalado nesta celebração.") from exc


def remover_atribuicao(celebracao, funcao):
    celebracao.atribuicoes.filter(funcao=funcao).delete()


def avisos_da_escala(celebracao):
    """Avisos não bloqueantes (ex.: nenhum experiente escalado)."""
    avisos = []
    atribs = list(celebracao.atribuicoes.select_related("servidor"))
    if celebracao.exige_experiente and atribs and not any(a.servidor.experiente for a in atribs):
        avisos.append("Nenhum servidor experiente escalado. Recomendado: pelo menos 1.")
    faltando = len(FUNCOES_PADRAO) - len(atribs)
    if faltando > 0:
        avisos.append(f"Ainda faltam {faltando} função(ões) sem servidor.")
    return avisos


def escala_anterior(celebracao):
    """Última celebração da mesma comunidade, antes desta, que já tem servidores escalados.

    Dá preferência a uma do mesmo dia da semana e horário (ex.: domingo 9h → domingo 9h).
    """
    anteriores = (
        Celebracao.objects.filter(comunidade=celebracao.comunidade,
                                  data_hora_inicio__lt=celebracao.data_hora_inicio)
        .annotate(n=Count("atribuicoes")).filter(n__gt=0)
        .order_by("-data_hora_inicio")
    )
    inicio = timezone.localtime(celebracao.data_hora_inicio)
    lista = list(anteriores[:20])
    for c in lista:
        quando = timezone.localtime(c.data_hora_inicio)
        if quando.weekday() == inicio.weekday() and quando.time() == inicio.time():
            return c
    return lista[0] if lista else None


def copiar_escala(destino, origem, usuario=None):
    """Ajuste da validação 1: reaproveita a escala de uma celebração anterior.

    Copia só as funções ainda vazias e reaplica TODAS as regras de atribuir() (servidor ativo,
    mesma comunidade, sem conflito de horário). Devolve (copiadas, avisos dos que ficaram de fora).
    """
    if origem.comunidade_id != destino.comunidade_id:
        raise RegraEscalaError("Só é possível copiar escalas da mesma comunidade.")
    preenchidas = set(destino.atribuicoes.values_list("funcao", flat=True))
    copiadas, avisos = 0, []
    for a in origem.atribuicoes.select_related("servidor").order_by("funcao"):
        if a.funcao in preenchidas:
            continue
        try:
            atribuir(destino, a.funcao, a.servidor, usuario)
            copiadas += 1
        except RegraEscalaError as erro:
            avisos.append(f"{a.get_funcao_display()}: {erro}")
    return copiadas, avisos


def linhas_da_escala(celebracao):
    """Lista de (funcao, label, atribuicao|None) na ordem padrão das funções."""
    por_funcao = {a.funcao: a for a in celebracao.atribuicoes.select_related("servidor")}
    return [(f.value, f.label, por_funcao.get(f.value)) for f in FUNCOES_PADRAO]


def publicar(celebracao):
    """RF04: publica a escala e garante o token público aleatório."""
    celebracao.publicar()
    return celebracao.token_publico


# ---------- RF05: túnicas e pagamentos ----------

def registrar_pagamento(tunica, valor, forma, data_pagamento, usuario=None, permitir_credito=False):
    valor = Decimal(valor)
    if valor <= 0:
        raise RegraEscalaError("O valor do pagamento deve ser maior que zero.")
    if not permitir_credito and tunica.total_pago + valor > tunica.valor_total:
        raise RegraEscalaError(
            f"O pagamento ultrapassa o saldo da túnica (saldo atual: R$ {tunica.saldo:.2f})."
        )
    parcela = tunica.pagamentos.count() + 1
    return PagamentoTunica.objects.create(
        tunica=tunica, valor=valor, forma=forma, data_pagamento=data_pagamento,
        parcela=parcela, registrado_por=usuario,
    )


def resumo_caixa():
    """Total devido, recebido e pendente de todas as túnicas (fechamento conferível)."""
    devido = Tunica.objects.aggregate(t=Sum("valor_total"))["t"] or Decimal("0.00")
    recebido = PagamentoTunica.objects.aggregate(t=Sum("valor"))["t"] or Decimal("0.00")
    return {"devido": devido, "recebido": recebido, "pendente": devido - recebido}

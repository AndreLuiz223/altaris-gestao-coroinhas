"""Testes unitários dos modelos e restrições do banco."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from escala.models import Celebracao, Comunidade, PagamentoTunica, Servidor, Tunica

pytestmark = pytest.mark.django_db


def test_str_e_propriedades(comunidade, celebracao, servidores):
    assert str(comunidade) == "Santa Rita de Cássia"
    assert str(servidores["ana"]) == "Ana B."
    assert servidores["ana"].experiente and not servidores["pedro"].experiente
    assert "Missa dominical" in str(celebracao)
    assert celebracao.data_hora_fim - celebracao.data_hora_inicio == timedelta(minutes=90)
    assert celebracao.total_funcoes == 8 and celebracao.preenchidas == 0


def test_menor_de_idade_exige_responsavel(comunidade):
    s = Servidor(comunidade=comunidade, nome="Sem Responsável", menor_de_idade=True)
    with pytest.raises(ValidationError):
        s.full_clean()


def test_servidor_duplicado_na_mesma_comunidade(comunidade, servidores):
    with pytest.raises(IntegrityError), transaction.atomic():
        Servidor.objects.create(comunidade=comunidade, nome="Ana B.", nome_responsavel="R")


def test_mesmo_nome_em_outra_comunidade_e_permitido(servidores, outra_comunidade):
    Servidor.objects.create(comunidade=outra_comunidade, nome="Ana B.", nome_responsavel="R")
    assert Servidor.objects.filter(nome="Ana B.").count() == 2


def test_celebracao_duplicada_no_mesmo_horario(comunidade, celebracao):
    with pytest.raises(IntegrityError), transaction.atomic():
        Celebracao.objects.create(comunidade=comunidade, titulo="Outra", data_hora_inicio=celebracao.data_hora_inicio)


def test_publicar_gera_token(celebracao):
    celebracao.publicar()
    assert celebracao.publicada and len(celebracao.token_publico) == 32


def test_saldo_da_tunica_em_decimal(tunica):
    PagamentoTunica.objects.create(tunica=tunica, valor=Decimal("85.00"), forma="dinheiro", data_pagamento="2026-11-01")
    assert tunica.total_pago == Decimal("85.00") and tunica.saldo == Decimal("90.00")
    assert "Coroinha completa" in str(tunica) and "R$ 85.00" in str(tunica.pagamentos.first())


def test_valor_da_tunica_deve_ser_positivo(servidores):
    t = Tunica(servidor=servidores["ana"], modelo=Tunica.Modelo.COROINHA_AVULSA, valor_total=Decimal("0"))
    with pytest.raises(ValidationError):
        t.full_clean()

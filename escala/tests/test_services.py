"""Testes unitários das regras de negócio (camada de serviços)."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from escala import services
from escala.models import Atribuicao, Celebracao, Funcao, Servidor

pytestmark = pytest.mark.django_db


def test_sugestao_ordena_por_quem_serviu_menos(celebracao, servidores, domingo, comunidade):
    # RF02: Lucas serviu 2x e Ana 1x no mês; Pedro e Marina 0x
    for i, (nome, n) in enumerate([("lucas", 2), ("ana", 1)]):
        for k in range(n):
            outra = Celebracao.objects.create(comunidade=comunidade, titulo="Missa",
                                              data_hora_inicio=domingo - timedelta(days=1 + i * 3 + k))
            Atribuicao.objects.create(celebracao=outra, servidor=servidores[nome], funcao=Funcao.CRUZ)
    nomes = [s.servidor.nome for s in services.sugerir_servidores(celebracao, Funcao.TURIBULO)]
    assert nomes[:2] == ["Marina S.", "Pedro H."]  # 0x, em ordem alfabética
    assert nomes[2:] == ["Ana B.", "Lucas F."]


def test_sugestao_exclui_inativos_e_outra_comunidade(celebracao, servidores, outra_comunidade):
    servidores["pedro"].status = Servidor.Status.AFASTADO
    servidores["pedro"].save()
    Servidor.objects.create(comunidade=outra_comunidade, nome="Gabriel T.", nome_responsavel="R")
    nomes = [s.servidor.nome for s in services.sugerir_servidores(celebracao)]
    assert "Pedro H." not in nomes
    assert "Gabriel T." not in nomes


def test_atribuir_cria_registro(celebracao, servidores, usuario):
    a = services.atribuir(celebracao, Funcao.CRUZ, servidores["lucas"], usuario)
    assert a.pk and a.criado_por == usuario
    assert celebracao.atribuicoes.count() == 1


def test_bloqueia_mesmo_servidor_em_duas_funcoes(celebracao, servidores):
    # RF03 – regra observada na escala do crisma
    services.atribuir(celebracao, Funcao.CRUZ, servidores["lucas"])
    with pytest.raises(services.RegraEscalaError) as erro:
        services.atribuir(celebracao, Funcao.TURIBULO, servidores["lucas"])
    assert "Lucas F. já está em Cruz nesta missa" in str(erro.value)
    assert celebracao.atribuicoes.count() == 1


def test_bloqueia_horario_sobreposto_em_outra_celebracao(celebracao, servidores, comunidade, domingo):
    outra = Celebracao.objects.create(comunidade=comunidade, titulo="Batizado",
                                      data_hora_inicio=domingo + timedelta(minutes=30))
    services.atribuir(outra, Funcao.CRUZ, servidores["ana"])
    with pytest.raises(services.RegraEscalaError, match="no mesmo horário"):
        services.atribuir(celebracao, Funcao.NAVETA, servidores["ana"])
    # e ela não aparece nas sugestões
    assert "Ana B." not in [s.servidor.nome for s in services.sugerir_servidores(celebracao)]


def test_horario_nao_sobreposto_e_permitido(celebracao, servidores, comunidade, domingo):
    depois = Celebracao.objects.create(comunidade=comunidade, titulo="Missa",
                                       data_hora_inicio=domingo + timedelta(hours=3))
    services.atribuir(depois, Funcao.CRUZ, servidores["ana"])
    services.atribuir(celebracao, Funcao.CRUZ, servidores["ana"])
    assert celebracao.atribuicoes.count() == 1


def test_bloqueia_servidor_inativo_e_de_outra_comunidade(celebracao, servidores, outra_comunidade):
    servidores["marina"].status = Servidor.Status.AFASTADO
    with pytest.raises(services.RegraEscalaError, match="não está ativo"):
        services.atribuir(celebracao, Funcao.CRUZ, servidores["marina"])
    gabriel = Servidor.objects.create(comunidade=outra_comunidade, nome="Gabriel T.", nome_responsavel="R")
    with pytest.raises(services.RegraEscalaError, match="não pertence"):
        services.atribuir(celebracao, Funcao.CRUZ, gabriel)


def test_trocar_servidor_da_funcao(celebracao, servidores):
    services.atribuir(celebracao, Funcao.CRUZ, servidores["lucas"])
    services.atribuir(celebracao, Funcao.CRUZ, servidores["ana"])
    assert list(celebracao.atribuicoes.values_list("servidor__nome", flat=True)) == ["Ana B."]


def test_restricao_do_banco_impede_duplicidade(celebracao, servidores):
    # garantia final no banco, independente da camada de serviços
    Atribuicao.objects.create(celebracao=celebracao, servidor=servidores["pedro"], funcao=Funcao.CRUZ)
    with pytest.raises(IntegrityError), transaction.atomic():
        Atribuicao.objects.create(celebracao=celebracao, servidor=servidores["pedro"], funcao=Funcao.NAVETA)


def test_aviso_sem_experiente(celebracao, servidores):
    services.atribuir(celebracao, Funcao.CRUZ, servidores["pedro"])
    avisos = services.avisos_da_escala(celebracao)
    assert any("experiente" in a for a in avisos)
    services.atribuir(celebracao, Funcao.TURIBULO, servidores["ana"])
    assert not any("experiente" in a for a in services.avisos_da_escala(celebracao))


def test_publicar_gera_token_aleatorio(celebracao):
    token = services.publicar(celebracao)
    celebracao.refresh_from_db()
    assert celebracao.publicada and len(token) >= 24
    assert services.publicar(celebracao) == token  # republicar mantém o mesmo link


def test_pagamentos_e_saldo(tunica, usuario):
    # RF05 – valores decimais e saldo calculado
    services.registrar_pagamento(tunica, "85.00", "dinheiro", "2026-11-01", usuario)
    services.registrar_pagamento(tunica, "42.50", "pix", "2026-11-08", usuario)
    assert tunica.total_pago == Decimal("127.50")
    assert tunica.saldo == Decimal("47.50")
    assert tunica.pagamentos.order_by("parcela").last().parcela == 2


def test_pagamento_acima_do_saldo_e_bloqueado(tunica):
    services.registrar_pagamento(tunica, "175.00", "pix", "2026-11-01")
    with pytest.raises(services.RegraEscalaError, match="ultrapassa o saldo"):
        services.registrar_pagamento(tunica, "0.01", "pix", "2026-11-02")


def test_resumo_caixa_confere_centavo_a_centavo(tunica):
    services.registrar_pagamento(tunica, "100.00", "dinheiro", "2026-11-01")
    caixa = services.resumo_caixa()
    assert caixa == {"devido": Decimal("175.00"), "recebido": Decimal("100.00"), "pendente": Decimal("75.00")}


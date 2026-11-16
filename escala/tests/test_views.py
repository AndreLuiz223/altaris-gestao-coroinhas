"""Testes de integração: Views + templates + banco + autenticação."""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from escala.models import Funcao, Servidor

pytestmark = pytest.mark.django_db

PROTEGIDAS = ["painel", "servidores", "tunicas", "servidor_novo", "tunica_nova"]


@pytest.mark.parametrize("nome", PROTEGIDAS)
def test_paginas_protegidas_exigem_login(client, nome):
    resp = client.get(reverse(nome))
    assert resp.status_code == 302 and reverse("login") in resp["Location"]


def test_login_valido_e_invalido(client, usuario):
    ruim = client.post(reverse("login"), {"username": "coordenacao", "password": "errada"})
    assert ruim.status_code == 200 and "Usuário ou senha inválidos" in ruim.content.decode()
    ok = client.post(reverse("login"), {"username": "coordenacao", "password": "Senha-de-Teste-123"})
    assert ok.status_code == 302


def test_senha_armazenada_com_argon2(usuario):
    assert usuario.password.startswith("argon2$argon2id$")
    assert "Senha-de-Teste-123" not in usuario.password


def test_logout_encerra_sessao(cliente_logado):
    cliente_logado.post(reverse("logout"))
    assert cliente_logado.get(reverse("painel")).status_code == 302


def test_fluxo_completo_montar_e_publicar(cliente_logado, celebracao, servidores):
    # Tela 1 -> Tela 2 -> atribuir -> publicar -> Tela 3 -> página pública
    painel = cliente_logado.get(reverse("painel"))
    assert "Montar escala" in painel.content.decode()

    lista = cliente_logado.get(reverse("montar_escala", args=[celebracao.pk]) + "?funcao=turibulo")
    html = lista.content.decode()
    assert "Escolher para Turíbulo" in html and "serviu 0x no mês" in html

    resp = cliente_logado.post(reverse("atribuir", args=[celebracao.pk]),
                               {"funcao": Funcao.TURIBULO, "servidor": servidores["ana"].pk}, follow=True)
    assert "Ana B. escalado(a) em Turíbulo" in resp.content.decode()

    resp = cliente_logado.post(reverse("publicar", args=[celebracao.pk]), follow=True)
    assert "Escala publicada!" in resp.content.decode()
    celebracao.refresh_from_db()
    publica = Client().get(reverse("escala_publica", args=[celebracao.token_publico]))
    assert publica.status_code == 200 and "Ana B." in publica.content.decode()


def test_alerta_de_conflito_na_interface(cliente_logado, celebracao, servidores):
    url = reverse("atribuir", args=[celebracao.pk])
    cliente_logado.post(url, {"funcao": Funcao.CRUZ, "servidor": servidores["lucas"].pk})
    resp = cliente_logado.post(url, {"funcao": Funcao.TURIBULO, "servidor": servidores["lucas"].pk}, follow=True)
    html = resp.content.decode()
    assert 'role="alert"' in html and "Lucas F. já está em Cruz nesta missa" in html
    assert "✕" in html  # alerta com símbolo, não só cor (RNF04)


def test_pagina_publica_sem_dados_de_contato(celebracao, servidores):
    servidores["ana"].telefone_responsavel = "(11) 91234-5678"
    servidores["ana"].save()
    from escala import services
    services.atribuir(celebracao, Funcao.CRUZ, servidores["ana"])
    token = services.publicar(celebracao)
    html = Client().get(reverse("escala_publica", args=[token])).content.decode()
    assert "Ana B." in html and "91234-5678" not in html and "Responsável" not in html


def test_token_invalido_retorna_404(client, celebracao):
    assert client.get(reverse("escala_publica", args=["token-inexistente"])).status_code == 404


def test_escala_nao_publicada_nao_e_publica(client, celebracao):
    celebracao.token_publico = "abc123"
    celebracao.save()
    assert client.get(reverse("escala_publica", args=["abc123"])).status_code == 404


def test_post_sem_csrf_e_recusado(usuario, celebracao, servidores):
    c = Client(enforce_csrf_checks=True)
    c.force_login(usuario)
    resp = c.post(reverse("atribuir", args=[celebracao.pk]), {"funcao": "cruz", "servidor": servidores["ana"].pk})
    assert resp.status_code == 403


def test_xss_no_nome_e_escapado(cliente_logado, comunidade):
    Servidor.objects.create(comunidade=comunidade, nome="<script>alert(1)</script>", nome_responsavel="R")
    html = cliente_logado.get(reverse("servidores")).content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_cabecalhos_de_seguranca(cliente_logado):
    resp = cliente_logado.get(reverse("painel"))
    assert "Content-Security-Policy" in resp and resp["X-Frame-Options"] == "DENY"


def test_cadastro_servidor_valida_responsavel(cliente_logado, comunidade):
    url = reverse("servidor_novo")
    dados = {"nome": "Júlia R.", "comunidade": comunidade.pk, "tipo": "coroinha", "nivel": "em_formacao",
             "status": "ativo", "menor_de_idade": "on"}
    resp = cliente_logado.post(url, dados)
    assert resp.status_code == 200 and "Informe o responsável" in resp.content.decode()
    dados["nome_responsavel"] = "Responsável Fictício"
    assert cliente_logado.post(url, dados).status_code == 302
    assert Servidor.objects.filter(nome="Júlia R.").exists()


def test_cadastro_servidor_duplicado_bloqueado(cliente_logado, comunidade, servidores):
    dados = {"nome": "Ana B.", "comunidade": comunidade.pk, "tipo": "coroinha", "nivel": "experiente",
             "status": "ativo", "nome_responsavel": "R"}
    resp = cliente_logado.post(reverse("servidor_novo"), dados)
    assert resp.status_code == 200 and Servidor.objects.filter(nome="Ana B.").count() == 1


def test_tunicas_e_pagamento_pela_interface(cliente_logado, tunica):
    resp = cliente_logado.post(reverse("pagamento_novo", args=[tunica.pk]),
                               {"valor": "200.00", "forma": "pix", "data_pagamento": "2026-11-01"})
    assert "ultrapassa o saldo" in resp.content.decode()
    cliente_logado.post(reverse("pagamento_novo", args=[tunica.pk]),
                        {"valor": "75.00", "forma": "pix", "data_pagamento": "2026-11-01"})
    html = cliente_logado.get(reverse("tunicas")).content.decode()
    assert "Saldo: R$ 100,00" in html or "Saldo: R$ 100.00" in html



@pytest.mark.django_db
def test_recursos_de_acessibilidade_presentes_inclusive_na_escala_publica(client, celebracao):
    """Letra maior, alto contraste e atalho para o conteúdo em todas as páginas."""
    from escala import services
    services.publicar(celebracao)
    for resp in (client.get(reverse("login")),
                 client.get(reverse("escala_publica", args=[celebracao.token_publico]))):
        html = resp.content.decode()
        assert 'data-a11y="fonte"' in html and 'data-a11y="contraste"' in html
        assert 'aria-pressed="false"' in html
        assert 'href="#conteudo"' in html and 'id="conteudo"' in html
        assert "js/acessibilidade.js" in html

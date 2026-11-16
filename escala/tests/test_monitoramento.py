"""Testes do monitoramento pós-lançamento e do preparo de produção (EP4)."""
from unittest import mock

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import override_settings

from escala.models import Comunidade

pytestmark = pytest.mark.django_db


def test_saude_responde_ok_com_banco(client):
    resp = client.get("/saude/")
    dados = resp.json()
    assert resp.status_code == 200 and dados["status"] == "ok" and dados["banco"] == "ok"
    assert resp["Cache-Control"] == "no-store"


@override_settings(DEBUG=False, SECURE_SSL_REDIRECT=True, ALLOWED_HOSTS=["altaris.onrender.com"])
def test_saude_funciona_para_sonda_interna_sem_https_e_com_outro_host(client):
    resp = client.get("/saude/", HTTP_HOST="10.0.0.5:10000")
    assert resp.status_code == 200


def test_saude_retorna_503_se_banco_cair(client):
    with mock.patch("escala.monitoramento.connection.cursor", side_effect=Exception("sem banco")):
        resp = client.get("/saude/")
    assert resp.status_code == 503 and resp.json()["banco"] == "erro"


def test_saude_nao_expoe_dados_pessoais(client, servidores):
    corpo = client.get("/saude/").content.decode()
    assert "Ana" not in corpo and "Responsável" not in corpo


def test_preparar_producao_e_idempotente(monkeypatch):
    monkeypatch.setenv("ALTARIS_USUARIO", "coordenacao")
    monkeypatch.setenv("ALTARIS_SENHA", "Senha-Forte-de-Teste-2026")
    call_command("preparar_producao")
    call_command("preparar_producao")
    assert Comunidade.objects.count() == 5
    usuario = User.objects.get(username="coordenacao")
    assert usuario.is_superuser and usuario.check_password("Senha-Forte-de-Teste-2026")


def test_preparar_producao_sem_senha_nao_cria_usuario(monkeypatch):
    monkeypatch.delenv("ALTARIS_SENHA", raising=False)
    call_command("preparar_producao")
    assert not User.objects.exists()

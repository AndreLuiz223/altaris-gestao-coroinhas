from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from escala.models import Celebracao, Comunidade, Servidor, Tunica


@pytest.fixture
def comunidade(db):
    return Comunidade.objects.create(nome="Santa Rita de Cássia")


@pytest.fixture
def outra_comunidade(db):
    return Comunidade.objects.create(nome="São João Batista")


@pytest.fixture
def domingo():
    base = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=3)
    return base


def criar_servidor(comunidade, nome, **kw):
    kw.setdefault("nome_responsavel", "Responsável Fictício")
    return Servidor.objects.create(comunidade=comunidade, nome=nome, **kw)


@pytest.fixture
def servidores(comunidade):
    return {
        "lucas": criar_servidor(comunidade, "Lucas F.", nivel=Servidor.Nivel.EXPERIENTE),
        "ana": criar_servidor(comunidade, "Ana B.", nivel=Servidor.Nivel.EXPERIENTE),
        "pedro": criar_servidor(comunidade, "Pedro H."),
        "marina": criar_servidor(comunidade, "Marina S."),
    }


@pytest.fixture
def celebracao(comunidade, domingo):
    return Celebracao.objects.create(comunidade=comunidade, titulo="Missa dominical", data_hora_inicio=domingo)


@pytest.fixture
def usuario(db):
    return User.objects.create_user("coordenacao", password="Senha-de-Teste-123", first_name="Coordenação")


@pytest.fixture
def cliente_logado(client, usuario):
    client.force_login(usuario)
    return client


@pytest.fixture
def tunica(servidores):
    return Tunica.objects.create(servidor=servidores["pedro"], modelo=Tunica.Modelo.COROINHA_COMPLETA,
                                 valor_total=Decimal("175.00"))

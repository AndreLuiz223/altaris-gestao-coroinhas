"""Monitoramento pós-lançamento (EP4).

Health check em /saude/ usado pelo Render (healthCheckPath) e por monitores externos de
disponibilidade. Responde antes do redirecionamento HTTPS e da validação de host, para que a
sonda interna do provedor funcione, e não expõe dados pessoais: só status, banco e versão.
"""
import logging
import os
import time

from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger("altaris.saude")
VERSAO = os.environ.get("RENDER_GIT_COMMIT", "local")[:7]


def verificar_saude():
    inicio = time.monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        banco = "ok"
    except Exception:  # noqa: BLE001 - qualquer falha de banco deixa o serviço indisponível
        logger.exception("Health check: banco de dados indisponível")
        banco = "erro"
    latencia_ms = round((time.monotonic() - inicio) * 1000, 1)
    status = "ok" if banco == "ok" else "erro"
    return {"status": status, "banco": banco, "latencia_ms": latencia_ms, "versao": VERSAO}


class HealthCheckMiddleware:
    """Responde /saude/ com JSON (200 ou 503) sem passar pelo resto da pilha."""

    caminho = "/saude/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == self.caminho and request.method in ("GET", "HEAD"):
            dados = verificar_saude()
            resposta = JsonResponse(dados, status=200 if dados["status"] == "ok" else 503)
            resposta["Cache-Control"] = "no-store"
            return resposta
        return self.get_response(request)

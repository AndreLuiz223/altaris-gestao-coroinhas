"""Prepara o ambiente de produção de forma idempotente (pode rodar a cada deploy).

- Cria as cinco comunidades da paróquia, se ainda não existirem.
- Cria o usuário da coordenação a partir de variáveis de ambiente, se ainda não existir
  (ALTARIS_USUARIO e ALTARIS_SENHA). A senha nunca fica no repositório.
"""
import os

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand

from escala.models import Comunidade

COMUNIDADES = [
    "Matriz Imaculada Conceição",
    "São Francisco de Assis",
    "São João Batista",
    "Santa Rita de Cássia",
    "Santo Expedito",
]


class Command(BaseCommand):
    help = "Cria comunidades e o usuário da coordenação (idempotente)."

    def handle(self, *args, **options):
        criadas = sum(Comunidade.objects.get_or_create(nome=n)[1] for n in COMUNIDADES)
        self.stdout.write(f"Comunidades novas: {criadas}")

        usuario, senha = os.environ.get("ALTARIS_USUARIO"), os.environ.get("ALTARIS_SENHA")
        if not usuario or not senha:
            self.stdout.write("ALTARIS_USUARIO/ALTARIS_SENHA não definidos: usuário não criado.")
            return
        if User.objects.filter(username=usuario).exists():
            self.stdout.write(f"Usuário '{usuario}' já existe.")
            return
        validate_password(senha)
        User.objects.create_superuser(usuario, password=senha, first_name="Coordenação")
        self.stdout.write(f"Usuário '{usuario}' criado.")

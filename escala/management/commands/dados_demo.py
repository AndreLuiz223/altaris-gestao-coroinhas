"""Carrega dados FICTÍCIOS para demonstração e testes de usabilidade (sem dados reais de menores)."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from escala import services
from escala.models import Celebracao, Comunidade, Funcao, Servidor, Tunica

COMUNIDADES = ["Matriz Imaculada Conceição", "São Francisco de Assis", "São João Batista",
               "Santa Rita de Cássia", "Santo Expedito"]
NOMES = ["Ana B.", "Pedro H.", "Marina S.", "Gabriel T.", "Lucas F.", "Júlia R.", "Rafael M.", "Beatriz C.",
         "Mateus L.", "Clara P.", "Tiago V.", "Sofia N."]


class Command(BaseCommand):
    help = "Cria comunidades, servidores, celebrações e túnicas fictícias."

    def add_arguments(self, parser):
        parser.add_argument("--senha", default=None, help="Senha do usuário 'coordenacao' (se não existir)")

    def handle(self, *args, **opts):
        comunidades = [Comunidade.objects.get_or_create(nome=n)[0] for n in COMUNIDADES]
        santa_rita = comunidades[3]
        for i, nome in enumerate(NOMES):
            Servidor.objects.get_or_create(
                nome=nome, comunidade=santa_rita,
                defaults={"nivel": Servidor.Nivel.EXPERIENTE if i % 3 == 0 else Servidor.Nivel.EM_FORMACAO,
                          "tipo": Servidor.Tipo.CERIMONIARIO if i % 4 == 0 else Servidor.Tipo.COROINHA,
                          "nome_responsavel": "Responsável fictício"},
            )
        hoje = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        sabado = hoje + timedelta(days=(5 - hoje.weekday()) % 7 or 7)
        domingo = sabado + timedelta(days=1)
        horarios = [(comunidades[2], sabado.replace(hour=19), "Missa", Celebracao.Tipo.COMUM),
                    (santa_rita, domingo.replace(hour=9), "Missa dominical", Celebracao.Tipo.DOMINICAL),
                    (comunidades[0], domingo.replace(hour=11), "Missa", Celebracao.Tipo.DOMINICAL)]
        cels = [Celebracao.objects.get_or_create(comunidade=c, data_hora_inicio=h,
                                                 defaults={"titulo": t, "tipo": tp})[0]
                for c, h, t, tp in horarios]
        cel = cels[1]
        if not cel.atribuicoes.exists():
            for funcao, nome in [(Funcao.CRUZ, "Lucas F."), (Funcao.NAVETA, "Júlia R."), (Funcao.MISSAL, "Rafael M.")]:
                services.atribuir(cel, funcao, Servidor.objects.get(nome=nome, comunidade=santa_rita))
        # histórico do mês para a ordenação "quem serviu menos"
        passado = Celebracao.objects.get_or_create(comunidade=santa_rita, data_hora_inicio=hoje.replace(hour=9, day=1),
                                                   defaults={"titulo": "Missa dominical"})[0]
        if not passado.atribuicoes.exists() and passado.pk != cel.pk:
            for funcao, nome in [(Funcao.CRUZ, "Gabriel T."), (Funcao.TURIBULO, "Marina S."), (Funcao.NAVETA, "Pedro H.")]:
                services.atribuir(passado, funcao, Servidor.objects.get(nome=nome, comunidade=santa_rita))
        if not Tunica.objects.exists():
            t = Tunica.objects.create(servidor=Servidor.objects.get(nome="Pedro H."),
                                      modelo=Tunica.Modelo.COROINHA_COMPLETA, valor_total=Decimal("175.00"))
            services.registrar_pagamento(t, "85.00", "dinheiro", hoje.date())
        if opts["senha"] and not User.objects.filter(username="coordenacao").exists():
            User.objects.create_user("coordenacao", password=opts["senha"], first_name="Coordenação")
        self.stdout.write(self.style.SUCCESS("Dados fictícios carregados."))

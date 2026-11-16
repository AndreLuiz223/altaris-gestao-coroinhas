"""Modelos de dados do ALTARIS (EP2 - Modelagem simplificada dos dados)."""
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Sum


class Comunidade(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Servidor(models.Model):
    class Tipo(models.TextChoices):
        COROINHA = "coroinha", "Coroinha"
        CERIMONIARIO = "cerimoniario", "Cerimoniário"

    class Nivel(models.TextChoices):
        EXPERIENTE = "experiente", "Experiente"
        EM_FORMACAO = "em_formacao", "Em formação"

    class Status(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        AFASTADO = "afastado", "Afastado"
        DESLIGADO = "desligado", "Desligado"

    nome = models.CharField(max_length=100)
    comunidade = models.ForeignKey(Comunidade, on_delete=models.PROTECT, related_name="servidores")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.COROINHA)
    nivel = models.CharField(max_length=20, choices=Nivel.choices, default=Nivel.EM_FORMACAO)
    etapa_formacao = models.CharField("etapa de formação", max_length=60, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVO)
    menor_de_idade = models.BooleanField("menor de idade", default=True)
    nome_responsavel = models.CharField("nome do responsável", max_length=100, blank=True)
    telefone_responsavel = models.CharField(
        "telefone do responsável",
        max_length=15,
        blank=True,
        validators=[RegexValidator(r"^\(\d{2}\) 9?\d{4}-\d{4}$", "Use o formato (11) 91234-5678.")],
    )
    tamanho_tunica = models.CharField("tamanho da túnica", max_length=2, blank=True,
                                      choices=[(t, t) for t in ["PP", "P", "M", "G", "GG"]])
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name_plural = "servidores"
        constraints = [
            models.UniqueConstraint(fields=["nome", "comunidade"], name="servidor_unico_por_comunidade"),
        ]

    def __str__(self):
        return self.nome

    def clean(self):
        if self.menor_de_idade and not self.nome_responsavel:
            raise ValidationError({"nome_responsavel": "Informe o responsável pelo servidor menor de idade."})

    @property
    def experiente(self):
        return self.nivel == self.Nivel.EXPERIENTE


class Funcao(models.TextChoices):
    CRUZ = "cruz", "Cruz"
    TURIBULO = "turibulo", "Turíbulo"
    NAVETA = "naveta", "Naveta"
    VELA_1 = "vela_1", "Vela 1"
    VELA_2 = "vela_2", "Vela 2"
    MISSAL = "missal", "Missal"
    SINETA = "sineta", "Sineta"
    LAVABO = "lavabo", "Lavabo"
    ACOMPANHANTE = "acompanhante", "Acompanhante"


FUNCOES_PADRAO = [
    Funcao.CRUZ, Funcao.TURIBULO, Funcao.NAVETA, Funcao.VELA_1,
    Funcao.VELA_2, Funcao.MISSAL, Funcao.SINETA, Funcao.LAVABO,
]


def gerar_token():
    return secrets.token_urlsafe(24)[:32]


class Celebracao(models.Model):
    class Tipo(models.TextChoices):
        COMUM = "comum", "Missa"
        DOMINICAL = "dominical", "Missa dominical"
        SOLENIDADE = "solenidade", "Solenidade"
        NOVENA = "novena", "Novena"
        ESPECIAL = "especial", "Especial"

    comunidade = models.ForeignKey(Comunidade, on_delete=models.PROTECT, related_name="celebracoes")
    titulo = models.CharField("título", max_length=80)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.DOMINICAL)
    data_hora_inicio = models.DateTimeField("início")
    duracao_min = models.PositiveIntegerField("duração (min)", default=90)
    exige_experiente = models.BooleanField(default=True)
    publicada = models.BooleanField(default=False)
    token_publico = models.CharField(max_length=32, unique=True, null=True, blank=True)
    observacao = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["data_hora_inicio"]
        verbose_name = "celebração"
        verbose_name_plural = "celebrações"
        constraints = [
            models.UniqueConstraint(fields=["comunidade", "data_hora_inicio"], name="celebracao_unica_por_horario"),
        ]

    def __str__(self):
        local = self.data_hora_inicio.astimezone()
        return f"{self.titulo} – {self.comunidade} – {local:%d/%m %H:%M}"

    @property
    def data_hora_fim(self):
        return self.data_hora_inicio + timedelta(minutes=self.duracao_min)

    @property
    def total_funcoes(self):
        return len(FUNCOES_PADRAO)

    @property
    def preenchidas(self):
        return self.atribuicoes.count()

    def publicar(self):
        if not self.token_publico:
            self.token_publico = gerar_token()
        self.publicada = True
        self.save(update_fields=["publicada", "token_publico"])


class Atribuicao(models.Model):
    class Presenca(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PRESENTE = "presente", "Presente"
        FALTA = "falta", "Falta"
        JUSTIFICADA = "falta_justificada", "Falta justificada"

    celebracao = models.ForeignKey(Celebracao, on_delete=models.CASCADE, related_name="atribuicoes")
    servidor = models.ForeignKey(Servidor, on_delete=models.PROTECT, related_name="atribuicoes")
    funcao = models.CharField(max_length=20, choices=Funcao.choices)
    presenca = models.CharField(max_length=20, choices=Presenca.choices, default=Presenca.PENDENTE)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "atribuição"
        verbose_name_plural = "atribuições"
        constraints = [
            # RF03: o mesmo servidor não pode ter duas funções na mesma celebração
            models.UniqueConstraint(fields=["celebracao", "servidor"], name="servidor_uma_funcao_por_celebracao"),
            # cada função é preenchida por uma única pessoa
            models.UniqueConstraint(fields=["celebracao", "funcao"], name="funcao_unica_por_celebracao"),
        ]

    def __str__(self):
        return f"{self.get_funcao_display()}: {self.servidor}"


class Tunica(models.Model):
    class Modelo(models.TextChoices):
        COROINHA_COMPLETA = "coroinha_completa", "Coroinha completa"
        COROINHA_AVULSA = "coroinha_avulsa", "Coroinha (peça avulsa)"
        CERIMONIARIO_COMPLETA = "cerimoniario_completa", "Cerimoniário completa"
        CERIMONIARIO_AVULSA = "cerimoniario_avulsa", "Cerimoniário (peça avulsa)"

    servidor = models.ForeignKey(Servidor, on_delete=models.PROTECT, related_name="tunicas")
    modelo = models.CharField(max_length=30, choices=Modelo.choices)
    tamanho = models.CharField(max_length=2, blank=True, choices=[(t, t) for t in ["PP", "P", "M", "G", "GG"]])
    valor_total = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    data_entrega = models.DateField(null=True, blank=True)
    devolvida = models.BooleanField(default=False)

    class Meta:
        verbose_name = "túnica"

    def __str__(self):
        return f"{self.get_modelo_display()} – {self.servidor}"

    @property
    def total_pago(self):
        return self.pagamentos.aggregate(t=Sum("valor"))["t"] or Decimal("0.00")

    @property
    def saldo(self):
        return self.valor_total - self.total_pago


class PagamentoTunica(models.Model):
    class Forma(models.TextChoices):
        DINHEIRO = "dinheiro", "Dinheiro"
        PIX = "pix", "PIX"

    tunica = models.ForeignKey(Tunica, on_delete=models.PROTECT, related_name="pagamentos")
    valor = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    forma = models.CharField(max_length=10, choices=Forma.choices)
    data_pagamento = models.DateField()
    parcela = models.PositiveSmallIntegerField(default=1)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "pagamento de túnica"
        verbose_name_plural = "pagamentos de túnica"

    def __str__(self):
        return f"R$ {self.valor} ({self.get_forma_display()}) – {self.tunica}"

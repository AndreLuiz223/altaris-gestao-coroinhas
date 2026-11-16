from django import forms

from .models import Servidor


class BootstrapMixin:
    def _bootstrap(self):
        for field in self.fields.values():
            css = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            if isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            field.widget.attrs.setdefault("class", css)


class ServidorForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Servidor
        fields = ["nome", "comunidade", "tipo", "nivel", "etapa_formacao", "status",
                  "menor_de_idade", "nome_responsavel", "telefone_responsavel", "tamanho_tunica"]
        widgets = {"telefone_responsavel": forms.TextInput(attrs={"type": "tel", "placeholder": "(11) 91234-5678"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bootstrap()

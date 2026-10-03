from django import forms

from portfolios.models import Portfolio


class PortfolioForm(forms.ModelForm):
    class Meta:
        model = Portfolio

        fields = [
            "name",
            "currency",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Long-Term Portfolio",
                    "autocomplete": "off",
                }
            ),
            "currency": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "EUR",
                    "maxlength": "3",
                    "autocomplete": "off",
                }
            ),
        }

        error_messages = {
            "currency": {
                "max_length": "Enter a valid 3-letter currency code.",
            },
        }

    def clean_currency(self):
        currency = self.cleaned_data["currency"].strip().upper()

        if len(currency) != 3 or not currency.isalpha():
            raise forms.ValidationError(
                "Enter a valid 3-letter currency code."
            )

        return currency
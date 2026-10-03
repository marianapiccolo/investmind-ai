from django import forms
from django.utils import timezone

from portfolios.models import Asset, Portfolio, Transaction


class PortfolioForm(forms.ModelForm):
    currency = forms.CharField(
        max_length=3,
        error_messages={
            "max_length": (
                "Enter a valid 3-letter currency code."
            ),
            "required": (
                "Enter a valid 3-letter currency code."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "EUR",
                "maxlength": "3",
                "autocomplete": "off",
            }
        ),
    )

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
                    "placeholder": (
                        "e.g. Long-Term Portfolio"
                    ),
                    "autocomplete": "off",
                }
            ),
        }

    def clean_currency(self):
        currency = (
            self.cleaned_data["currency"]
            .strip()
            .upper()
        )

        if (
            len(currency) != 3
            or not currency.isalpha()
        ):
            raise forms.ValidationError(
                "Enter a valid 3-letter currency code."
            )

        return currency


class AssetChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, asset):
        return (
            f"{asset.ticker} — "
            f"{asset.name} "
            f"({asset.currency})"
        )


class TransactionForm(forms.ModelForm):
    asset = AssetChoiceField(
        queryset=Asset.objects.none(),
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    transaction_type = forms.ChoiceField(
        choices=Transaction.TransactionType.choices,
        initial=Transaction.TransactionType.BUY,
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    transaction_date = forms.DateTimeField(
        input_formats=[
            "%Y-%m-%dT%H:%M",
        ],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={
                "class": "form-control",
                "type": "datetime-local",
            },
        ),
    )

    class Meta:
        model = Transaction

        fields = [
            "transaction_type",
            "asset",
            "quantity",
            "price",
            "transaction_date",
        ]

        widgets = {
            "quantity": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "any",
                    "placeholder": "0.00",
                }
            ),
            "price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "any",
                    "placeholder": "0.00",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            **kwargs,
        )

        self.fields["asset"].queryset = (
            Asset.objects.all()
            .order_by("ticker")
        )

        if not self.is_bound:
            self.fields[
                "transaction_date"
            ].initial = (
                timezone.localtime()
                .replace(
                    second=0,
                    microsecond=0,
                )
            )
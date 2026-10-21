from datetime import date
from decimal import Decimal
from pathlib import Path
import re
from types import SimpleNamespace

from django.template import Context, Engine
from django.test import SimpleTestCase, override_settings


@override_settings(STATIC_URL="/static/", LANGUAGE_CODE="en-us")
class RiskTemplateTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = Engine(
            dirs=[str(Path(__file__).resolve().parents[1] / "templates")],
            libraries={"static": "django.templatetags.static"},
            loaders=[
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "base.html": (
                            "{% block title %}{% endblock %}"
                            "{% block content %}{% endblock %}"
                            "{% block extra_js %}{% endblock %}"
                        )
                    },
                ),
                "django.template.loaders.filesystem.Loader",
            ],
        )

    def render_risk(self, *, volatility=None, downside=None, best="-0.15", worst="-14.12"):
        portfolio = SimpleNamespace(id=2, name="Reserva")
        reason = (
            "Annualized metrics are unavailable because the series includes "
            "transaction-only dates without fresh market prices."
            if volatility is None or downside is None
            else ""
        )
        data = {
            "annualized_volatility_percentage": volatility,
            "annualized_downside_deviation_percentage": downside,
            "annualization_unavailable_reason": reason,
            "maximum_drawdown_percentage": Decimal("-14.25"),
            "time_weighted_return_percentage": Decimal("-14.25"),
            "best_period": {"date": date(2026, 10, 19), "return_percentage": Decimal(best)},
            "worst_period": {"date": date(2026, 10, 18), "return_percentage": Decimal(worst)},
            "start_date": date(2026, 10, 17),
            "end_date": date(2026, 10, 19),
            "return_observations": 2,
            "positive_periods": 0,
            "negative_periods": 2,
        }
        return self.engine.get_template("portfolios/risk.html").render(
            Context(
                {
                    "selected_portfolio": portfolio,
                    "portfolios": [portfolio],
                    "risk": {"available": True, "data": data},
                    "risk_distribution_chart": None,
                    "extreme_return_chart": None,
                },
                use_l10n=False,
            )
        )

    def period_cards(self, rendered):
        return [
            (classes, re.sub(r"\s+", "", value))
            for classes, value in re.findall(
                r'<div\s+class="([^"]*\brisk-period-value\b[^"]*)"\s*>(.*?)</div>',
                rendered,
                flags=re.DOTALL,
            )
        ]

    def test_missing_metrics_show_unavailable_and_reason(self):
        rendered = self.render_risk()
        self.assertEqual(rendered.count("Unavailable"), 2)
        self.assertIn("Annualized metrics unavailable", rendered)
        self.assertIn("transaction-only dates", rendered)
        self.assertNotRegex(rendered, r">\s*%\s*<")
        self.assertIn("-14.25%", rendered)

    def test_zero_metrics_are_available_values(self):
        rendered = self.render_risk(volatility=Decimal("0"), downside=Decimal("0"))
        self.assertNotIn("Unavailable", rendered)
        self.assertNotIn("Annualized metrics unavailable", rendered)
        self.assertGreaterEqual(rendered.count("0.00%"), 2)

    def test_best_of_negative_periods_remains_negative(self):
        rendered = self.render_risk()
        cards = self.period_cards(rendered)
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0][1], "-0.15%")
        self.assertEqual(cards[1][1], "-14.12%")
        for classes, _ in cards:
            self.assertIn("metric-negative", classes)
            self.assertNotIn("metric-positive", classes)
        self.assertNotIn("+-", rendered)

    def test_worst_of_positive_periods_remains_positive(self):
        cards = self.period_cards(self.render_risk(best="5", worst="1"))
        self.assertEqual([value for _, value in cards], ["+5.00%", "+1.00%"])
        for classes, _ in cards:
            self.assertIn("metric-positive", classes)
            self.assertNotIn("metric-negative", classes)

    def test_zero_periods_have_no_positive_or_negative_sign_style(self):
        cards = self.period_cards(self.render_risk(best="0", worst="0"))
        self.assertEqual([value for _, value in cards], ["0.00%", "0.00%"])
        for classes, _ in cards:
            self.assertNotIn("metric-positive", classes)
            self.assertNotIn("metric-negative", classes)

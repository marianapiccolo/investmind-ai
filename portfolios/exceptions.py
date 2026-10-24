from rest_framework.exceptions import APIException


class MarketDataUnavailable(APIException):
    status_code = 502

    default_detail = "Market data provider is temporarily unavailable."

    default_code = "market_data_unavailable"

class AIServiceUnavailable(
    APIException
):
    status_code = 502
    default_detail = (
        "AI service is temporarily unavailable."
    )
    default_code = "ai_service_unavailable"
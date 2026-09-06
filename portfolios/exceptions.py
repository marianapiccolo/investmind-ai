from rest_framework.exceptions import APIException


class MarketDataUnavailable(APIException):
    status_code = 502

    default_detail = "Market data provider is temporarily unavailable."

    default_code = "market_data_unavailable"

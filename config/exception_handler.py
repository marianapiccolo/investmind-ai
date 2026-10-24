from rest_framework.views import (
    exception_handler as drf_exception_handler,
)


def api_exception_handler(exc, context):
    response = drf_exception_handler(
        exc,
        context,
    )

    if response is None:
        return None

    original_data = response.data

    response.data = {
        "status_code": response.status_code,
        "error": getattr(
            exc,
            "default_code",
            "api_error",
        ),
        "details": original_data,
    }

    return response

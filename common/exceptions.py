from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response


def bilim_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    return Response(
        {"success": False, "data": None, "error": response.data},
        status=response.status_code,
        headers=getattr(response, "headers", None),
    )

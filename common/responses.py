from rest_framework.response import Response
from rest_framework import status as http_status


def api_response(
    *,
    success: bool = True,
    data=None,
    error=None,
    status_code: int = http_status.HTTP_200_OK,
):
    return Response(
        {"success": success, "data": data, "error": error},
        status=status_code,
    )

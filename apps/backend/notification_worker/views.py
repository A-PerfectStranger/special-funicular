"""Only a parent can register their own device. Recipients are never client input."""

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from pickup.views import body, command, endpoint, response


@csrf_exempt
@require_POST
@endpoint
def register(request: HttpRequest) -> JsonResponse:
    data = body(request, {"token", "enabled"})
    if not isinstance(data["token"], str) or type(data["enabled"]) is not bool:
        raise ValueError()
    return response(
        command(
            request,
            "PADRE",
            "SELECT public.e4_endpoint(%s,%s)",
            (data["token"], data["enabled"]),
        )
    )

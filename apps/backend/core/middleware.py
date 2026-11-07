from collections.abc import Callable

from django.http import HttpRequest, HttpResponse


class SafeResponsesMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response["Cache-Control"] = "no-store"
        response["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response["Referrer-Policy"] = "no-referrer"
        return response

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from core.views import live


class SafeResponsesMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response["Cache-Control"] = "no-store"
        response["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        # Chromium sends Origin:null for form POSTs under no-referrer. Django
        # correctly rejects that origin. Keep referrers local to the web BFF so
        # its CSRF-protected forms work without disclosing URLs to the IdP.
        web_form = settings.E1_IDENTITY_ENABLED and request.path_info.startswith(
            ("/auth/", "/portal/")
        )
        response["Referrer-Policy"] = "same-origin" if web_form else "no-referrer"
        return response


class LivenessMiddleware:
    """Only the stateless health probe may arrive with an ALB target IP Host."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if (
            settings.TRUSTED_INGRESS == "ecs-express"
            and request.path_info == "/health/live"
            and request.method in {"GET", "HEAD"}
        ):
            return live(request)
        return self.get_response(request)

"""Middleware de cabeçalhos de segurança (RNF02 - XSS / clickjacking)."""

CSP = (
    "default-src 'self'; "
    "style-src 'self'; "
    "script-src 'self'; "
    "img-src 'self' data:; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self'"
)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", CSP)
        return response

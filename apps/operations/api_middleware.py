from rest_framework.response import Response


class ApiDenialPlaceholderMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_template_response(self, request, response):
        if (
            request.path_info.startswith("/api/")
            and isinstance(response, Response)
            and response.status_code in {401, 403, 404, 429}
            and isinstance(response.data, dict)
        ):
            response.data.setdefault("placeholder", "КЛОУН")
        return response

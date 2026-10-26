from django.shortcuts import render


def forbidden(request, exception=None):
    return render(request, "error.html", {"code": 403, "title": "Restricted record",
                                          "text": "Your role does not grant access to this page. Access attempts are audited."}, status=403)


def not_found(request, exception=None):
    return render(request, "error.html", {"code": 404, "title": "Not found",
                                          "text": "That record or page does not exist."}, status=404)

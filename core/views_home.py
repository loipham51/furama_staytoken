from django.conf import settings
from django.shortcuts import render


def home(request):
    "Home landing page showing QR claim guidance."
    return render(request, "home.html", {"demo_mode": settings.ST_DEMO_MODE})

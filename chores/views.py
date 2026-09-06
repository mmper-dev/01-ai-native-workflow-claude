from django.http import HttpResponse


def home(request):
    """Placeholder landing page -- replaced by the occurrence list in step 1."""
    return HttpResponse("Household chores: scaffold OK")

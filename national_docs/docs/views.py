from django.shortcuts import render

# Create your views here.

def landing_page(request):
    return render(request, 'docs/landing_page.html')

def login_page(request):
    return render(request, 'docs/login_page.html')

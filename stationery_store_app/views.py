from django.shortcuts import render

def home(request):
    return render(request, 'home.html')
def admin_login(request):
    return render(request, 'login_form.html', {'role': 'Адміністратор'})

def manager_login(request):
    return render(request, 'login_form.html', {'role': 'Менеджер'})

def seller_login(request):
    return render(request, 'login_form.html', {'role': 'Продавець'})
from django.shortcuts import render, redirect

def home(request):
    return render(request, 'home.html')
def director_login(request):
    return render(request, 'login_form.html', {'role': 'Директор'})

def manager_login(request):
    return render(request, 'login_form.html', {'role': 'Менеджер'})

def seller_login(request):
    return render(request, 'login_form.html', {'role': 'Продавець'})

def register(request, role):
    if role == "Директор":
        login_url = "director_login"
    elif role == "Менеджер":
        login_url = "manager_login"
    else:
        login_url = "seller_login"
    return render(request, 'register_form.html', {'role': role, 'login_url': login_url})
def reset_password(request):
    if request.method == "POST":
        return redirect('home')
    return render(request,'reset_password.html')

def director_panel(request):
    return render(request, 'director_panel.html')
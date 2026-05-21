from django.shortcuts import render, redirect
import bcrypt
from .models import UserAuth

def home(request):
    return render(request, 'home.html')

def director_login(request):
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        try:
            user = UserAuth.objects.get(login=username)
            print(f"Знайдено користувача: {user.login}")
            print(f"Хеш з БД: {user.password_hash}")
            result = bcrypt.checkpw(password.encode(), user.password_hash.encode())
            print(f"Результат перевірки: {result}")
            if result:
                request.session['user_id'] = user.id
                return redirect('director_panel')
            else:
                error = 'Невірний логін або пароль'
        except UserAuth.DoesNotExist:
            print(f"Користувача '{username}' не знайдено в БД")
            error = 'Невірний логін або пароль'
    return render(request, 'login_form.html', {'role': 'Директор', 'error': error})
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
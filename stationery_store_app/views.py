from django.shortcuts import render, redirect
import bcrypt
from .models import UserAuth, UserRegister

def home(request):
    return render(request, 'home.html')

def login(request, role):
    error = None
    redirect_urls = {
        'director': 'director_panel',
        'manager': 'manager_panel',
        'seller': 'seller_panel',
    }

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        try:
            user = UserAuth.objects.get(login=username)
            if bcrypt.checkpw(password.encode(), user.password_hash.encode()):
                request.session['user_id'] = user.id
                return redirect(redirect_urls.get(role, 'home'))
            else:
                error = 'Невірний логін або пароль'
        except UserAuth.DoesNotExist:
            error = 'Невірний логін або пароль'

    roles_titles = {
        'director': 'Директор',
        'manager': 'Менеджер',
        'seller': 'Продавець'
    }
    return render(request, 'login_form.html', {
        'role_display': roles_titles.get(role, role),
        'role_latin': role, 'error': error
    })

def register(request, role):
    roles_titles = {
        'director': 'Директор',
        'manager': 'Менеджер',
        'seller': 'Продавець'
    }
    display_role = roles_titles.get(role, role)
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        full_name = request.POST.get('full_name')
        store_id = username = request.POST.get('store_id')
        hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user_register = UserRegister.objects.create(
            full_name = full_name,
            staff_position = display_role,
            store_id = store_id
        )
        UserAuth.objects.create(login = username,
                                password_hash = hashed_pw,
                                staff = user_register)
        return redirect('login', role = role)
    return render(request, 'register_form.html', {
        'role_display': display_role,
        'role_latin': role
    })
def reset_password(request):
    if request.method == "POST":
        username = request.POST.get('username')
        new_password = request.POST.get('new_password')
        try:
            user = UserAuth.objects.get(login = username)
            hashed_pw = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            user.password_hash = hashed_pw
            user.save()
            return redirect('home')
        except UserAuth.DoesNotExist:
            return render(request, 'reset_password.html', {'error':'Користувача не знайдено'})
    return render(request,'reset_password.html')

def director_panel(request):
    return render(request, 'director_panel.html')
def manager_panel(request):
    return render(request, 'manager_panel.html')
def seller_panel(request):
    return render(request, 'seller_panel.html')
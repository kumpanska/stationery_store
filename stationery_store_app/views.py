from django.shortcuts import render, redirect
import bcrypt
from django.db import connection

def home(request):
    return render(request, 'home.html')

def login(request, role):
    error = None
    redirect_urls = {
        'director': 'director_panel',
        'manager': 'manager_panel',
        'seller': 'seller_panel',
    }
    roles_titles = {
        'director': 'Директор',
        'manager': 'Менеджер',
        'seller': 'Продавець'
    }
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        if not username or not password:
            error = "Заповніть усі поля"
        else:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, password_hash FROM user_auth WHERE login = %s", [username])
                user = cursor.fetchone()
                if user:
                    user_id, password_hash = user
                    if bcrypt.checkpw(password.encode(), password_hash.encode()):
                        request.session['user_id'] = user_id
                        return redirect(redirect_urls.get(role, 'home'))
                    else:
                        error = "Невірний логін або пароль"
                else:
                    error = "Невірний логін або пароль"
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
        store_id = request.POST.get('store_id')
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM store WHERE id = %s", [store_id])
            store = cursor.fetchone()
            if not store:
                return render(request, 'register_form.html', {
                    'role_display': display_role,
                    'role_latin': role,
                    'error': 'Магазин з таким ID не існує'
                })
            hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            cursor.execute("""
                INSERT INTO staff (full_name, staff_position, store_id)
                VALUES (%s, %s, %s) RETURNING id
            """, [full_name, display_role, store_id])
            staff_id = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO user_auth (login, password_hash, staff_id)
                VALUES (%s, %s, %s)
            """, [username, hashed_pw, staff_id])
        return redirect('login', role=role)
    return render(request, 'register_form.html', {
        'role_display': display_role,
        'role_latin': role
    })

def reset_password(request):
    if request.method == "POST":
        username = request.POST.get('username')
        new_password = request.POST.get('new_password')
        if not username or not new_password:
            return render(request, 'reset_password.html', {'error': 'Заповніть усі поля'})
        hashed_pw = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        with connection.cursor() as cursor:
            cursor.execute("UPDATE user_auth SET password_hash = %s WHERE login = %s",
                           [hashed_pw, username])
            if cursor.rowcount == 0:
                return render(request, 'reset_password.html', {'error': 'Користувача не знайдено'})
        return render(request, 'reset_password.html', {'success': 'Пароль успішно змінено'})
    return render(request, 'reset_password.html')

def director_panel(request):
    return render(request, 'director_panel.html')
def manager_panel(request):
    return render(request, 'manager_panel.html')
def seller_panel(request):
    return render(request, 'seller_panel.html')
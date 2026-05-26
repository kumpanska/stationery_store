import bcrypt
import plotly.graph_objects as go
from django.db import connection
from django.shortcuts import render, redirect
def home(request):
    return render(request, 'home.html')

def login(request, role):
    error = None
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
                cursor.execute("""
                               SELECT ua.id, ua.password_hash, s.store_id, st.store_name
                               FROM user_auth ua
                                        JOIN staff s ON ua.staff_id = s.id
                                        JOIN store st ON s.store_id = st.id
                               WHERE ua.login = %s
                               """, [username])
                user = cursor.fetchone()
                if user:
                    user_id, password_hash, store_id, store_name = user
                    if bcrypt.checkpw(password.encode(), password_hash.encode()):
                        request.session['user_id'] = user_id
                        return redirect(f'/{role}/panel/')
                    else:
                        error = "Невірний логін або пароль"
                else:
                    error = "Невірний логін або пароль"

    return render(request, 'login_form.html', {
        'role_display': roles_titles.get(role, role),
        'role_latin': role,
        'error': error
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
            cursor.execute("SELECT store_name FROM store WHERE id = %s", [store_id])
            store = cursor.fetchone()
            if not store:
                return render(request, 'register_form.html', {
                    'role_display': display_role,
                    'role_latin': role,
                    'error': 'Магазин з таким ID не існує'
                })
            store_name = store[0]
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
        return render(request, 'register_form.html', {
            'role_display': display_role,
            'role_latin': role,
            'success': f'Реєстрація успішна! Магазин: {store_name}'
        })
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

def build_sales_chart(sales_data):
    from collections import defaultdict
    by_date = defaultdict(lambda: {'amount': 0.0, 'sellers': []})
    for row in sales_data:
        d = row['date']
        by_date[d]['amount'] += row['amount']
        seller = row['seller']
        if seller not in by_date[d]['sellers']:
            by_date[d]['sellers'].append(seller)

    dates = sorted(by_date.keys())
    amounts = [by_date[d]['amount'] for d in dates]
    seller_labels = [', '.join(by_date[d]['sellers']) for d in dates]
    hover_texts = [
        f"<b>{d}</b><br>Сума: {by_date[d]['amount']:,.0f} грн<br>Продавці: {', '.join(by_date[d]['sellers'])}"
        for d in dates
    ]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=amounts,
        mode='lines+markers+text',
        name='Загальні продажі',
        line=dict(color='#4a7c59', width=3),
        marker=dict(size=9, color='#4a7c59', symbol='circle'),
        fill='tozeroy',
        fillcolor='rgba(74, 124, 89, 0.12)',
        text=[f"{a:,.0f} грн<br><span style='font-size:10px;color:#666'>{s}</span>"
              for a, s in zip(amounts, seller_labels)],
        textposition='top center',
        hovertext=hover_texts,
        hoverinfo='text',
    ))
    fig.update_layout(
        title=dict(text='Загальні продажі магазину за період', font=dict(size=17), x=0.5),
        xaxis=dict(
            title='Дата',
            tickformat='%d.%m',
            showgrid=True,
            gridcolor='#eeeeee',
        ),
        yaxis=dict(
            title='Сума (грн)',
            showgrid=True,
            gridcolor='#eeeeee',
            tickformat=',.0f',
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        hovermode='x unified',
        margin=dict(l=60, r=30, t=70, b=60),
        height=430,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)

def director_panel(request):
    user_auth_id = request.session.get('user_id')
    if not user_auth_id:
        return redirect('/login/director/')
    store_id = None
    store_info = None
    sellers = []
    managers = []
    suppliers = []
    sales_data = []
    top_products = []
    success = None
    form_submitted = False
    chart_html = None

    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT s.store_id
                       FROM staff s
                                JOIN user_auth ua ON ua.staff_id = s.id
                       WHERE ua.id = %s
                       """, [user_auth_id])
        row = cursor.fetchone()
        if not row:
            return redirect('/login/director/')
        store_id = row[0]

        cursor.execute("SELECT store_name, address FROM store WHERE id = %s", [store_id])
        store_info = cursor.fetchone()
        cursor.execute(
            "SELECT id, full_name FROM staff WHERE store_id = %s AND staff_position = 'Продавець'",
            [store_id]
        )
        sellers = [{'id': r[0], 'full_name': r[1]} for r in cursor.fetchall()]
        cursor.execute(
            "SELECT id, full_name FROM staff WHERE store_id = %s AND staff_position = 'Менеджер'",
            [store_id]
        )
        managers = [{'id': r[0], 'full_name': r[1]} for r in cursor.fetchall()]
        cursor.execute(
            "SELECT id, company_name, contact_full_name, phone, email FROM supplier"
        )
        suppliers = [
            {'id': r[0], 'company_name': r[1], 'contact_full_name': r[2], 'phone': r[3], 'email': r[4]}
            for r in cursor.fetchall()
        ]

        if request.method == 'POST':
            form_type = request.POST.get('form_type')

            if form_type == 'sales_stats':
                form_submitted = True
                start_date = request.POST.get('start_date')
                end_date = request.POST.get('end_date')
                if start_date and end_date:
                    cursor.execute("""
                                   SELECT r.date, SUM(r.total_amount), s.full_name
                                   FROM receipt r
                                            JOIN staff s ON r.staff_id = s.id
                                   WHERE r.store_id = %s
                                     AND r.date BETWEEN %s AND %s
                                   GROUP BY r.date, s.full_name
                                   ORDER BY r.date
                                   """, [store_id, start_date, end_date])
                    rows = cursor.fetchall()
                    sales_data = [
                        {'date': str(r[0]), 'amount': float(r[1]), 'seller': r[2]}
                        for r in rows
                    ]
                    if sales_data:
                        chart_html = build_sales_chart(sales_data)

            elif form_type == 'add_supplier':
                company_name = request.POST.get('company_name')
                contact_full_name = request.POST.get('contact_full_name')
                phone = request.POST.get('phone')
                email = request.POST.get('email')
                cursor.execute("""
                               INSERT INTO supplier (company_name, contact_full_name, phone, email)
                               VALUES (%s, %s, %s, %s)
                               """, [company_name, contact_full_name, phone, email])
                success = 'Постачальника успішно додано!'
                cursor.execute(
                    "SELECT id, company_name, contact_full_name, phone, email FROM supplier"
                )
                suppliers = [
                    {'id': r[0], 'company_name': r[1], 'contact_full_name': r[2], 'phone': r[3], 'email': r[4]}
                    for r in cursor.fetchall()
                ]
        cursor.execute("""
                       SELECT p.product_name, SUM(sp.quantity) as total_sold
                       FROM sale_position sp
                                JOIN product p ON sp.product_id = p.id
                                JOIN receipt r ON sp.receipt_id = r.id
                       WHERE r.store_id = %s
                       GROUP BY p.product_name
                       ORDER BY total_sold DESC LIMIT 5
                       """, [store_id])
        top_products = [{'name': r[0], 'sold': r[1]} for r in cursor.fetchall()]

    return render(request, 'director_panel.html', {
        'store_info': store_info,
        'sellers': sellers,
        'managers': managers,
        'suppliers': suppliers,
        'sales_data': sales_data,
        'top_products': top_products,
        'success': success,
        'form_submitted': form_submitted,
        'chart_html': chart_html,
    })

def manager_panel(request):
    if not request.session.get('user_id'):
        return redirect('/login/manager/')
    return render(request, 'manager_panel.html')


def seller_panel(request):
    if not request.session.get('user_id'):
        return redirect('/login/seller/')
    return render(request, 'seller_panel.html')
import bcrypt
import plotly.graph_objects as go
from collections import defaultdict
from django.db import connection, transaction
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
            try:
                with transaction.atomic():
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
            except Exception as e:
                return render(request, 'register_form.html', {
                    'role_display': display_role,
                    'role_latin': role,
                    'error': f'Помилка при реєстрації: {e}'
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
    by_date = defaultdict(lambda: {'amount': 0.0, 'sellers': set(), 'payments': set()})
    for row in sales_data:
        d = row['date']
        by_date[d]['amount'] += row['amount']
        by_date[d]['sellers'].add(row['seller'])
        by_date[d]['payments'].add(row['payment_method'])

    dates = sorted(by_date.keys())
    amounts = [by_date[d]['amount'] for d in dates]
    hover_texts = [
        f"<b>{d}</b><br>Сума: {by_date[d]['amount']:,.0f} грн"
        f"<br>Продавці: {', '.join(by_date[d]['sellers'])}"
        f"<br>Спосіб оплати: {', '.join(by_date[d]['payments'])}"
        for d in dates
    ]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=amounts,
        mode='lines+markers+text',
        name='Загальні продажі',
        line=dict(color='#4a7c59', width=3),
        marker=dict(size=9, color='#4a7c59', symbol='circle'),
        fill='tozeroy',
        fillcolor='rgba(74, 124, 89, 0.12)',
        text=[f"{a:,.0f} грн" for a in amounts],
        textposition='top center',
        hovertext=hover_texts,
        hoverinfo='text',
    ))
    fig.update_layout(
        title=dict(text='Загальні продажі магазину за період', font=dict(size=17), x=0.5),
        xaxis=dict(title='Дата', tickformat='%d.%m', showgrid=True, gridcolor='#eeeeee'),
        yaxis=dict(title='Сума (грн)', showgrid=True, gridcolor='#eeeeee', tickformat=',.0f'),
        plot_bgcolor='white', paper_bgcolor='white',
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
    seller_stats = []
    success = None
    error = None
    form_submitted = False
    chart_html = None
    selected_seller_id = None
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

        cursor.execute("""
                       SELECT id, full_name
                       FROM staff
                       WHERE store_id = %s
                         AND staff_position = 'Продавець'
                       """, [store_id])
        sellers = [{'id': r[0], 'full_name': r[1]} for r in cursor.fetchall()]
        cursor.execute("""
                       SELECT id, full_name
                       FROM staff
                       WHERE store_id = %s
                         AND staff_position = 'Менеджер'
                       """, [store_id])
        managers = [{'id': r[0], 'full_name': r[1]} for r in cursor.fetchall()]
        cursor.execute("""
                       SELECT sup.id, sup.company_name, sup.contact_full_name, sup.phone, sup.email
                       FROM supplier sup
                                JOIN store_supplier ss ON ss.supplier_id = sup.id
                       WHERE ss.store_id = %s
                       ORDER BY sup.company_name
                       """, [store_id])
        suppliers = [
            {'id': r[0], 'company_name': r[1], 'contact_full_name': r[2], 'phone': r[3], 'email': r[4]}
            for r in cursor.fetchall()
        ]
        cursor.execute("SELECT id, company_name FROM supplier ORDER BY company_name")
        all_suppliers = [{'id': r[0], 'company_name': r[1]} for r in cursor.fetchall()]
        cursor.execute("""
                       SELECT p.product_name, SUM(sp.quantity) AS total_sold
                       FROM sale_position sp
                                JOIN product p ON sp.product_id = p.id
                                JOIN receipt r ON sp.receipt_id = r.id
                       WHERE r.store_id = %s
                       GROUP BY p.product_name
                       ORDER BY total_sold DESC LIMIT 5
                       """, [store_id])
        top_products = [{'name': r[0], 'sold': r[1]} for r in cursor.fetchall()]

        if request.method == 'POST':
            form_type = request.POST.get('form_type')
            if form_type == 'sales_stats':
                form_submitted = True
                start_date = request.POST.get('start_date')
                end_date = request.POST.get('end_date')
                selected_seller_id = request.POST.get('seller_id') or None
                if start_date and end_date:
                    if selected_seller_id:
                        cursor.execute("""
                                       SELECT r.date, r.time, SUM(r.total_amount), s.full_name, r.payment_method
                                       FROM receipt r
                                                JOIN staff s ON r.staff_id = s.id
                                       WHERE r.store_id = %s
                                         AND r.date BETWEEN %s AND %s
                                         AND r.staff_id = %s
                                       GROUP BY r.date, r.time, s.full_name, r.payment_method
                                       ORDER BY r.date DESC, r.time DESC
                                       """, [store_id, start_date, end_date, selected_seller_id])
                    else:
                        cursor.execute("""
                                       SELECT r.date, r.time, SUM(r.total_amount), s.full_name, r.payment_method
                                       FROM receipt r
                                                JOIN staff s ON r.staff_id = s.id
                                       WHERE r.store_id = %s
                                         AND r.date BETWEEN %s AND %s
                                       GROUP BY r.date, r.time, s.full_name, r.payment_method
                                       ORDER BY r.date DESC, r.time DESC
                                       """, [store_id, start_date, end_date])
                    rows = cursor.fetchall()
                    sales_data = [
                        {
                            'date': f"{r[0]} {r[1].strftime('%H:%M:%S') if r[1] else ''}".strip(),
                            'amount': float(r[2]),
                            'seller': r[3],
                            'payment_method': r[4]
                        }
                        for r in rows
                    ]

                    if sales_data and 'build_sales_chart' in globals():
                        chart_html = build_sales_chart(sales_data)

                    cursor.execute("""
                                   SELECT s.full_name,
                                          COUNT(r.id)         AS receipts_count,
                                          SUM(r.total_amount) AS total
                                   FROM receipt r
                                            JOIN staff s ON r.staff_id = s.id
                                   WHERE r.store_id = %s
                                     AND r.date BETWEEN %s AND %s
                                   GROUP BY s.full_name
                                   ORDER BY total DESC
                                   """, [store_id, start_date, end_date])
                    seller_stats = [
                        {'name': r[0], 'receipts': r[1], 'total': float(r[2])}
                        for r in cursor.fetchall()
                    ]

            elif form_type == 'add_supplier':
                supplier_id_to_add = request.POST.get('existing_supplier_id', '').strip()
                if supplier_id_to_add:
                    cursor.execute("""
                                   SELECT 1
                                   FROM store_supplier
                                   WHERE store_id = %s
                                     AND supplier_id = %s
                                   """, [store_id, supplier_id_to_add])
                    already_linked = cursor.fetchone()
                    if already_linked:
                        error = 'Цей постачальник вже прив\'язаний до магазину.'
                    else:
                        cursor.execute("""
                                       INSERT INTO store_supplier (store_id, supplier_id)
                                       VALUES (%s, %s)
                                       """, [store_id, supplier_id_to_add])
                        cursor.execute(
                            "SELECT company_name FROM supplier WHERE id = %s",
                            [supplier_id_to_add]
                        )
                        name = cursor.fetchone()[0]
                        success = f'Постачальника "{name}" успішно прив\'язано до магазину!'

                        cursor.execute("""
                                       SELECT sup.id, sup.company_name, sup.contact_full_name, sup.phone, sup.email
                                       FROM supplier sup
                                                JOIN store_supplier ss ON ss.supplier_id = sup.id
                                       WHERE ss.store_id = %s
                                       ORDER BY sup.company_name
                                       """, [store_id])
                        suppliers = [
                            {'id': r[0], 'company_name': r[1], 'contact_full_name': r[2],
                             'phone': r[3], 'email': r[4]}
                            for r in cursor.fetchall()
                        ]
                else:
                    error = 'Оберіть постачальника зі списку.'

            elif form_type == 'remove_supplier':
                supplier_id = request.POST.get('supplier_id')
                cursor.execute(
                    "SELECT company_name FROM supplier WHERE id = %s", [supplier_id]
                )
                sup = cursor.fetchone()
                if sup:
                    cursor.execute("""
                                   DELETE
                                   FROM store_supplier
                                   WHERE store_id = %s
                                     AND supplier_id = %s
                                   """, [store_id, supplier_id])
                    success = f'Постачальника "{sup[0]}" відв\'язано від магазину!'
                    cursor.execute("""
                                   SELECT sup.id, sup.company_name, sup.contact_full_name, sup.phone, sup.email
                                   FROM supplier sup
                                            JOIN store_supplier ss ON ss.supplier_id = sup.id
                                   WHERE ss.store_id = %s
                                   ORDER BY sup.company_name
                                   """, [store_id])
                    suppliers = [
                        {'id': r[0], 'company_name': r[1], 'contact_full_name': r[2],
                         'phone': r[3], 'email': r[4]}
                        for r in cursor.fetchall()
                    ]
                else:
                    error = 'Постачальника не знайдено.'

    return render(request, 'director_panel.html', {
        'store_id': store_id,
        'store_info': store_info,
        'sellers': sellers,
        'managers': managers,
        'suppliers': suppliers,
        'sales_data': sales_data,
        'seller_stats': seller_stats,
        'top_products': top_products,
        'success': success,
        'error': error,
        'form_submitted': form_submitted,
        'chart_html': chart_html,
        'selected_seller_id': selected_seller_id,
        'all_suppliers': all_suppliers,
    })

def manager_panel(request):
    user_auth_id = request.session.get('user_id')
    if not user_auth_id:
        return redirect('/login/manager/')
    store_id = None
    store_info = None
    products = []
    staff_list = []
    categories = []
    suppliers = []
    arrivals_list = []
    success = None
    error = None
    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT s.store_id
                       FROM staff s
                                JOIN user_auth ua ON ua.staff_id = s.id
                       WHERE ua.id = %s
                       """, [user_auth_id])
        row = cursor.fetchone()
        if not row:
            return redirect('/login/manager/')
        store_id = row[0]
        cursor.execute("SELECT store_name, address FROM store WHERE id = %s", [store_id])
        store_info = cursor.fetchone()
        cursor.execute("SELECT id, category_name FROM products_category ORDER BY category_name")
        categories = [{'id': r[0], 'name': r[1]} for r in cursor.fetchall()]
        cursor.execute("""
                       SELECT s.id, s.company_name
                       FROM supplier s
                                JOIN store_supplier ss ON ss.supplier_id = s.id
                       WHERE ss.store_id = %s
                       ORDER BY s.company_name
                       """, [store_id])
        suppliers = [{'id': r[0], 'name': r[1]} for r in cursor.fetchall()]

        def get_filtered_products():
            cursor.execute("""
                           SELECT p.id,
                                  p.product_name,
                                  p.sale_price,
                                  sp.local_purchase_price AS purchase_price,
                                  sp.quantity,
                                  p.barcode,
                                  pc.category_name,
                                  sup.company_name
                           FROM product p
                                    JOIN products_category pc ON p.category_id = pc.id
                                    JOIN supplier sup ON p.supplier_id = sup.id
                                    JOIN store_supplier ss ON ss.supplier_id = sup.id AND ss.store_id = %s
                                    JOIN store_product sp ON sp.product_id = p.id AND sp.store_id = %s
                           ORDER BY pc.category_name, p.product_name
                           """, [store_id, store_id])
            return [
                {
                    'id': r[0], 'name': r[1], 'sale_price': float(r[2]),
                    'purchase_price': float(r[3]), 'quantity': r[4],
                    'barcode': r[5], 'category': r[6], 'supplier': r[7],
                    'low_stock': r[4] <= 5
                }
                for r in cursor.fetchall()
            ]

        def get_staff_list():
            cursor.execute("""
                           SELECT id, full_name, staff_position
                           FROM staff
                           WHERE store_id = %s
                             AND staff_position = 'Продавець'
                           ORDER BY staff_position, full_name
                           """, [store_id])
            return [{'id': r[0], 'full_name': r[1], 'position': r[2]} for r in cursor.fetchall()]

        def get_arrivals_list():
            cursor.execute("""
                           SELECT ag.date,
                                  sup.company_name,
                                  p.product_name,
                                  pa.quantity,
                                  pa.purchase_price,
                                  ag.total_amount
                           FROM arrival_of_goods ag
                                    JOIN supplier sup ON ag.supplier_id = sup.id
                                    JOIN position_of_arrival pa ON pa.arrival_of_goods_id = ag.id
                                    JOIN product p ON pa.product_id = p.id
                           WHERE ag.store_id = %s
                           ORDER BY ag.date DESC, ag.id DESC
                           """, [store_id])
            return [
                {
                    'date': r[0],
                    'supplier': r[1],
                    'product': r[2],
                    'quantity': r[3],
                    'purchase_price': float(r[4]),
                    'total_amount': float(r[5]),
                }
                for r in cursor.fetchall()
            ]

        if request.method == 'POST':
            form_type = request.POST.get('form_type')
            if form_type == 'add_product':
                name = request.POST.get('product_name', '').strip()
                sale_price = request.POST.get('sale_price')
                purchase_price = request.POST.get('purchase_price')
                quantity = request.POST.get('quantity')
                barcode = request.POST.get('barcode', '').strip() or None
                category_id = request.POST.get('category_id')
                supplier_id = request.POST.get('supplier_id')
                if name and sale_price and purchase_price and quantity and category_id and supplier_id:
                    try:
                        with transaction.atomic():
                            cursor.execute("""
                                           INSERT INTO product (product_name, sale_price, barcode, category_id, supplier_id)
                                           VALUES (%s, %s, %s, %s, %s) RETURNING id
                                           """, [name, sale_price, barcode, category_id, supplier_id])
                            new_product_id = cursor.fetchone()[0]
                            cursor.execute("""
                                           INSERT INTO store_product (store_id, product_id, quantity, local_purchase_price)
                                           VALUES (%s, %s, %s, %s)
                                           """, [store_id, new_product_id, quantity, purchase_price])
                        success = f'Товар "{name}" успішно додано та прив\'язано до магазину!'
                    except Exception as e:
                        error = f"Помилка бази даних: {e}"
                else:
                    error = "Заповніть усі обов'язкові поля товару."
            elif form_type == 'edit_product':
                product_id = request.POST.get('product_id')
                name = request.POST.get('product_name', '').strip()
                purchase_price = request.POST.get('purchase_price')
                quantity = request.POST.get('quantity')
                try:
                    with transaction.atomic():
                        cursor.execute("""
                                       UPDATE store_product
                                       SET quantity=%s,
                                           local_purchase_price=%s
                                       WHERE store_id = %s
                                         AND product_id = %s
                                       """, [quantity, purchase_price, store_id, product_id])
                    success = f'Товар "{name}" оновлено!'
                except Exception as e:
                    error = f"Помилка оновлення: {e}"

            elif form_type == 'delete_product':
                product_id = request.POST.get('product_id')
                cursor.execute("SELECT product_name FROM product WHERE id=%s", [product_id])
                p = cursor.fetchone()
                if p:
                    cursor.execute("DELETE FROM store_product WHERE product_id=%s AND store_id=%s", [product_id, store_id])
                    success = f'Товар "{p[0]}" прибрано з асортименту магазину!'
                else:
                    error = 'Товар не знайдено.'

            elif form_type == 'delete_staff':
                staff_id = request.POST.get('staff_id')
                cursor.execute("SELECT full_name FROM staff WHERE id=%s AND store_id=%s", [staff_id, store_id])
                s = cursor.fetchone()
                if s:
                    with transaction.atomic():
                        cursor.execute("DELETE FROM user_auth WHERE staff_id=%s", [staff_id])
                        cursor.execute("DELETE FROM staff WHERE id=%s", [staff_id])
                    success = f'Працівника "{s[0]}" видалено!'
                else:
                    error = 'Працівника не знайдено або він не належить цьому магазину.'

            elif form_type == 'add_arrival':
                supplier_id = request.POST.get('supplier_id')
                product_id = request.POST.get('product_id')
                quantity = request.POST.get('quantity')
                price = request.POST.get('purchase_price')
                if not all([supplier_id, product_id, quantity, price]):
                    error = "Заповніть усі поля надходження."
                else:
                    total_amount = float(quantity) * float(price)
                    cursor.execute("SELECT 1 FROM store_supplier WHERE store_id = %s AND supplier_id = %s", [store_id, supplier_id])
                    if not cursor.fetchone():
                        error = "Цей постачальник не прив'язаний до вашого магазину."
                    else:
                        cursor.execute("SELECT 1 FROM product WHERE id = %s AND supplier_id = %s", [product_id, supplier_id])
                        if not cursor.fetchone():
                            error = "Цей товар не належить обраному постачальнику."
                        else:
                            try:
                                with transaction.atomic():
                                    cursor.execute("""
                                                   INSERT INTO arrival_of_goods (date, supplier_id, store_id, total_amount)
                                                   VALUES (CURRENT_DATE, %s, %s, %s) RETURNING id
                                                   """, [supplier_id, store_id, total_amount])
                                    arrival_id = cursor.fetchone()[0]
                                    cursor.execute("""
                                                   INSERT INTO position_of_arrival
                                                       (arrival_of_goods_id, product_id, quantity, purchase_price)
                                                   VALUES (%s, %s, %s, %s)
                                                   """, [arrival_id, product_id, quantity, price])
                                    cursor.execute("""
                                                   UPDATE store_product
                                                   SET quantity = quantity + %s,
                                                       local_purchase_price = %s
                                                   WHERE store_id = %s AND product_id = %s
                                                   """, [quantity, price, store_id, product_id])
                                success = "Надходження успішно додано!"
                            except Exception as e:
                                error = f"Помилка бази даних при проведені надходження: {e}"

        products = get_filtered_products()
        staff_list = get_staff_list()
        arrivals_list = get_arrivals_list()

    return render(request, 'manager_panel.html', {
        'store_info': store_info,
        'products': products,
        'staff_list': staff_list,
        'categories': categories,
        'suppliers': suppliers,
        'arrivals_list': arrivals_list,
        'success': success,
        'error': error,
    })


def seller_panel(request):
    user_auth_id = request.session.get('user_id')
    if not user_auth_id:
        return redirect('/login/seller/')
    store_id = None
    staff_id = None
    store_info = None
    products = []
    my_sales = []
    categories = []
    success = None
    error = None
    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT s.id, s.store_id
                       FROM staff s
                                JOIN user_auth ua ON ua.staff_id = s.id
                       WHERE ua.id = %s
                       """, [user_auth_id])
        row = cursor.fetchone()
        if not row:
            return redirect('/login/seller/')
        staff_id, store_id = row
        cursor.execute("SELECT store_name, address FROM store WHERE id = %s", [store_id])
        store_info = cursor.fetchone()
        cursor.execute("SELECT id, category_name FROM products_category ORDER BY category_name")
        categories = [{'id': r[0], 'name': r[1]} for r in cursor.fetchall()]

        def get_products():
            cursor.execute("""
                           SELECT p.id, p.product_name, p.sale_price, sp.quantity, pc.category_name
                           FROM product p
                                    JOIN products_category pc ON p.category_id = pc.id
                                    JOIN store_product sp ON sp.product_id = p.id
                           WHERE sp.store_id = %s
                             AND sp.quantity > 0
                           ORDER BY pc.category_name, p.product_name
                           """, [store_id])
            return [
                {
                    'id': r[0], 'name': r[1],
                    'sale_price': float(r[2]),
                    'quantity': r[3],
                    'category': r[4],
                }
                for r in cursor.fetchall()
            ]

        def get_my_sales():
            cursor.execute("""
                           SELECT r.id,
                                  r.date,
                                  r.time,
                                  r.total_amount,
                                  r.payment_method,
                                  COUNT(sp.id) AS items_count
                           FROM receipt r
                                    JOIN sale_position sp ON sp.receipt_id = r.id
                           WHERE r.staff_id = %s
                           GROUP BY r.id, r.date, r.time, r.total_amount, r.payment_method
                           ORDER BY r.date DESC, r.time DESC LIMIT 50
                           """, [staff_id])
            return [
                {
                    'id': r[0],
                    'date': f"{r[1]} {r[2].strftime('%H:%M:%S') if r[2] else ''}".strip(),
                    'total_amount': float(r[3]),
                    'payment_method': r[4],
                    'items_count': r[5],
                }
                for r in cursor.fetchall()
            ]

        if request.method == 'POST':
            form_type = request.POST.get('form_type')
            if form_type == 'new_sale':
                payment_method = request.POST.get('payment_method')
                product_ids = request.POST.getlist('product_id')
                quantities = request.POST.getlist('sale_quantity')
                items = [
                    (pid, int(qty))
                    for pid, qty in zip(product_ids, quantities)
                    if pid and qty and int(qty) > 0
                ]
                if not items:
                    error = "Додайте хоча б один товар до продажу."
                elif not payment_method:
                    error = "Оберіть спосіб оплати."
                else:
                    stock_error = None
                    validated_items = []
                    total_amount = 0.0
                    for product_id, qty in items:
                        cursor.execute("""
                                       SELECT p.product_name, sp.quantity, p.sale_price
                                       FROM product p
                                       JOIN store_product sp ON sp.product_id = p.id
                                       WHERE p.id = %s AND sp.store_id = %s
                                       """, [product_id, store_id])
                        prod = cursor.fetchone()
                        if not prod:
                            stock_error = "Товар не знайдено на складі магазину."
                            break
                        product_name, stock_qty, sale_price = prod
                        sale_price = float(sale_price)
                        if stock_qty < qty:
                            stock_error = f'Недостатньо товару "{product_name}": у вашому магазині є {stock_qty}, потрібно {qty}.'
                            break
                        total_amount += sale_price * qty
                        validated_items.append((product_id, qty, sale_price))
                    if stock_error:
                        error = stock_error
                    else:
                        try:
                            with transaction.atomic():
                                cursor.execute("""
                                               INSERT INTO receipt (date, time, total_amount, payment_method, staff_id, store_id)
                                               VALUES (CURRENT_DATE, CURRENT_TIME, %s, %s, %s, %s) RETURNING id
                                               """, [total_amount, payment_method, staff_id, store_id])
                                receipt_id = cursor.fetchone()[0]
                                for product_id, qty, price in validated_items:
                                    cursor.execute("""
                                                   INSERT INTO sale_position (receipt_id, product_id, quantity, sale_price)
                                                   VALUES (%s, %s, %s, %s)
                                                   """, [receipt_id, product_id, qty, price])

                                    cursor.execute("""
                                                   UPDATE store_product
                                                   SET quantity = quantity - %(qty)s
                                                   WHERE store_id = %(store_id)s
                                                     AND product_id = %(product_id)s
                                                   """, {
                                                       'qty': qty,
                                                       'store_id': store_id,
                                                       'product_id': product_id
                                                   })
                            success = f"Продаж на суму {total_amount:,.2f} грн успішно оформлено!"
                        except Exception as e:
                            error = f"Помилка при збереженні чека у базі даних: {e}"

        products = get_products()
        my_sales = get_my_sales()

    return render(request, 'seller_panel.html', {
        'store_info': store_info,
        'products': products,
        'my_sales': my_sales,
        'categories': categories,
        'success': success,
        'error': error,
    })

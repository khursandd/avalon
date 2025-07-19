from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group, User
from django.contrib.auth.hashers import make_password
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import PermissionDenied
from django.utils.timezone import now
from django.db.models import Q, Sum, Max
from django.db import transaction



from .models import Fabric, WorkerProductLog, Product, MaterialForProduct, MaterialTransaction, ProductTransaction
from .decorators import is_admin_or_superuser
from .forms import FabricForm, MaterialTransactionForm, ProductForm

from datetime import timedelta
from decimal import Decimal


def _admin_only(user):
    return user.is_superuser or user.groups.filter(name='admin').exists()


# Create your views here.


@login_required
def role_based_home(request):
    user = request.user
    products = Product.objects.all()

    # === Считаем агрегаты по логам (количество и последняя дата производства)
    product_stats = (
        WorkerProductLog.objects
        .values('product')  # группировка по продукту
        .annotate(
            total_qty=Sum('quantity'),
            last_date=Max('date')
        )
    )
    stats_map = {row['product']: row for row in product_stats}

    # === Заполняем дополнительные поля для каждого продукта
    for p in products:
        stat = stats_map.get(p.id)
        p.total_qty = stat['total_qty'] if stat else 0  # всего произведено
        p.last_produced = stat['last_date'] if stat else None
        p.total_value = (p.price_per_unit or 0) * (p.quantity or 0)  # общая стоимость остатка
        p.stock_qty = p.quantity or 0  # остаток на складе

    # ===== SUPERUSER =====
    if user.is_superuser:
        admins = Group.objects.get(name='admin').user_set.all()[:3]
        workers = Group.objects.get(name='worker').user_set.all()[:3]
        no_role_users = User.objects.filter(groups__isnull=True)[:3]
        fabrics = Fabric.objects.all()

        # Общая стоимость ткани
        for fabric in fabrics:
            qty = Decimal(fabric.quantity or 0)
            price = fabric.price or Decimal('0.00')
            fabric.total_price = qty * price

        context = {
            'admins': admins,
            'workers': workers,
            'fabrics': fabrics,
            'products': products,
            'no_rule_users': no_role_users,
            'title': f'Superuser page {user.username}',
        }
        return render(request, 'main/for_superuser.html', context)

    # ===== ADMIN =====
    elif user.groups.filter(name='admin').exists():
        workers = Group.objects.get(name='worker').user_set.all()
        fabrics = Fabric.objects.all()

        for fabric in fabrics:
            qty = Decimal(fabric.quantity or 0)
            price = fabric.price or Decimal('0.00')
            fabric.total_price = qty * price

        context = {
            'title': f'{user.username} page',
            'fabrics': fabrics,
            'workers': workers,
            'products': products,
        }
        return render(request, 'main/for_admins.html', context)

    # ===== WORKER =====
    elif user.groups.filter(name='worker').exists():
        logs = WorkerProductLog.objects.filter(worker=user)
        period = request.GET.get('period', 'all')

        current_time = now()
        if period == 'week':
            start_date = current_time - timedelta(weeks=1)
        elif period == 'month':
            start_date = current_time - timedelta(days=30)
        elif period == '3months':
            start_date = current_time - timedelta(days=90)
        elif period == '6months':
            start_date = current_time - timedelta(days=180)
        else:
            start_date = None

        if start_date:
            logs = logs.filter(date__gte=start_date)

        logs = logs.order_by('-date')

        context = {
            'recent_logs': logs,
            'user': user,
            'selected_period': period
        }
        return render(request, 'main/for_workers.html', context)

    # ===== NO ROLE =====
    else:
        return render(request, 'main/no_role.html')


def view_fabric(request, pk):
    fabric = get_object_or_404(Fabric, pk=pk)
    return render(request, 'main/view_fabric.html', {'fabric': fabric})


def home(request):
    return render(request, 'main/home.html')


def sign_up(request):
    if not (request.user.is_superuser or request.user.groups.filter(name='admin').exists()):
        return HttpResponseForbidden("Недостаточно прав.")
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home')
    else:
        form = UserCreationForm()

    return render(request, 'registration/sign_up.html', {'form': form})


def is_superuser(user):
    return user.is_superuser


@user_passes_test(is_superuser)
def manage_users(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        # Создание нового пользователя
        if action == 'create':
            username = request.POST.get('username')
            password = request.POST.get('password')
            group_name = request.POST.get('group')

            if username and password:
                user = User.objects.create(
                    username=username,
                    password=make_password(password)
                )
                if group_name:
                    group = Group.objects.get(name=group_name)
                    user.groups.add(group)

        # Удаление пользователя
        elif action == 'delete':
            user_id = request.POST.get('user_id')
            User.objects.filter(id=user_id).delete()

        # Обновление пользователя
        elif action == 'update':
            user_id = request.POST.get('user_id')
            new_username = request.POST.get('username')
            new_password = request.POST.get('password')
            group_name = request.POST.get('group')

            user = get_object_or_404(User, id=user_id)

            if new_username:
                user.username = new_username
            if new_password:
                user.password = make_password(new_password)
            if group_name:
                user.groups.clear()
                group = Group.objects.get(name=group_name)
                user.groups.add(group)

            user.save()

        return redirect('home')

    users = User.objects.all().exclude(is_superuser=True)
    groups = Group.objects.all()

    return render(request, 'main/manage_users.html', {
        'users': users,
        'groups': groups
    })


@user_passes_test(is_admin_or_superuser)
def add_product(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        is_active = bool(request.POST.get('is_active'))
        price = request.POST.get('price')  # необязательно — если есть поле
        image = request.FILES.get('image')

        if not name:
            return render(request, 'product/add_product.html', {
                'error': 'Название обязательно.'
            })

        # если в модели Product есть price и image — учитываем
        kwargs = {'name': name, 'is_active': is_active}
        if hasattr(Product, 'price_per_unit') and price not in (None, ''):
            kwargs['price_per_unit'] = price
        if hasattr(Product, 'image') and image:
            kwargs['image'] = image

        Product.objects.create(**kwargs)
        return redirect('home')

    return render(request, 'product/add_product.html')
from django.db.models import Sum, Max
from decimal import Decimal

from django.db.models import Sum, Max
from decimal import Decimal

@login_required
def view_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    # Считаем произведённое
    total_produced = (
        WorkerProductLog.objects.filter(product=product)
        .aggregate(total=Sum('quantity'))['total'] or 0
    )

    # Остаток = произведено + текущее количество (если quantity != произведено)
    current_qty = total_produced + (product.quantity or 0)

    # Общая стоимость остатков
    stock_value = current_qty * (product.price_per_unit or 0)

    last_date = (
        WorkerProductLog.objects.filter(product=product)
        .order_by('-date')
        .values_list('date', flat=True)
        .first()
    )

    recent_logs = WorkerProductLog.objects.filter(product=product).order_by('-date')[:10]

    context = {
        'product': product,
        'total_qty': total_produced,
        'current_qty': current_qty,  # теперь тут 324
        'stock_value': stock_value,
        'last_date': last_date,
        'recent_logs': recent_logs,
        'can_manage': request.user.is_superuser or request.user.groups.filter(name='admin').exists(),
    }

    return render(request, 'product/view_product.html', context)

@user_passes_test(is_admin_or_superuser)
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    # Сколько логов связано (через FK или по имени — на случай старых записей)
    logs_count_fk = WorkerProductLog.objects.filter(product=product).count()
    logs_count_name = WorkerProductLog.objects.filter(
        product__isnull=True, product_name=product.name
    ).count()
    total_logs_count = logs_count_fk + logs_count_name

    if request.method == 'POST':
        # Перед удалением ничего дополнительно делать не надо:
        # WorkerProductLog.product станет NULL (SET_NULL), product_name сохранится
        product.delete()
        return redirect('home')

    # GET -> показать подтверждение
    return render(request, 'product/delete_product.html', {
        'product': product,
        'logs_count_fk': logs_count_fk,
        'logs_count_name': logs_count_name,
        'total_logs_count': total_logs_count,
    })


@user_passes_test(is_admin_or_superuser)
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            return redirect('view_product', pk=product.pk)
    else:
        form = ProductForm(instance=product)

    return render(request, 'product/edit_product.html', {
        'form': form,
        'product': product,
    })



@login_required
def view_user(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    group = user_obj.groups.first()

    # Проверка прав
    if request.user.is_superuser:
        pass
    elif request.user.groups.filter(name='admin').exists():
        if user_obj.is_superuser or (group and group.name == 'admin'):
            raise PermissionDenied
    else:
        raise PermissionDenied

    # Фильтрация логов
    recent_logs = []
    if group and group.name == 'worker':
        recent_logs = WorkerProductLog.objects.filter(worker=user_obj)

        period = request.GET.get('period', 'all')
        current_time = now()

        if period == 'week':
            start_date = current_time - timedelta(weeks=1)
            recent_logs = recent_logs.filter(date__gte=start_date)
        elif period == 'month':
            start_date = current_time - timedelta(days=30)
            recent_logs = recent_logs.filter(date__gte=start_date)
        elif period == '3months':
            start_date = current_time - timedelta(days=90)
            recent_logs = recent_logs.filter(date__gte=start_date)
        elif period == '6months':
            start_date = current_time - timedelta(days=180)
            recent_logs = recent_logs.filter(date__gte=start_date)

        recent_logs = recent_logs.order_by('-date')

    return render(request, 'main/view_user.html', {
        'user_obj': user_obj,
        'group': group,
        'recent_logs': recent_logs,
        'selected_period': request.GET.get('period', 'all')
    })


def edit_user(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    current_group = user_obj.groups.first()  # группа редактируемого пользователя

    # --- ПРАВА ДОСТУПА -----------------------------------------------------
    if request.user.is_superuser:
        can_change_group = True
    elif request.user.groups.filter(name='admin').exists():
        # нельзя редактировать суперюзера или админа
        if user_obj.is_superuser or (current_group and current_group.name == 'admin'):
            raise PermissionDenied
        can_change_group = False  # админ НЕ меняет группу
    else:
        raise PermissionDenied
    # ----------------------------------------------------------------------

    if request.method == 'POST':
        new_username = (request.POST.get('username') or "").strip()
        new_password = request.POST.get('password') or ""
        new_group_name = request.POST.get('group') if can_change_group else None

        # --- Обновление имени пользователя ---
        if new_username and new_username != user_obj.username:
            # проверка уникальности
            if User.objects.filter(username=new_username).exclude(pk=user_obj.pk).exists():
                messages.error(request, "Пользователь с таким именем уже существует.")
            else:
                user_obj.username = new_username

        # --- Обновление пароля ---
        if new_password:
            user_obj.password = make_password(new_password)

        # --- Обновление группы (только суперюзер) ---
        if can_change_group and new_group_name:
            try:
                group = Group.objects.get(name=new_group_name)
            except Group.DoesNotExist:
                messages.error(request, f"Группа '{new_group_name}' не найдена.")
            else:
                user_obj.groups.clear()
                user_obj.groups.add(group)
                current_group = group  # обновим для контекста

        user_obj.save()
        messages.success(request, "Пользователь обновлён.")
        return redirect('view_user', pk=user_obj.pk)

    # GET — показать форму
    groups = Group.objects.all() if can_change_group else []  # админам список не нужен

    return render(request, 'main/edit_user.html', {
        'user_obj': user_obj,
        'current_group': current_group,
        'groups': groups,
        'can_change_group': can_change_group,
    })


@login_required
def add_fabric(request):
    if request.method == 'POST':
        form = FabricForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('home')
    else:
        form = FabricForm()
    return render(request, 'main/add_fabric.html', {'form': form})


@login_required
def edit_fabric(request, pk):
    fabric = get_object_or_404(Fabric, pk=pk)
    if request.method == 'POST':
        form = FabricForm(request.POST, request.FILES, instance=fabric)
        if form.is_valid():
            form.save()
            return redirect('home')
    else:
        form = FabricForm(instance=fabric)
    return render(request, 'main/edit_fabric.html', {'form': form, 'fabric': fabric})


@user_passes_test(is_admin_or_superuser)
def delete_fabric(request, pk):
    fabric = get_object_or_404(Fabric, pk=pk)
    fabric.delete()
    return redirect('home')


@user_passes_test(is_superuser)
def all_admins(request):
    admin_group = Group.objects.get(name='admin')
    admins = admin_group.user_set.all()
    return render(request, 'main/all_admins.html', {'admins': admins})


@user_passes_test(is_admin_or_superuser)
def all_workers(request):
    worker_group = Group.objects.get(name='worker')
    workers = worker_group.user_set.all()
    return render(request, 'main/all_workers.html', {'workers': workers})


@user_passes_test(is_admin_or_superuser)
def all_no_rule_users(request):
    users = User.objects.filter(groups__isnull=True)
    return render(request, 'main/all_no_rule_users.html', {'users': users})


@user_passes_test(is_admin_or_superuser)
def add_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if username and password:
            if User.objects.filter(username=username).exists():
                return render(request, 'main/add_user.html', {
                    'error': 'Пользователь с таким именем уже существует.'
                })

            user = User.objects.create(
                username=username,
                password=make_password(password)
            )
            # Добавляем в группу worker
            worker_group, _ = Group.objects.get_or_create(name='worker')
            user.groups.add(worker_group)

            return redirect('home')

    return render(request, 'main/add_user.html')


def add_worker_product(request):
    current_user = request.user
    # кто целевой работник?
    worker_username = request.GET.get('worker')
    target_user = None

    if current_user.is_superuser or current_user.groups.filter(name='admin').exists():
        if worker_username:
            target_user = User.objects.filter(username=worker_username).first()
        worker_group = Group.objects.filter(name='worker').first()
        workers = worker_group.user_set.all() if worker_group else User.objects.none()
    else:
        target_user = current_user
        workers = None

    # список продуктов (только активные)
    products = Product.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        # целевой работник
        if current_user.is_superuser or current_user.groups.filter(name='admin').exists():
            worker_username = request.POST.get('worker') or worker_username
            target_user = User.objects.filter(username=worker_username).first()
            if not target_user:
                return render(request, 'main/add_worker_product.html', {
                    'error': 'Пользователь не найден',
                    'workers': workers,
                    'products': products,
                    'target_user': None,
                })
        else:
            target_user = current_user

        product_id = request.POST.get('product')  # пришёл PK продукта
        product_obj = Product.objects.filter(pk=product_id).first()

        product_name_fallback = request.POST.get('product_name')  # вдруг добавишь поле вручную
        quantity = request.POST.get('quantity') or 0

        WorkerProductLog.objects.create(
            worker=target_user,
            product=product_obj,
            product_name=product_name_fallback or (product_obj.name if product_obj else ''),
            quantity=quantity,
        )
        return redirect('home')

    return render(request, 'main/add_worker_product.html', {
        'workers': workers,
        'products': products,
        'target_user': target_user,
    })




@login_required
@user_passes_test(is_admin_or_superuser)
def materials_in(request, pk):
    fabric = get_object_or_404(Fabric, pk=pk)

    if request.method == 'POST':
        raw_value = request.POST.get('value', '').strip()
        note = request.POST.get('note', '').strip()

        # валидация
        if not raw_value:
            messages.error(request, "Введите количество.")
            return redirect('materials_in', pk=fabric.pk)

        try:
            amount = Decimal(raw_value)
        except (InvalidOperation, TypeError):
            messages.error(request, "Неверное число.")
            return redirect('materials_in', pk=fabric.pk)

        if amount <= 0:
            messages.error(request, "Количество должно быть больше нуля.")
            return redirect('materials_in', pk=fabric.pk)

        # атомарно: обновляем склад + пишем транзакцию
        with transaction.atomic():
            fabric.refresh_from_db()  # на случай параллельных операций
            fabric.quantity = (fabric.quantity or Decimal('0')) + amount
            fabric.save()

            MaterialTransaction.objects.create(
                fabric=fabric,
                user=request.user,
                transaction_type=MaterialTransaction.IN,
                amount=amount,
                note=note or "Приход вручную",
            )

        messages.success(
            request,
            f"Добавлено {amount} {fabric.get_unit_display()} материала «{fabric.name}».",
        )
        return redirect('materials_history', pk=fabric.pk)

    # GET
    return render(request, 'materials/materials_in.html', {'fabric': fabric})


@login_required
@user_passes_test(is_admin_or_superuser)
def materials_out(request, pk):
    fabric = get_object_or_404(Fabric, pk=pk)

    if request.method == 'POST':
        raw_value = request.POST.get('value', '').strip()
        note = request.POST.get('note', '').strip()

        if not raw_value:
            messages.error(request, "Введите количество.")
            return redirect('materials_out', pk=fabric.pk)

        try:
            amount = Decimal(raw_value)
        except (InvalidOperation, TypeError):
            messages.error(request, "Неверное число.")
            return redirect('materials_out', pk=fabric.pk)

        if amount <= 0:
            messages.error(request, "Количество должно быть больше нуля.")
            return redirect('materials_out', pk=fabric.pk)

        with transaction.atomic():
            fabric.refresh_from_db()
            current_qty = fabric.quantity or Decimal('0')

            if amount > current_qty:
                messages.error(
                    request,
                    f"Нельзя списать {amount} — доступно только {current_qty} {fabric.get_unit_display()}.",
                )
                return redirect('materials_out', pk=fabric.pk)

            fabric.quantity = current_qty - amount
            fabric.save()

            MaterialTransaction.objects.create(
                fabric=fabric,
                user=request.user,
                transaction_type=MaterialTransaction.OUT,
                amount=amount,
                note=note or "Списание вручную",
            )

        messages.success(
            request,
            f"Списано {amount} {fabric.get_unit_display()} материала «{fabric.name}».",
        )
        return redirect('materials_history', pk=fabric.pk)

    # GET
    return render(request, 'materials/materials_out.html', {'fabric': fabric})




@login_required
def materials_history(request, pk):
    fabric = get_object_or_404(Fabric, pk=pk)
    transactions = fabric.transactions.select_related('user').all()  # thanks related_name

    return render(request, 'materials/materials_history.html', {
        'fabric': fabric,
        'transactions': transactions,
    })





from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.db.models import Sum
from django.contrib import messages
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required

from .models import Product, WorkerProductLog, ProductTransaction
@login_required
def products_in(request, pk):
    product = get_object_or_404(Product, pk=pk)

    # Всего произведено работниками
    total_produced = (
        WorkerProductLog.objects
        .filter(product=product)
        .aggregate(total=Sum('quantity'))['total'] or 0
    )
    # Уже оприходовано (текущее наличие на складе)
    current_qty = product.quantity or Decimal('0')
    # Сколько ещё можно перенести на склад
    available_to_add = Decimal(total_produced) - current_qty
    if available_to_add < 0:
        available_to_add = Decimal('0')

    if request.method == 'POST':
        raw_value = (request.POST.get('value') or '').strip()
        note = (request.POST.get('note') or '').strip()

        if not raw_value:
            messages.error(request, "Введите количество.")
            return redirect('product_in', pk=product.pk)

        # (Если нужны дробные — поменяйте WorkerProductLog.quantity на DecimalField)
        if '.' in raw_value or ',' in raw_value:
            messages.error(request, "Сейчас допускаются только целые числа.")
            return redirect('product_in', pk=product.pk)

        try:
            amount_int = int(raw_value)
        except ValueError:
            messages.error(request, "Неверное число.")
            return redirect('product_in', pk=product.pk)

        if amount_int <= 0:
            messages.error(request, "Количество должно быть больше нуля.")
            return redirect('product_in', pk=product.pk)

        amount = Decimal(amount_int)

        with transaction.atomic():
            product_locked = Product.objects.select_for_update().get(pk=product.pk)

            # Повторный расчёт внутри транзакции — защита от гонок
            total_produced_locked = (
                WorkerProductLog.objects
                .filter(product=product_locked)
                .aggregate(total=Sum('quantity'))['total'] or 0
            )
            current_qty_locked = product_locked.quantity or Decimal('0')
            available_locked = Decimal(total_produced_locked) - current_qty_locked
            if amount > available_locked:
                messages.error(request, f"Нельзя оприходовать {amount}. Доступно только {available_locked}.")
                return redirect('product_in', pk=product_locked.pk)

            product_locked.quantity = current_qty_locked + amount
            product_locked.save(update_fields=['quantity'])

            ProductTransaction.objects.create(
                product=product_locked,
                user=request.user,
                transaction_type=ProductTransaction.IN,
                amount=amount,
                note=note or "Приход (из произведённого)"
            )

        messages.success(
            request,
            f"Оприходовано {amount} {product.get_unit_display()} «{product.name}». "
            f"На складе теперь: {product_locked.quantity}."
        )
        return redirect('product_history', pk=product.pk)

    return render(request, 'product/product_in.html', {
        'product': product,
        'total_produced': total_produced,
        'current_qty': current_qty,
        'available_to_add': available_to_add,
    })
    
    

@login_required
def products_out(request, pk):
    product = get_object_or_404(Product, pk=pk)
    current_qty = product.quantity or Decimal('0')

    # Для информативности показываем общее производство
    from django.db.models import Sum
    total_produced = (
        WorkerProductLog.objects
        .filter(product=product)
        .aggregate(total=Sum('quantity'))['total'] or 0
    )

    if request.method == 'POST':
        raw_value = (request.POST.get('value') or '').strip()
        note = (request.POST.get('note') or '').strip()

        if not raw_value:
            messages.error(request, "Введите количество.")
            return redirect('product_out', pk=product.pk)

        if '.' in raw_value or ',' in raw_value:
            messages.error(request, "Только целые значения (измените модель для дробей).")
            return redirect('product_out', pk=product.pk)

        try:
            amount_int = int(raw_value)
        except ValueError:
            messages.error(request, "Неверное число.")
            return redirect('product_out', pk=product.pk)

        if amount_int <= 0:
            messages.error(request, "Количество должно быть больше нуля.")
            return redirect('product_out', pk=product.pk)

        amount = Decimal(amount_int)

        if amount > current_qty:
            messages.error(request, f"Нельзя списать {amount}. Доступно {current_qty}.")
            return redirect('product_out', pk=product.pk)

        with transaction.atomic():
            product_locked = Product.objects.select_for_update().get(pk=product.pk)
            locked_qty = product_locked.quantity or Decimal('0')
            if amount > locked_qty:
                messages.error(request, f"Недостаточно на складе (доступно {locked_qty}).")
                return redirect('product_out', pk=product_locked.pk)

            product_locked.quantity = locked_qty - amount
            product_locked.save(update_fields=['quantity'])

            ProductTransaction.objects.create(
                product=product_locked,
                user=request.user,
                transaction_type=ProductTransaction.OUT,
                amount=amount,
                note=note or "Расход"
            )

        messages.success(
            request,
            f"Списано {amount} {product.get_unit_display()} «{product.name}». Остаток: {product_locked.quantity}."
        )
        return redirect('product_history', pk=product.pk)

    return render(request, 'product/product_out.html', {
        'product': product,
        'current_qty': current_qty,
        'total_produced': total_produced,
    })


  
@login_required
def products_history(request, pk):
    product = get_object_or_404(Product, pk=pk)
    transactions = (
        ProductTransaction.objects
        .filter(product=product)
        .select_related('user')
        .order_by('-created_at')
    )
    return render(request, 'product/product_history.html', {
        'product': product,
        'transactions': transactions
    })

    product = get_object_or_404(Product, pk=pk)
    transactions = ProductTransaction.objects.filter(product=product).select_related('user').order_by('-created_at')
    return render(request, 'product/product_history.html', {
        'product': product,
        'transactions': transactions
    })
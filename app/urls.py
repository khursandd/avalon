from django.urls import path
from django.conf.urls.i18n import set_language
from . import views

urlpatterns = [
    # --- Главная ---
    path('', views.role_based_home, name='home'),
    path('home/', views.role_based_home, name='home'),

    # --- Ткани ---
    path('fabric/<int:pk>/', views.view_fabric, name='view_fabric'),
    path('fabric/<int:pk>/edit/', views.edit_fabric, name='edit_fabric'),
    path('add-fabric/', views.add_fabric, name='add_fabric'),
    path('delete-fabric/<int:pk>/', views.delete_fabric, name='delete_fabric'),

    # --- Пользователи ---
    path('add_user/', views.add_user, name='add_user'),
    path('user/<int:pk>/', views.view_user, name='view_user'),
    path('user/<int:pk>/edit/', views.edit_user, name='edit_user'),
    path('all_admins/', views.all_admins, name='all_admins'),
    path('all_workers/', views.all_workers, name='all_workers'),
    path('all_no_rule_users/', views.all_no_rule_users, name='all_no_rule_users'),

    # --- Работники ---
    path('add_worker_product/', views.add_worker_product, name='add_worker_product'),

    # --- Продукты ---
    # path('products/', views.product_list, name='product_list'),
    path('products/add/', views.add_product, name='add_product'),
    path('products/<int:pk>/', views.view_product, name='view_product'),
    path('products/<int:pk>/edit/', views.edit_product, name='edit_product'),
    path('products/<int:pk>/delete/', views.delete_product, name='delete_product'),
    path('products/<int:pk>/in/', views.products_in, name='product_in'),
    path('products/<int:pk>/out/', views.products_out, name='product_out'),
    path('products/<int:pk>/history/', views.products_history, name='product_history'),

    # --- Материалы ---
    path('materials/in/<int:pk>/', views.materials_in, name='materials_in'),
    path('materials/out/<int:pk>/', views.materials_out, name='materials_out'),
    path('materials/history/<int:pk>/', views.materials_history, name='materials_history'),

    # --- Локализация ---
    path('i18n/setlang/', set_language, name='set_language'),
]

from django.contrib import admin
from .models import Fabric, FabricChangeLog, WorkerProductLog


@admin.register(Fabric)
class FabricAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'quantity', 'unit', 'price', 'image')
    list_filter = ('unit',)
    search_fields = ('name',)


@admin.register(FabricChangeLog)
class FabricChangeLogAdmin(admin.ModelAdmin):
    list_display = ('fabric', 'action', 'change_weight', 'change_length', 'user', 'timestamp')
    list_filter = ('action', 'timestamp', 'user')
    search_fields = ('fabric__name', 'user__username')


@admin.register(WorkerProductLog)
class WorkerProductLogAdmin(admin.ModelAdmin):
    list_display = ('worker', 'product_name', 'quantity', 'date')
    list_filter = ('date', 'worker')
    search_fields = ('product_name', 'worker__username')

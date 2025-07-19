from django.db import models
from django.contrib.auth.models import User


class Fabric(models.Model):
    UNIT_CHOICES = [
        ('kg', 'кг'),
        ('m', 'м'),
        ('pcs', 'шт'),
    ]
    name = models.CharField(max_length=255, unique=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='kg')
    image = models.ImageField(upload_to='fabrics/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)



class FabricChangeLog(models.Model):
    ACTION_CHOICES = [
        ('add', 'Добавление'),
        ('remove', 'Убавление'),
        ('delete', 'Полное удаление'),
    ]

    fabric = models.ForeignKey(Fabric, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    change_weight = models.FloatField(null=True, blank=True)
    change_length = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.fabric.name} - {self.get_action_display()} - {self.timestamp.strftime('%Y-%m-%d')}"



class Product(models.Model):
    UNIT_CHOICES = [
        ('pcs', 'шт.'),
        ('kg', 'кг'),
    ]

    name = models.CharField(max_length=255, unique=True)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='pcs')  # <-- добавлено
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class WorkerProductLog(models.Model):
    worker = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=255)  # запасной текст, если продукт удалён
    quantity = models.PositiveIntegerField()
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.worker} - {self.product or self.product_name} - {self.quantity}"



class ProductType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    
    
class MaterialForProduct(models.Model):
    product_type = models.ForeignKey(ProductType, on_delete=models.CASCADE)
    fabric = models.ForeignKey(Fabric, on_delete=models.CASCADE)
    quantity = models.FloatField()

    def __str__(self):
        return f"{self.product_type.name} - {self.fabric.name} - {self.quantity}"

class MaterialTransaction(models.Model):
    IN = 'IN'
    OUT = 'OUT'
    TYPES = [
        (IN, 'Приход'),
        (OUT, 'Расход'),
    ]

    fabric = models.ForeignKey(Fabric, on_delete=models.CASCADE, related_name='transactions')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    transaction_type = models.CharField(max_length=3, choices=TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)



class ProductTransaction(models.Model):
    IN = 'IN'
    OUT = 'OUT'
    TYPES = [
        (IN, 'Приход'),
        (OUT, 'Расход'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='transactions')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    transaction_type = models.CharField(max_length=3, choices=TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']




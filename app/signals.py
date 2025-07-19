from decimal import Decimal
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import WorkerProductLog, Product, ProductTransaction


# --- Если лог меняют (редактируют), нужно знать старое значение ---
@receiver(pre_save, sender=WorkerProductLog)
def worker_log_pre_save(sender, instance, **kwargs):
    if instance.pk:
        # Получаем старую версию из БД
        try:
            old = WorkerProductLog.objects.get(pk=instance.pk)
            instance._old_quantity = old.quantity
            instance._old_product_id = old.product_id
        except WorkerProductLog.DoesNotExist:
            instance._old_quantity = None
            instance._old_product_id = None
    else:
        instance._old_quantity = None
        instance._old_product_id = None


@receiver(post_save, sender=WorkerProductLog)
def worker_log_post_save(sender, instance, created, **kwargs):
    """
    created -> новое производство
    updated -> изменить остаток на разницу
    """
    if not instance.product:
        return

    product = Product.objects.select_for_update().get(pk=instance.product.pk)

    if created:
        product.quantity = (product.quantity or Decimal('0')) + Decimal(instance.quantity)
    else:
        # Изменили лог
        old_qty = getattr(instance, '_old_quantity', None)
        old_product_id = getattr(instance, '_old_product_id', None)

        if old_product_id and old_product_id != instance.product_id:
            # Перенесли лог с одного продукта на другой
            try:
                old_product = Product.objects.select_for_update().get(pk=old_product_id)
                old_product.quantity = (old_product.quantity or Decimal('0')) - Decimal(old_qty or 0)
                if old_product.quantity < 0:
                    old_product.quantity = 0
                old_product.save(update_fields=['quantity'])
            except Product.DoesNotExist:
                pass
            # Для нового продукта просто прибавляем полное количество
            product.quantity = (product.quantity or Decimal('0')) + Decimal(instance.quantity)
        else:
            if old_qty is not None and old_qty != instance.quantity:
                diff = Decimal(instance.quantity) - Decimal(old_qty)
                product.quantity = (product.quantity or Decimal('0')) + diff

    if product.quantity < 0:
        product.quantity = 0

    product.save(update_fields=['quantity'])


@receiver(post_delete, sender=WorkerProductLog)
def worker_log_post_delete(sender, instance, **kwargs):
    if not instance.product:
        return
    try:
        product = Product.objects.select_for_update().get(pk=instance.product.pk)
    except Product.DoesNotExist:
        return
    product.quantity = (product.quantity or Decimal('0')) - Decimal(instance.quantity)
    if product.quantity < 0:
        product.quantity = 0
    product.save(update_fields=['quantity'])

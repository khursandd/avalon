from django.apps import AppConfig
from django.db.models.signals import post_migrate

class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        from django.contrib.auth.models import Group  # импорт внутри метода
        from django.db.models.signals import post_migrate

        def create_default_groups(sender, **kwargs):
            groups = ['admin', 'worker']
            for group in groups:
                Group.objects.get_or_create(name=group)

        post_migrate.connect(create_default_groups, sender=self)



from django.contrib.auth.decorators import user_passes_test

def is_admin_or_superuser(user):
    return user.is_superuser or user.groups.filter(name='admin').exists()

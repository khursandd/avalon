from django import  forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Fabric, MaterialTransaction, Product

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]



class FabricForm(forms.ModelForm):
    class Meta:
        model = Fabric
        fields = ['name', 'quantity', 'price', 'unit', 'image']


class MaterialTransactionForm(forms.ModelForm):
    class Meta:
        model = MaterialTransaction
        fields = ['amount', 'transaction_type', 'note']  # ✅ используем реальные поля
        widgets = {
            'note': forms.TextInput(attrs={'placeholder': 'Комментарий (необязательно)'}),
        }


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'price_per_unit', 'image', 'is_active']
        
        


from django import forms
from .models import Transaction, Category

class TransactionForm(forms.ModelForm):
    class Meta:
        model  = Transaction
        fields = ['type', 'category', 'amount', 'description', 'date', 'reference']
        widgets = {
            'date':        forms.DateInput(attrs={'type': 'date'}),
            'description': forms.TextInput(attrs={'placeholder': 'Brief description'}),
            'reference':   forms.TextInput(attrs={'placeholder': 'Invoice # or ref (optional)'}),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset    = Category.objects.filter(created_by=user)
        self.fields['category'].required    = False
        self.fields['category'].empty_label = 'No category'

class CategoryForm(forms.ModelForm):
    class Meta:
        model   = Category
        fields  = ['name', 'type', 'color']
        widgets = {'color': forms.TextInput(attrs={'type': 'color'})}

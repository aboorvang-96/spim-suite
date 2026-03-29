from django import forms
from .models import ExpenseCategory, IncomeCategory


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'description', 'color', 'icon']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Category name'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Description (optional)'}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'form-input-color'}),
            'icon': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Icon name (e.g. shopping-cart)'}),
        }


class IncomeCategoryForm(forms.ModelForm):
    class Meta:
        model = IncomeCategory
        fields = ['name', 'description', 'color', 'icon']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Category name'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Description (optional)'}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'form-input-color'}),
            'icon': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Icon name (e.g. briefcase)'}),
        }

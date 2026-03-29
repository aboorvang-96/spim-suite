from django import forms
from .models import Income


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Income
        fields = ['title', 'amount', 'category', 'date', 'source', 'description', 'payment_mode']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Income title'}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '0.00', 'step': '0.01', 'min': '0'}),
            'category': forms.Select(attrs={'class': 'form-input'}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'source': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Salary, Freelance'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Description (optional)'}),
            'payment_mode': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            from categories.models import IncomeCategory
            self.fields['category'].queryset = IncomeCategory.objects.filter(created_by=user)
        self.fields['category'].empty_label = 'Select Category'

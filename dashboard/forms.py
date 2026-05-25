from django import forms
from .models import CompanySettings


class CompanySettingsForm(forms.ModelForm):
    class Meta:
        model = CompanySettings
        fields = ['name', 'address', 'contact_number', 'gst_number', 'managing_director']
        widgets = {
            'name':              forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Company Name'}),
            'address':           forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Company Address'}),
            'contact_number':    forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Contact Number'}),
            'gst_number':        forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'GST Number'}),
            'managing_director': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Managing Director Name'}),
        }

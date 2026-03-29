from django import forms
from .models import Client

class ClientForm(forms.ModelForm):
    class Meta:
        model   = Client
        fields  = ['name','email','phone','company','address','website','notes']
        widgets = {
            'address': forms.Textarea(attrs={'rows':2}),
            'notes':   forms.Textarea(attrs={'rows':2}),
        }

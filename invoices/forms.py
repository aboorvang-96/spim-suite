from django import forms
from django.forms import inlineformset_factory
from .models import Invoice, InvoiceItem
import datetime, random

class InvoiceForm(forms.ModelForm):
    class Meta:
        model   = Invoice
        fields  = ['invoice_number','client','project','status','issue_date','due_date','tax_rate','notes']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type':'date'}),
            'due_date':   forms.DateInput(attrs={'type':'date'}),
            'notes':      forms.Textarea(attrs={'rows':2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            yr  = datetime.date.today().strftime('%Y%m')
            rnd = random.randint(100, 999)
            self.fields['invoice_number'].initial = 'INV-' + yr + '-' + str(rnd)
        self.fields['project'].required = False

ItemFormSet = inlineformset_factory(
    Invoice, InvoiceItem,
    fields=['description','quantity','rate'],
    extra=2, can_delete=True,
    widgets={
        'description': forms.TextInput(attrs={'placeholder':'Service or item description'}),
        'quantity':    forms.NumberInput(attrs={'placeholder':'1','step':'0.01'}),
        'rate':        forms.NumberInput(attrs={'placeholder':'0.00','step':'0.01'}),
    }
)

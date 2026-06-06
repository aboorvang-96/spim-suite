from django import forms
from .models import Income


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Income
        fields = [
            'amount', 'date', 'description',
            'payment_mode', 'income_type', 'location_site', 'payment_by',
            # New site-detail fields (Income/Expense restructure).
            'from_account', 'to_account', 'remarks',
        ]
        widgets = {
            'amount':      forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '0.00', 'step': '0.01', 'min': '0'}),
            'date':        forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Description'}),
            'remarks':     forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Remarks (optional)'}),
            'from_account': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'From Account'}),
            'to_account':   forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'To Account'}),
        }
        labels = {
            'payment_mode':  'Account',
            'income_type':   'Income Type',
            'location_site': 'Location / Site',
            'payment_by':    'Income Source',
            'description':   'Description',
            'from_account':  'From Account',
            'to_account':    'To Account',
            'remarks':       'Remarks',
        }

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # payment_mode comes from modal as free text (e.g. "Bank Account 1");
        # bypass the model's PAYMENT_MODE_CHOICES validation entirely.
        self.fields['payment_mode'] = forms.CharField(
            required=False,
            max_length=20,
            widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Account'}),
            label='Account',
        )

    def _post_clean(self):
        # Run normal model validation, then drop any payment_mode error caused
        # by the model's PAYMENT_MODE_CHOICES list — modal sends free-text values.
        super()._post_clean()
        if 'payment_mode' in self._errors:
            self._errors.pop('payment_mode', None)
            value = self.cleaned_data.get('payment_mode')
            if not value:
                value = (self.data.get('payment_mode') or '').strip()
            value = value[:20]
            self.cleaned_data['payment_mode'] = value
            self.instance.payment_mode = value

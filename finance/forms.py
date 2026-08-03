from django import forms
from .models import Transaction, Category


class FlexibleModelChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that silently coerces invalid/non-numeric values to None
    so the modal's free-text custom selections never trigger a 400."""
    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            return super().to_python(value)
        except (forms.ValidationError, ValueError, TypeError):
            return None


class TransactionForm(forms.ModelForm):
    class Meta:
        model  = Transaction
        fields = ['date', 'type', 'category', 'expense_category', 'amount', 'location_site', 'payment_by', 'vendor', 'purpose', 'payment_mode', 'income_source', 'description']
        widgets = {
            'date':        forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'placeholder': 'Remarks', 'rows': 3}),
            'location_site': forms.TextInput(attrs={'placeholder': 'Location / Site'}),
            'vendor':      forms.TextInput(attrs={'placeholder': 'To'}),
            'payment_by':  forms.TextInput(attrs={'placeholder': 'From'}),
            'purpose':     forms.TextInput(attrs={'placeholder': 'Expense Type'}),
        }
        labels = {
            'type': 'Type',
            'location_site': 'Location / Site',
            'payment_by': 'From',
            'vendor': 'To',
            'purpose': 'Expense Type',
            'payment_mode': 'Account',
            'description': 'Remarks',
            'expense_category': 'Category',
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Replace category with a flexible variant that doesn't 400 on free text
        self.fields['category'] = FlexibleModelChoiceField(
            queryset=Category.objects.filter(created_by=user),
            required=False,
            empty_label='No category',
        )
        # payment_mode comes from the modal as free text (e.g. "Bank Account 1");
        # bypass the model's TYPE_CHOICES validation by replacing the field entirely.
        self.fields['payment_mode'] = forms.CharField(
            required=False,
            max_length=20,
            widget=forms.TextInput(attrs={'placeholder': 'Account'}),
            label='Account',
        )
        # Fixed-choice expense category (Income/Expense restructure) — blank is
        # a valid value (admin may leave it unset). Replace with a free CharField
        # so the site-detail inline table can post extended category codes (e.g.
        # 'room', 'diesel') without a model-level choices migration.
        if 'expense_category' in self.fields:
            self.fields['expense_category'] = forms.CharField(
                required=False,
                max_length=20,
                widget=forms.Select(choices=[('', '— Select —')] + list(Transaction.EXPENSE_CATEGORY_CHOICES)),
            )

    def _post_clean(self):
        # Run normal model validation, then drop any payment_mode error caused
        # by the model's TYPE_CHOICES list — the modal lets users pick free-text
        # account names (e.g. "Bank Account 1") that aren't in the choices.
        # Also drop any expense_category error so the site-detail inline table
        # can post extended category codes (e.g. 'room', 'diesel') that aren't
        # in the model's EXPENSE_CATEGORY_CHOICES list.
        super()._post_clean()
        if 'payment_mode' in self._errors:
            self._errors.pop('payment_mode', None)
            value = self.cleaned_data.get('payment_mode')
            if not value:
                value = (self.data.get('payment_mode') or '').strip()
            value = value[:20]  # respect model max_length
            self.cleaned_data['payment_mode'] = value
            self.instance.payment_mode = value
        if 'expense_category' in self._errors:
            self._errors.pop('expense_category', None)
            value = (self.data.get('expense_category') or '').strip().lower()[:20]
            self.cleaned_data['expense_category'] = value
            self.instance.expense_category = value

class CategoryForm(forms.ModelForm):
    class Meta:
        model   = Category
        fields  = ['name', 'type', 'color']
        widgets = {'color': forms.TextInput(attrs={'type': 'color'})}

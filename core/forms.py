from django import forms
from .models import VoucherType, Merchant, POSTerminal


class OTPStartForm(forms.Form):
    email = forms.EmailField(required=True)
    next = forms.CharField(required=False)

    def clean_next(self):
        target = (self.cleaned_data.get("next") or "").strip()
        if len(target) > 200:
            raise forms.ValidationError("Tham số chuyển hướng không hợp lệ.")
        return target or None


class ClaimProfileForm(forms.Form):
    full_name = forms.CharField(max_length=120, required=True)
    phone = forms.CharField(max_length=32, required=True)

    def clean_full_name(self):
        value = (self.cleaned_data.get("full_name") or "").strip()
        if len(value) < 3:
            raise forms.ValidationError("Name is too short.")
        return value


class VoucherTypeForm(forms.ModelForm):
    class Meta:
        model = VoucherType
        fields = [
            'name', 'description', 'max_supply', 'per_user_limit', 'active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'block w-full rounded-xl border-0 bg-slate-50 px-4 py-3 text-sm text-slate-900 placeholder-slate-500 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-500 focus:ring-inset transition-all',
                'placeholder': 'e.g., Spa 30% Off 2025'
            }),
            'description': forms.Textarea(attrs={
                'class': 'block w-full rounded-xl border-0 bg-slate-50 px-4 py-3 text-sm text-slate-900 placeholder-slate-500 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-500 focus:ring-inset transition-all resize-none',
                'rows': 4,
                'placeholder': 'Describe the voucher campaign...'
            }),
            'max_supply': forms.NumberInput(attrs={
                'class': 'block w-full rounded-xl border-0 bg-slate-50 px-4 py-3 text-sm text-slate-900 placeholder-slate-500 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-500 focus:ring-inset transition-all',
                'placeholder': '1000'
            }),
            'per_user_limit': forms.NumberInput(attrs={
                'class': 'block w-full rounded-xl border-0 bg-slate-50 px-4 py-3 text-sm text-slate-900 placeholder-slate-500 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-500 focus:ring-inset transition-all',
                'placeholder': '1'
            }),
            'active': forms.CheckboxInput(attrs={
                'class': 'h-6 w-6 rounded-lg border-slate-300 text-emerald-600 focus:ring-emerald-500 shadow-sm'
            }),
        }

    def clean_slug(self):
        value = (self.cleaned_data.get('slug') or '').strip()
        return value.lower()

    def clean_token_id(self):
        # Accept numeric strings and ints; store as decimal-compatible integer string
        value = self.cleaned_data.get('token_id')
        if value is None or str(value).strip() == '':
            raise forms.ValidationError('Token ID is required.')
        try:
            iv = int(str(value))
        except Exception:
            raise forms.ValidationError('Token ID must be an integer.')
        if iv < 0:
            raise forms.ValidationError('Token ID must be non-negative.')
        return iv

    def clean_phone(self):
        raw = (self.cleaned_data.get("phone") or "").strip()
        # Normalize: keep digits, allow one leading '+'
        normalized = raw
        if raw.startswith('+'):
            normalized = '+' + ''.join(ch for ch in raw[1:] if ch.isdigit())
        else:
            normalized = ''.join(ch for ch in raw if ch.isdigit())
        if len(normalized.replace('+','')) < 8 or len(normalized.replace('+','')) > 15:
            raise forms.ValidationError("Phone number looks invalid.")
        return normalized


class MerchantForm(forms.ModelForm):
    class Meta:
        model = Merchant
        fields = ['name', 'category', 'active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'block w-full rounded-xl border-0 bg-slate-50 px-4 py-3 text-sm text-slate-900 placeholder-slate-500 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-500 focus:ring-inset transition-all',
                'placeholder': 'e.g., Furama Spa & Wellness'
            }),
            'category': forms.Select(attrs={
                'class': 'block w-full rounded-xl border-0 bg-slate-50 px-4 py-3 text-sm text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-500 focus:ring-inset transition-all'
            }, choices=[
                ('', 'Select category...'),
                ('spa', 'Spa & Wellness'),
                ('restaurant', 'Restaurant'),
                ('bar', 'Bar & Lounge'),
                ('gym', 'Fitness Center'),
                ('shop', 'Retail Shop'),
                ('service', 'Service Center'),
                ('other', 'Other')
            ]),
            'active': forms.CheckboxInput(attrs={
                'class': 'h-6 w-6 rounded-lg border-slate-300 text-emerald-600 focus:ring-emerald-500 shadow-sm'
            }),
        }

    def clean_name(self):
        value = (self.cleaned_data.get('name') or '').strip()
        if len(value) < 2:
            raise forms.ValidationError('Merchant name is too short.')
        return value


class POSTerminalForm(forms.ModelForm):
    class Meta:
        model = POSTerminal
        fields = ['merchant', 'code', 'active']
        widgets = {
            'merchant': forms.Select(attrs={
                'class': 'block w-full rounded-xl border-0 bg-slate-50 px-4 py-3 text-sm text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-500 focus:ring-inset transition-all'
            }),
            'code': forms.TextInput(attrs={
                'class': 'block w-full rounded-xl border-0 bg-slate-50 px-4 py-3 text-sm text-slate-900 placeholder-slate-500 shadow-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-500 focus:ring-inset transition-all font-mono',
                'placeholder': 'e.g., SPA01, REST01'
            }),
            'active': forms.CheckboxInput(attrs={
                'class': 'h-6 w-6 rounded-lg border-slate-300 text-emerald-600 focus:ring-emerald-500 shadow-sm'
            }),
        }

    def clean_code(self):
        value = (self.cleaned_data.get('code') or '').strip().upper()
        if len(value) < 2:
            raise forms.ValidationError('Terminal code is too short.')
        if not value.replace('_', '').replace('-', '').isalnum():
            raise forms.ValidationError('Terminal code can only contain letters, numbers, hyphens, and underscores.')
        return value

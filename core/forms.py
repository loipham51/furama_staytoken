from django import forms


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

    def clean_phone(self):
        value = (self.cleaned_data.get("phone") or "").strip()
        if len(value) < 8:
            raise forms.ValidationError("Phone number looks invalid.")
        return value

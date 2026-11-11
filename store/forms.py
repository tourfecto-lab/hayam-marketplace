import re

from django import forms


class CheckoutForm(forms.Form):
    name = forms.CharField(label="الاسم", max_length=150)
    phone = forms.CharField(label="رقم الموبايل", max_length=14)
    email = forms.EmailField(label="الإيميل (اختياري)", required=False)
    address = forms.CharField(
        label="العنوان بالتفصيل والمحافظة", max_length=1000, widget=forms.Textarea
    )
    key = forms.UUIDField(widget=forms.HiddenInput)

    def clean_phone(self) -> str:
        phone = self.cleaned_data["phone"].translate(
            str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
        )
        phone = re.sub(r"[\s()-]", "", phone)
        if phone.startswith("+20"):
            phone = "0" + phone[3:]
        if not re.fullmatch(r"01[0125][0-9]{8}", phone):
            raise forms.ValidationError("اكتب رقم موبايل مصري صحيح.")
        return "+20" + phone[1:]


class CartForm(forms.Form):
    variant = forms.IntegerField(min_value=1)
    quantity = forms.IntegerField(min_value=0, max_value=10)

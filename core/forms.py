from django import forms
from django.core.validators import MinLengthValidator, MaxLengthValidator


class ChannelHandleForm(forms.Form):
    handle = forms.CharField(
        max_length=30,
        min_length=3,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите псевдоним YT-канала без @',
            'style': 'width: 300px;'
        }),
        validators=[
            MinLengthValidator(3),
            MaxLengthValidator(30)
        ]
    )

    def clean_handle(self):
        handle = self.cleaned_data['handle'].strip()
        if handle.startswith('@'):
            handle = handle[1:]
        return handle
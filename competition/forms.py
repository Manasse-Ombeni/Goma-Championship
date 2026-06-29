import re
from django import forms
from django.contrib.auth.models import User
from .models import Team, Match  # ← AJOUTER Match ici

class TeamForm(forms.ModelForm):
    owner_username = forms.CharField(
        label="Nom d'utilisateur",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full p-3 bg-black/30 rounded-xl border border-white/10',
            'placeholder': 'ex: ombeni10'
        })
    )
    owner_password = forms.CharField(
        label="Mot de passe",
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'w-full p-3 bg-black/30 rounded-xl border border-white/10',
            'placeholder': '••••••••'
        })
    )

    class Meta:
        model = Team
        # ← J'AI ENLEVÉ 'pseudo' qui n'existe pas dans ton modèle
        fields = ['name', 'abbreviation', 'whatsapp']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full p-3 bg-black/30 rounded-xl border border-white/10',
                'placeholder': 'N\'importe quel pays : France, Brésil...'
            }),
            'abbreviation': forms.TextInput(attrs={
                'class': 'w-full p-3 bg-black/30 rounded-xl border border-white/10',
                'placeholder': 'FRA'
            }),
            'whatsapp': forms.TextInput(attrs={
                'class': 'w-full p-3 bg-black/30 rounded-xl border border-white/10',
                'placeholder': '+243992848365 ou +33...'
            }),
        }
        labels = {
            'name': 'Nom de l’équipe',
            'abbreviation': 'Abréviation',
            'whatsapp': 'WhatsApp (avec indicatif)',
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Donne un nom à ton équipe")
        return name

    def clean_whatsapp(self):
        whatsapp = self.cleaned_data.get('whatsapp', '').strip().replace(' ', '')
        if not whatsapp:
            raise forms.ValidationError("Numéro requis")
        if not whatsapp.startswith('+'):
            raise forms.ValidationError("Mets l'indicatif : +243, +33, +1, +44...")
        if not re.match(r'^\+\d{8,15}$', whatsapp):
            raise forms.ValidationError("Format : +[indicatif][numéro]. Ex: +243992848365")
        return whatsapp

    def clean_owner_username(self):
        username = self.cleaned_data.get('owner_username', '').strip()
        if not username:
            return username
        if not self.instance.pk and User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Ce nom d'utilisateur est déjà pris")
        return username

    def clean_owner_password(self):
        password = self.cleaned_data.get('owner_password', '')
        if not self.instance.pk and not password:
            raise forms.ValidationError("Mot de passe requis")
        if password and len(password) < 6:
            raise forms.ValidationError("Minimum 6 caractères")
        return password




class KnockoutResultForm(forms.ModelForm):
    """Formulaire pour encoder un match éliminatoire avec prolongations/TAB"""

    class Meta:
        model = Match
        fields = [
            'home_goals', 'away_goals',
            'extra_time', 'home_goals_et', 'away_goals_et',
            'penalty_shootout', 'home_penalties', 'away_penalties',
        ]
        widgets = {
            'home_goals': forms.NumberInput(attrs={
                'class': 'w-full p-3 bg-black/30 rounded-xl border border-white/10 text-center text-2xl font-black',
                'min': '0', 'placeholder': '0'
            }),
            'away_goals': forms.NumberInput(attrs={
                'class': 'w-full p-3 bg-black/30 rounded-xl border border-white/10 text-center text-2xl font-black',
                'min': '0', 'placeholder': '0'
            }),
            'home_goals_et': forms.NumberInput(attrs={
                'class': 'w-full p-3 bg-black/30 rounded-xl border border-white/10 text-center',
                'min': '0', 'placeholder': '0'
            }),
            'away_goals_et': forms.NumberInput(attrs={
                'class': 'w-full p-3 bg-black/30 rounded-xl border border-white/10 text-center',
                'min': '0', 'placeholder': '0'
            }),
            'home_penalties': forms.NumberInput(attrs={
                'class': 'w-full p-3 bg-black/30 rounded-xl border border-white/10 text-center',
                'min': '0', 'placeholder': '0'
            }),
            'away_penalties': forms.NumberInput(attrs={
                'class': 'w-full p-3 bg-black/30 rounded-xl border border-white/10 text-center',
                'min': '0', 'placeholder': '0'
            }),
            'extra_time': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 rounded',
                'id': 'id_extra_time'
            }),
            'penalty_shootout': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 rounded',
                'id': 'id_penalty_shootout'
            }),
        }
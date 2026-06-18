from django import forms
from .models import Team, Match

PAYS_AUTORISES = [
    'RDC','Congo','France','Argentine','Brésil','Allemagne','Espagne','Portugal',
    'Angleterre','Belgique','Maroc','Sénégal','Cameroun','Côte d’Ivoire','Nigeria',
    'Ghana','Egypte','Tunisie','Algérie','USA','Mexique','Canada','Japon',
    'Corée du Sud','Australie','Italie','Pays-Bas','Suisse','Croatie','Uruguay',
    'Colombie','Chili','Pérou','Équateur','Paraguay','Danemark','Norvège','Suède'
]

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name','abbreviation','owner_username','owner_password','whatsapp']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder':'Ex: France','class':'w-full p-3 bg-black/60 border border-white/20 rounded-xl'}),
            'abbreviation': forms.TextInput(attrs={'placeholder':'Ex: FRA','maxlength':'3','class':'w-full p-3 bg-black/60 border border-white/20 rounded-xl uppercase'}),
            'owner_username': forms.TextInput(attrs={'placeholder':'Ex: halsey_10','class':'w-full p-3 bg-black/60 border border-white/20 rounded-xl'}),
            'owner_password': forms.PasswordInput(attrs={'placeholder':'Choisis un mot de passe','class':'w-full p-3 bg-black/60 border border-white/20 rounded-xl'}),
            'whatsapp': forms.TextInput(attrs={'placeholder':'Ex: +243970000000','class':'w-full p-3 bg-black/60 border border-white/20 rounded-xl'}),
        }
        labels = {
            'name': "Nom de l'équipe (pays)",
            'abbreviation': 'Abréviation équipe',
            'owner_username': "Nom d'utilisateur",
            'owner_password': 'Mot de passe',
            'whatsapp': 'Numéro WhatsApp',
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if name not in PAYS_AUTORISES:
            raise forms.ValidationError(f"Choisis un pays valide. Exemples : RDC, France, Argentine...")
        if Team.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("Ce pays est déjà pris par une autre équipe.")
        return name

    def clean_abbreviation(self):
        return self.cleaned_data['abbreviation'].upper()[:3]

class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['home_goals','away_goals']
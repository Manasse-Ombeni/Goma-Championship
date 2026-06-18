from django.db import models
from django.contrib.auth.models import User

class Tournament(models.Model):
    name = models.CharField(max_length=100, default="Goma Efootball Championship")
    def __str__(self): return self.name

class Group(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    name = models.CharField(max_length=1)  # A,B,C...
    def __str__(self): return f"Groupe {self.name}"

class Team(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=50, unique=True)  # Pays
    abbreviation = models.CharField(max_length=3)
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    owner_username = models.CharField(max_length=150, default='')
    owner_password = models.CharField(max_length=128, default='')
    whatsapp = models.CharField(max_length=20, blank=True)
    is_validated = models.BooleanField(default=False)
    points = models.IntegerField(default=0)
    goals_for = models.IntegerField(default=0)
    goals_against = models.IntegerField(default=0)
    def __str__(self): return self.name

class Match(models.Model):
    PHASES = [
    ('group','Poules'),
    ('R16','Huitièmes de finale'),
    ('QF','Quarts de finale'),
    ('SF','Demi-finales'),
    ('3P','Match 3ème place'),
    ('F','Finale'),
]
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    phase = models.CharField(max_length=10, choices=PHASES, default='group')
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.SET_NULL)
    home = models.ForeignKey(Team, related_name='home_matches', on_delete=models.CASCADE)
    away = models.ForeignKey(Team, related_name='away_matches', on_delete=models.CASCADE)
    home_goals = models.IntegerField(null=True, blank=True)
    away_goals = models.IntegerField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    played = models.BooleanField(default=False)
    def __str__(self): return f"{self.home} vs {self.away}"
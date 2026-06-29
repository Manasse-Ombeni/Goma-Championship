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
    collective_strength = models.IntegerField(default=0, blank=True, help_text="Force collective eFootball (ex: 3209)")
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


# models.py
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
    home = models.ForeignKey(
        Team, related_name='home_matches',
        null=True, blank=True, on_delete=models.SET_NULL
    )
    away = models.ForeignKey(
        Team, related_name='away_matches',
        null=True, blank=True, on_delete=models.SET_NULL
    )
    home_goals = models.IntegerField(null=True, blank=True)
    away_goals = models.IntegerField(null=True, blank=True)

    # ── Prolongations ──────────────────────────────────────────
    extra_time = models.BooleanField(default=False)
    home_goals_et = models.IntegerField(null=True, blank=True,
                                        help_text="Buts domicile en prolongation")
    away_goals_et = models.IntegerField(null=True, blank=True,
                                        help_text="Buts extérieur en prolongation")

    # ── Tirs au but ────────────────────────────────────────────
    penalty_shootout = models.BooleanField(default=False)
    home_penalties = models.IntegerField(null=True, blank=True,
                                         help_text="Tirs au but domicile")
    away_penalties = models.IntegerField(null=True, blank=True,
                                         help_text="Tirs au but extérieur")

    scheduled_at = models.DateTimeField(null=True, blank=True)
    played = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.home} vs {self.away}"

    @property
    def winner(self):
        """Retourne l'équipe gagnante ou None si pas joué / nul en poule"""
        if not self.played:
            return None
        if self.penalty_shootout:
            if self.home_penalties > self.away_penalties:
                return self.home
            return self.away
        if self.extra_time:
            total_home = (self.home_goals or 0) + (self.home_goals_et or 0)
            total_away = (self.away_goals or 0) + (self.away_goals_et or 0)
            if total_home > total_away:
                return self.home
            return self.away
        if (self.home_goals or 0) > (self.away_goals or 0):
            return self.home
        if (self.away_goals or 0) > (self.home_goals or 0):
            return self.away
        return None

    @property
    def loser(self):
        w = self.winner
        if not w:
            return None
        return self.away if w == self.home else self.home

    @property
    def score_display(self):
        """Affiche le score complet avec prolongations/TAB"""
        if not self.played:
            return "VS"
        h = self.home_goals or 0
        a = self.away_goals or 0
        s = f"{h} - {a}"
        if self.extra_time:
            he = self.home_goals_et or 0
            ae = self.away_goals_et or 0
            s += f" ({h+he}-{a+ae} ap)"
        if self.penalty_shootout:
            s += f" ({self.home_penalties}-{self.away_penalties} tab)"
        return s
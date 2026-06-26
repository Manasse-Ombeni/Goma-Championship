from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.db.models import Q 
import random
from django.contrib.auth.models import User
from django.contrib import messages

from.models import Tournament, Team, Match, Group
from .forms import TeamForm
from django import forms

def get_tournament():
    t, _ = Tournament.objects.get_or_create(pk=1, defaults={'name': 'Goma Efootball Championship'})
    return t

def is_manager(user):
    return user.is_staff

# PUBLIC
def home(request):
    t = get_tournament()
    teams = Team.objects.filter(tournament=t, is_validated=True).count()
    next_matches = Match.objects.filter(tournament=t, played=False)[:5]
    results = Match.objects.filter(tournament=t, played=True).order_by('-id')[:5]
    return render(request, 'competition/home.html', {'teams':teams,'next':next_matches,'results':results,'t':t})

def teams(request):
    t = get_tournament()
    qs = Team.objects.filter(tournament=t, is_validated=True).order_by('-points','-goals_for')
    return render(request, 'competition/teams.html', {'teams':qs})

def team_register(request):
    t = get_tournament()
    if request.method == 'POST':
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save(commit=False)
            team.tournament = t
            
            username = form.cleaned_data['owner_username']
            password = form.cleaned_data['owner_password']
            
            # — ANTI-DOUBLON —
            if Team.objects.filter(tournament=t, name__iexact=team.name).exists():
                form.add_error('name', "Ce nom d'équipe est déjà pris")
                return render(request, 'competition/register.html', {'form':form})
            
            if User.objects.filter(username=username).exists():
                # si l'user existe déjà, on vérifie s'il a déjà une équipe
                existing_user = User.objects.get(username=username)
                if Team.objects.filter(tournament=t, owner=existing_user).exists():
                    form.add_error('owner_username', "Tu es déjà inscrit")
                    return render(request, 'competition/register.html', {'form':form})
                user = existing_user
            else:
                user = User.objects.create_user(username=username, password=password)
            
            if not user.has_usable_password():
                user.set_password(password); user.save()
            
            team.owner = user
            team.is_validated = False
            team.save()
            
            # → redirige vers la page "paye maintenant"
            return redirect('registration_success', pk=team.pk)
    else:
        form = TeamForm()
    return render(request, 'competition/register.html', {'form':form})

from django.utils import timezone
from datetime import timedelta

def schedule(request):  # <-- renomme ici
    t = Tournament.objects.first()
    now = timezone.now()
    matches = Match.objects.filter(tournament=t).select_related('home','away').order_by('scheduled_at')

    user_team = None
    if request.user.is_authenticated:
        user_team = Team.objects.filter(tournament=t, owner=request.user).first()

    for m in matches:
        m.deadline = (m.scheduled_at or now) + timedelta(hours=24)
        m.hours_left = max(0, int((m.deadline - now).total_seconds() / 3600))
        m.is_late = now > m.deadline and not m.played
        m.is_mine = user_team and (m.home == user_team or m.away == user_team)

    return render(request, 'competition/matches.html', {'matches': matches, 'user_team': user_team})  # <-- matches.html

def standings(request):
    t = get_tournament()
    groups = Group.objects.filter(tournament=t).order_by('name')
    data = {g.name: Team.objects.filter(group=g, is_validated=True).order_by('-points','-goals_for','goals_against') for g in groups}
    return render(request, 'competition/standings.html', {'data':data})

def bracket(request):
    t = get_tournament()
    return render(request, 'competition/bracket.html', {
        'r16': Match.objects.filter(tournament=t, phase='R16').order_by('id'),
        'qf': Match.objects.filter(tournament=t, phase='QF').order_by('id'),
        'sf': Match.objects.filter(tournament=t, phase='SF').order_by('id'),
        'third': Match.objects.filter(tournament=t, phase='3P').first(),
        'final': Match.objects.filter(tournament=t, phase='F').first(),
    })

def logout_view(request):
    logout(request); return redirect('home')

# MANAGER
@login_required
@user_passes_test(is_manager)
def manager_dashboard(request):
    t = get_tournament()
    
    # Querysets
    all_teams = Team.objects.filter(tournament=t)
    pending_teams = all_teams.filter(is_validated=False).order_by('id')
    validated_teams = all_teams.filter(is_validated=True).order_by('-collective_strength', 'name')
    
    # Compteurs (entiers, pas QuerySet)
    total_teams = all_teams.count()
    pending = pending_teams.count()
    validated = validated_teams.count()
    
    # Groupes remplis
    groups_filled = f"{Team.objects.filter(tournament=t, group__isnull=False).values('group').distinct().count()}/8"
    
    context = {
        'total_teams': total_teams,
        'pending': pending,
        'validated': validated,
        'pending_teams': pending_teams,
        'validated_teams': validated_teams,
        'groups_filled': groups_filled,
    }
    return render(request, 'competition/manager/dashboard.html', context)

@login_required
@user_passes_test(is_manager)
def validate_team(request, pk):
    team = get_object_or_404(Team, pk=pk); team.is_validated = True; team.save()
    return redirect('manager')

@login_required
@user_passes_test(is_manager)
def reject_team(request, pk):
    team = get_object_or_404(Team, pk=pk)
    team.delete()
    return redirect('manager')

@login_required
@user_passes_test(is_manager)
def match_update(request, pk):
    match = get_object_or_404(Match, pk=pk)
    if request.method == 'POST':
        form = MatchForm(request.POST, instance=match)
        if form.is_valid():
            m = form.save(commit=False)
            m.played = True
            m.save()

            # 1. Stats poules
            if m.phase == 'group' and m.home and m.away and m.home_goals is not None:
                m.home.goals_for += m.home_goals
                m.home.goals_against += m.away_goals
                m.away.goals_for += m.away_goals
                m.away.goals_against += m.home_goals
                if m.home_goals > m.away_goals: m.home.points += 3
                elif m.home_goals < m.away_goals: m.away.points += 3
                else: m.home.points += 1; m.away.points += 1
                m.home.save(); m.away.save()

            # 2. Avancement automatique phases finales
            if m.phase in ['R16','QF','SF'] and m.home_goals != m.away_goals:
                winner = m.home if m.home_goals > m.away_goals else m.away
                loser = m.away if winner == m.home else m.home
                t = m.tournament

                # Récupère les matchs dans l'ordre
                r16 = list(Match.objects.filter(tournament=t, phase='R16').order_by('id'))
                qf = list(Match.objects.filter(tournament=t, phase='QF').order_by('id'))
                sf = list(Match.objects.filter(tournament=t, phase='SF').order_by('id'))
                final = Match.objects.filter(tournament=t, phase='F').first()
                third = Match.objects.filter(tournament=t, phase='3P').first()

                if m.phase == 'R16':
                    idx = r16.index(m)
                    target_qf = qf[idx // 2]  # 0-1 -> QF1, 2-3 -> QF2, etc.
                    if idx % 2 == 0: target_qf.home = winner
                    else: target_qf.away = winner
                    target_qf.save()

                elif m.phase == 'QF':
                    idx = qf.index(m)
                    target_sf = sf[idx // 2]
                    if idx % 2 == 0: target_sf.home = winner
                    else: target_sf.away = winner
                    target_sf.save()

                elif m.phase == 'SF':
                    idx = sf.index(m)
                    # Vainqueur en finale
                    if idx == 0: final.home = winner; third.home = loser
                    else: final.away = winner; third.away = loser
                    final.save(); third.save()

            return redirect('manager')
    else:
        form = MatchForm(instance=match)
    return render(request, 'competition/match_form.html', {'form':form,'match':match})

import random
from django.contrib import messages

@login_required
@user_passes_test(is_manager)
def generate_draw(request):
    t = get_tournament()
    teams = list(Team.objects.filter(tournament=t, is_validated=True))

    if len(teams)!= 32:
        messages.error(request, "Il faut 32 équipes validées")
        return redirect('manager')

    # Récupère ou crée les groupes A-H
    groups = {}
    for letter in ['A','B','C','D','E','F','G','H']:
        grp, _ = Group.objects.get_or_create(tournament=t, name=letter)
        groups[letter] = grp

    with_strength = [tm for tm in teams if tm.collective_strength > 0]
    without_strength = [tm for tm in teams if tm.collective_strength == 0]

    with_strength.sort(key=lambda x: x.collective_strength, reverse=True)

    # 4 pots
    pots = [with_strength[i::4] for i in range(4)]
    for pot in pots:
        random.shuffle(pot)

    pots[3].extend(without_strength)
    random.shuffle(pots[3])

    # Distribution
    letters = ['A','B','C','D','E','F','G','H']
    for group_idx in range(8):
        for pot_idx in range(4):
            if pots[pot_idx]:
                team = pots[pot_idx].pop(0)
                team.group = groups[letters[group_idx]] # ← objet Group, pas string
                team.save()

    messages.success(request, "Tirage équilibré effectué!")
    return redirect('manager')

@login_required
@user_passes_test(is_manager)
def generate_schedule(request):
    t = get_tournament()
    Match.objects.filter(tournament=t, stage='group').delete()

    for group in Group.objects.filter(tournament=t):
        teams = list(group.team_set.all())
        if len(teams)!= 4:
            continue

        # Round-robin 3 journées
        fixtures = [
            (0,1, 2,3), # J1
            (0,2, 1,3), # J2
            (0,3, 1,2), # J3
        ]
        for day, (a,b,c,d) in enumerate(fixtures, 1):
            Match.objects.create(tournament=t, group=group, home=teams[a], away=teams[b], matchday=day, stage='group')
            Match.objects.create(tournament=t, group=group, home=teams[c], away=teams[d], matchday=day, stage='group')

    messages.success(request, "Calendrier généré : 3 journées, 48 matchs")
    return redirect('manager')

@login_required
@user_passes_test(is_manager)
def generate_knockout(request):
    t = get_tournament()
    Match.objects.filter(tournament=t, phase__in=['R16','QF','SF','3P','F']).delete()

    groups = {}
    for g in Group.objects.filter(tournament=t).order_by('name'):
        top2 = list(Team.objects.filter(group=g, is_validated=True).order_by('-points','-goals_for')[:2])
        if len(top2) == 2: groups[g.name] = top2

    if len(groups)!= 8: return redirect('manager')

    # Huitièmes officiels
    r16 = [
        (groups['A'][0], groups['B'][1]), (groups['C'][0], groups['D'][1]),
        (groups['E'][0], groups['F'][1]), (groups['G'][0], groups['H'][1]),
        (groups['B'][0], groups['A'][1]), (groups['D'][0], groups['C'][1]),
        (groups['F'][0], groups['E'][1]), (groups['H'][0], groups['G'][1]),
    ]
    for h,a in r16: Match.objects.create(tournament=t, phase='R16', home=h, away=a)

    # Placeholders
    for _ in range(4): Match.objects.create(tournament=t, phase='QF', home=None, away=None)
    for _ in range(2): Match.objects.create(tournament=t, phase='SF', home=None, away=None)
    Match.objects.create(tournament=t, phase='3P', home=None, away=None)
    Match.objects.create(tournament=t, phase='F', home=None, away=None)

    return redirect('bracket')


def team_detail(request, pk):
    team = get_object_or_404(Team, pk=pk)
    t = team.tournament
    
    # Historique
    matches = Match.objects.filter(
        Q(home=team) | Q(away=team), 
        tournament=t, 
        played=True
    ).select_related('home','away').order_by('-id')
    
    # Stats
    played = matches.count()
    wins = draws = losses = 0
    gf = ga = 0
    
    for m in matches:
        is_home = m.home == team
        goals_for = m.home_goals if is_home else m.away_goals
        goals_against = m.away_goals if is_home else m.home_goals
        gf += goals_for or 0
        ga += goals_against or 0
        
        if goals_for > goals_against: wins += 1
        elif goals_for == goals_against: draws += 1
        else: losses += 1
    
    # Palmares simple (pour l'instant)
    palmares = {
        'titres': 0,  # on comptera les finales gagnées plus tard
        'finales': Match.objects.filter(tournament=t, phase='F', played=True).filter(Q(home=team)|Q(away=team)).count(),
        'participations': 1,
    }
    
    return render(request, 'competition/team_detail.html', {
        'team': team,
        'matches': matches[:10],
        'stats': {'played': played, 'wins': wins, 'draws': draws, 'losses': losses, 'gf': gf, 'ga': ga, 'gd': gf-ga},
        'palmares': palmares
    })


def reglement(request):
    return render(request, 'competition/reglement.html')


def registration_success(request, pk):
    team = get_object_or_404(Team, pk=pk)
    return render(request, 'competition/registration_success.html', {'team': team})


from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

@login_required
def my_team(request):
    t = get_tournament()
    team = get_object_or_404(Team, tournament=t, owner=request.user)
    return render(request, 'competition/my_team.html', {'team': team})

@login_required
def edit_team(request):
    t = get_tournament()
    team = get_object_or_404(Team, tournament=t, owner=request.user)
    
    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            new_name = form.cleaned_data['name']
            # anti-doublon sauf pour son équipe
            if Team.objects.filter(tournament=t, name__iexact=new_name).exclude(pk=team.pk).exists():
                messages.error(request, "Ce nom est déjà pris")
            else:
                form.save()
                messages.success(request, "Équipe mise à jour")
                return redirect('my_team')
    else:
        form = TeamForm(instance=team)
    
    return render(request, 'competition/edit_team.html', {'form': form, 'team': team})

@login_required
def delete_team(request):
    t = get_tournament()
    team = get_object_or_404(Team, tournament=t, owner=request.user)
    
    if request.method == 'POST':
        team.delete()
        messages.warning(request, "Ton équipe a été supprimée")
        return redirect('home')
    
    return render(request, 'competition/delete_team.html', {'team': team})

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Mot de passe changé")
            return redirect('my_team')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'competition/change_password.html', {'form': form})


@login_required
@user_passes_test(is_manager)
def manager_edit_team(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team)
        # en édition on ignore les champs user
        form.fields['owner_username'].required = False
        form.fields['owner_password'].required = False
        if form.is_valid():
            form.save()
            messages.success(request, f"{team.name} modifiée")
            return redirect('manager')
    else:
        form = TeamForm(instance=team)
        form.fields['owner_username'].widget = forms.HiddenInput()
        form.fields['owner_password'].widget = forms.HiddenInput()
    
    return render(request, 'competition/manager/edit_team.html', {'form': form, 'team': team})

@login_required
@user_passes_test(is_manager)
def manager_delete_any_team(request, pk):
    team = get_object_or_404(Team, pk=pk)
    name = team.name
    team.delete()
    messages.warning(request, f"{name} supprimée définitivement")
    return redirect('manager')


@login_required
@user_passes_test(is_manager)
def manager_users(request):
    # Tous les utilisateurs (avec leur équipe si elle existe)
    users = User.objects.all().prefetch_related('team_set').order_by('-is_staff', 'username')
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')
        u = get_object_or_404(User, pk=user_id)
        
        if action == 'promote':
            u.is_staff = True
            u.save()
            messages.success(request, f"{u.username} est maintenant Manager")
        elif action == 'demote':
            if u != request.user:
                u.is_staff = False
                u.save()
                messages.warning(request, f"{u.username} n'est plus Manager")
        
        return redirect('manager_users')
    
    return render(request, 'competition/manager/users.html', {'users': users})


@login_required
@user_passes_test(is_manager)
def set_strength(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if request.method == 'POST':
        strength = request.POST.get('strength', '0')
        team.collective_strength = int(strength) if strength.isdigit() else 0
        team.save()
        messages.success(request, f"{team.name} → {team.collective_strength}")
        return redirect('manager')
    return render(request, 'competition/manager/set_strength.html', {'team': team})


from django.db import transaction

@login_required
@user_passes_test(is_manager)
def reset_draw(request):
    t = get_tournament()
    try:
        with transaction.atomic():
            # 1. supprime les matchs de poule
            Match.objects.filter(tournament=t, stage='group').delete()
            # 2. vide les groupes
            Team.objects.filter(tournament=t).update(group=None)
            # 3. optionnel : vide aussi les groupes vides
            # Group.objects.filter(tournament=t).delete()
        
        messages.success(request, "✅ Tirage réinitialisé. Tu peux relancer.")
    except Exception as e:
        messages.error(request, f"Erreur reset: {str(e)}")
    
    return redirect('manager')


def groups_view(request):
    t = get_tournament()
    groups = Group.objects.filter(tournament=t).prefetch_related('team_set').order_by('name')
    return render(request, 'competition/groups.html', {'groups': groups})






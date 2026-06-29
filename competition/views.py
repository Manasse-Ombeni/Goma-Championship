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
from django.utils import timezone
from datetime import timedelta, time



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

def schedule(request):
    t = Tournament.objects.first()
    now = timezone.now()

    matches = Match.objects.filter(
        tournament=t, phase='group'
    ).select_related(
        'home', 'away', 'group', 'home__owner', 'away__owner'
    ).order_by('scheduled_at', 'group__name', 'id')

    user_team = (
        Team.objects.filter(tournament=t, owner=request.user).first()
        if request.user.is_authenticated else None
    )

    # ── Regroupement par journée via scheduled_at ────────────────
    # On détermine J1/J2/J3 selon la date du scheduled_at
    matches_by_day = {'J1': [], 'J2': [], 'J3': []}

    # Récupère les dates uniques triées pour identifier J1, J2, J3
    dates_uniques = sorted(set(
        m.scheduled_at.date()
        for m in matches
        if m.scheduled_at
    ))

    # Associe chaque date à une journée
    date_to_day = {}
    labels = ['J1', 'J2', 'J3']
    for i, date in enumerate(dates_uniques[:3]):
        date_to_day[date] = labels[i]

    for m in matches:
        # ── Compte à rebours ────────────────────────────────────
        if m.played:
            m.hours_left = 0
            m.minutes_left = 0
            m.countdown_label = "Terminé"
        elif m.scheduled_at:
            delta = m.scheduled_at - now
            total_seconds = max(0, int(delta.total_seconds()))
            m.hours_left = total_seconds // 3600
            m.minutes_left = (total_seconds % 3600) // 60
            m.countdown_ts = int(m.scheduled_at.timestamp())  # pour JS

            if total_seconds <= 0:
                m.countdown_label = "Temps écoulé"
            elif m.hours_left < 1:
                m.countdown_label = f"{m.minutes_left}min"
            else:
                m.countdown_label = f"{m.hours_left}h {m.minutes_left:02d}min"
        else:
            m.hours_left = 0
            m.minutes_left = 0
            m.countdown_label = "À planifier"
            m.countdown_ts = None

        m.is_mine = user_team and (m.home == user_team or m.away == user_team)

        # ── Affectation à la bonne journée ──────────────────────
        if m.scheduled_at:
            day_label = date_to_day.get(m.scheduled_at.date())
            if day_label:
                matches_by_day[day_label].append(m)
        else:
            # Fallback : répartition par index si pas de date
            # (ancien système, au cas où)
            group_matches = list(matches.filter(group=m.group))
            try:
                idx = group_matches.index(m)
                if idx < 2:
                    matches_by_day['J1'].append(m)
                elif idx < 4:
                    matches_by_day['J2'].append(m)
                else:
                    matches_by_day['J3'].append(m)
            except ValueError:
                matches_by_day['J1'].append(m)

    return render(request, 'competition/matches.html', {
        'days': matches_by_day,
        'user_team': user_team,
    })

def standings(request):
    t = Tournament.objects.first()
    groups = Group.objects.filter(tournament=t).order_by('name')

    matches = Match.objects.filter(tournament=t, phase='group', played=True).select_related('home','away','group')

    classement = {}
    for g in groups:
        # on prend les équipes via le FK inverse : team_set
        teams = Team.objects.filter(group=g, tournament=t)
        table = {team: {'pts':0,'j':0,'g':0,'n':0,'p':0,'bp':0,'bc':0} for team in teams}

        for m in matches.filter(group=g):
            th = table.get(m.home); ta = table.get(m.away)
            if not th or not ta: continue
            th['j'] += 1; ta['j'] += 1
            th['bp'] += m.home_goals; th['bc'] += m.away_goals
            ta['bp'] += m.away_goals; ta['bc'] += m.home_goals
            if m.home_goals > m.away_goals:
                th['pts'] += 3; th['g'] += 1; ta['p'] += 1
            elif m.home_goals < m.away_goals:
                ta['pts'] += 3; ta['g'] += 1; th['p'] += 1
            else:
                th['pts'] += 1; ta['pts'] += 1; th['n'] += 1; ta['n'] += 1

        lst = []
        for team, s in table.items():
            # adapte au template que tu as donné
            team.pts = s['pts']
            team.played = s['j']
            team.won = s['g']
            team.drawn = s['n']
            team.lost = s['p']
            team.gd = s['bp'] - s['bc']
            lst.append(team)
        
        lst.sort(key=lambda x: (-x.pts, -x.gd))
        classement[g.name] = lst

    return render(request, 'competition/standings.html', {'data': classement})

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

import random

@login_required
@user_passes_test(is_manager)
def generate_draw(request):
    t = get_tournament()
    teams = list(Team.objects.filter(tournament=t, is_validated=True))

    if len(teams)!= 32:
        messages.error(request, f"Il faut 32 équipes validées (actuellement {len(teams)})")
        return redirect('manager')

    # reset d'abord
    Team.objects.filter(tournament=t).update(group=None)
    Match.objects.filter(tournament=t, phase='group').delete()

    # groupes A-H
    groups = {}
    for letter in ['A','B','C','D','E','F','G','H']:
        grp, _ = Group.objects.get_or_create(tournament=t, name=letter)
        groups[letter] = grp

    # sépare
    with_strength = [tm for tm in teams if tm.collective_strength > 0]
    without_strength = [tm for tm in teams if tm.collective_strength == 0]

    with_strength.sort(key=lambda x: x.collective_strength, reverse=True)
    random.shuffle(without_strength)

    # --- CRÉE 4 POTS DE 8 ÉQUIPES ---
    pots = [[], [], [], []]

    # remplis avec les forces
    for i, team in enumerate(with_strength):
        pots[i % 4].append(team)

    # complète avec les sans-force
    all_teams = with_strength + without_strength
    # on veut exactement 8 par pot
    for pot in pots:
        while len(pot) < 8:
            if without_strength:
                pot.append(without_strength.pop(0))
            else:
                break

    # mélange chaque pot
    for pot in pots:
        random.shuffle(pot)

    # --- DISTRIBUTION : 1 équipe de chaque pot par groupe ---
    letters = ['A','B','C','D','E','F','G','H']
    for idx, letter in enumerate(letters):
        for pot_idx in range(4):
            if pots[pot_idx]:
                team = pots[pot_idx].pop(0)
                team.group = groups[letter]
                team.save()

    messages.success(request, "✅ Tirage équilibré : 8 groupes de 4")
    return redirect('manager')


@login_required
@user_passes_test(is_manager)
def generate_schedule(request):
    t = get_tournament()

    # ── Sauvegarde les résultats déjà joués ─────────────────────
    resultats_joues = {}
    for m in Match.objects.filter(tournament=t, phase='group', played=True):
        key = (m.group_id, m.home_id, m.away_id)
        resultats_joues[key] = {
            'home_goals': m.home_goals,
            'away_goals': m.away_goals,
        }

    # ── Supprime les anciens matchs ──────────────────────────────
    Match.objects.filter(tournament=t, phase='group').delete()

    # ── Calcule les deadlines ────────────────────────────────────
    # Sans pytz — compatible Render (UTC) et local
    now_utc = timezone.now()

    today_midnight_utc = now_utc.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Goma = UTC+2 → 23h59 local = 21h59 UTC
    deadlines = {
        'J1': today_midnight_utc + timedelta(hours=21, minutes=59),
        'J2': today_midnight_utc + timedelta(days=1, hours=21, minutes=59),
        'J3': today_midnight_utc + timedelta(days=2, hours=21, minutes=59),
    }

    # ── Recrée les matchs ────────────────────────────────────────
    for group in Group.objects.filter(tournament=t):
        teams = list(group.team_set.all())
        if len(teams) != 4:
            continue

        fixtures = [
            ('J1', [(0, 1), (2, 3)]),
            ('J2', [(0, 2), (1, 3)]),
            ('J3', [(0, 3), (1, 2)]),
        ]

        for day_label, pairs in fixtures:
            for a, b in pairs:
                home = teams[a]
                away = teams[b]
                key = (group.id, home.id, away.id)
                ancien = resultats_joues.get(key, {})
                played = bool(ancien)

                Match.objects.create(
                    tournament=t,
                    group=group,
                    home=home,
                    away=away,
                    phase='group',
                    played=played,
                    home_goals=ancien.get('home_goals'),
                    away_goals=ancien.get('away_goals'),
                    scheduled_at=deadlines[day_label],
                )

    messages.success(
        request,
        "📅 Calendrier régénéré — J1/J2/J3 sur 3 jours ✅"
    )
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
        # supprime les matchs de poule (phase='group')
        Match.objects.filter(tournament=t, phase='group').delete()
        # vide les groupes des équipes
        Team.objects.filter(tournament=t).update(group=None)
        messages.success(request, "✅ Tirage réinitialisé")
    except Exception as e:
        messages.error(request, f"Erreur reset: {e}")
    return redirect('manager')


def groups_view(request):
    t = get_tournament()
    groups = Group.objects.filter(tournament=t).prefetch_related('team_set').order_by('name')
    return render(request, 'competition/groups.html', {'groups': groups})



@login_required
def enter_result(request, match_id):
    if not request.user.is_staff:
        return redirect('schedule')

    m = get_object_or_404(Match, id=match_id)
    is_knockout = m.phase != 'group'

    if request.method == 'POST':
        if is_knockout:
            # ── Phase éliminatoire ──────────────────────────────
            hg = int(request.POST.get('hg', 0))
            ag = int(request.POST.get('ag', 0))
            et = request.POST.get('extra_time') == 'on'
            hget = int(request.POST.get('home_goals_et') or 0)
            aget = int(request.POST.get('away_goals_et') or 0)
            tab = request.POST.get('penalty_shootout') == 'on'
            hp = int(request.POST.get('home_penalties') or 0)
            ap = int(request.POST.get('away_penalties') or 0)

            m.home_goals = hg
            m.away_goals = ag
            m.extra_time = et
            m.home_goals_et = hget if et else None
            m.away_goals_et = aget if et else None
            m.penalty_shootout = tab
            m.home_penalties = hp if tab else None
            m.away_penalties = ap if tab else None
            m.played = True
            m.save()

            # ── Avancement automatique ──────────────────────────
            winner = m.winner
            loser = m.loser
            t = m.tournament

            if winner and m.phase in ['R16', 'QF', 'SF']:
                r16 = list(Match.objects.filter(tournament=t, phase='R16').order_by('id'))
                qf  = list(Match.objects.filter(tournament=t, phase='QF').order_by('id'))
                sf  = list(Match.objects.filter(tournament=t, phase='SF').order_by('id'))
                final = Match.objects.filter(tournament=t, phase='F').first()
                third = Match.objects.filter(tournament=t, phase='3P').first()

                if m.phase == 'R16':
                    idx = r16.index(m)
                    target = qf[idx // 2]
                    if idx % 2 == 0:
                        target.home = winner
                    else:
                        target.away = winner
                    target.save()

                elif m.phase == 'QF':
                    idx = qf.index(m)
                    target = sf[idx // 2]
                    if idx % 2 == 0:
                        target.home = winner
                    else:
                        target.away = winner
                    target.save()

                elif m.phase == 'SF':
                    idx = sf.index(m)
                    if idx == 0:
                        final.home = winner
                        if third: third.home = loser
                    else:
                        final.away = winner
                        if third: third.away = loser
                    final.save()
                    if third: third.save()

            return redirect('bracket')

        else:
            # ── Phase de groupes (ancien système) ──────────────
            m.home_goals = int(request.POST.get('hg', 0))
            m.away_goals = int(request.POST.get('ag', 0))
            m.played = True
            m.save()
            return redirect('schedule')

    return render(request, 'competition/enter_result.html', {
        'm': m,
        'is_knockout': is_knockout,
    })

def update_standings(group):
    teams = group.team_set.all()
    for t in teams:
        t.points = t.goals_for = t.goals_against = 0
        t.save()
    
    for m in Match.objects.filter(group=group, played=True):
        m.home.goals_for += m.home_goals
        m.home.goals_against += m.away_goals
        m.away.goals_for += m.away_goals
        m.away.goals_against += m.home_goals
        
        if m.home_goals > m.away_goals:
            m.home.points += 3
        elif m.away_goals > m.home_goals:
            m.away.points += 3
        else:
            m.home.points += 1
            m.away.points += 1
        m.home.save()
        m.away.save()








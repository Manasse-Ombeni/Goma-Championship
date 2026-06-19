from django.urls import path
from django.contrib.auth import views as auth_views
from competition import views

urlpatterns = [
    path('', views.home, name='home'),
    path('equipes/', views.teams, name='teams'),
    path('inscription/', views.team_register, name='register'),
    path('calendrier/', views.schedule, name='schedule'),  # <-- UNE SEULE FOIS
    path('classement/', views.standings, name='standings'),
    path('bracket/', views.bracket, name='bracket'),
    
    # Auth
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Manager
    path('manager/', views.manager_dashboard, name='manager'),
    path('manager/valider/<int:pk>/', views.validate_team, name='validate_team'),
    path('manager/match/<int:pk>/', views.match_update, name='match_update'),
    path('manager/tirage/', views.generate_draw, name='generate_draw'),
    path('manager/generer-calendrier/', views.generate_schedule, name='generate_schedule'),
    path('manager/knockout/', views.generate_knockout, name='generate_knockout'),
    path('equipe/<int:pk>/', views.team_detail, name='team_detail'),
    path('reglement/', views.reglement, name='reglement'),
    path('inscription/success/<int:pk>/', views.registration_success, name='registration_success'),
    path('manager/rejeter/<int:pk>/', views.reject_team, name='reject_team'),
    path('mon-equipe/', views.my_team, name='my_team'),
    path('mon-equipe/modifier/', views.edit_team, name='edit_team'),
    path('mon-equipe/supprimer/', views.delete_team, name='delete_team'),
    path('mon-equipe/mot-de-passe/', views.change_password, name='change_password'),
]
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register_face, name='register_face'),
    path('detect_frame/', views.detect_frame, name='detect_frame'),
    path('registered_faces/', views.registered_faces, name='registered_faces'),
]
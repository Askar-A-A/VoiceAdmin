from django.urls import path
from . import views, voice

urlpatterns = [
    # Web builder (login required)
    path('phone-menu/', views.ivr_builder, name='ivr_builder'),
    path('phone-menu/phone-number/', views.set_phone_number, name='set_phone_number'),
    path('phone-menu/<int:parent_pk>/add/', views.menu_create, name='menu_create'),
    path('phone-menu/menu/<int:pk>/edit/', views.menu_edit, name='menu_edit'),
    path('phone-menu/menu/<int:pk>/delete/', views.menu_delete, name='menu_delete'),

    # Telephony webhooks (public, called by CarrierX during a live call)
    path('voice/incoming/', voice.incoming_call, name='voice_incoming'),
    path('voice/access-code/', voice.access_code, name='voice_access_code'),
    path('voice/menu/<int:pk>/', voice.menu_input, name='voice_menu'),
    path('voice/menu/<int:pk>/record/', voice.menu_record, name='voice_record'),
    path('voice/play/<str:file_sid>/', voice.voice_play, name='voice_play'),
]

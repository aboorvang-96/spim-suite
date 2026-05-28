from django.urls import path
from . import views

app_name = 'material_stock'

urlpatterns = [
    path('',            views.index, name='index'),
    path('api/state/',  views.state, name='state'),
]

from django.urls import path
from .views import CreateOrganizationView, AddHrView

app_name = 'organizations'

urlpatterns = [
    path('create/', CreateOrganizationView.as_view(), name='create_organization'),
    path('add-hr/', AddHrView.as_view(), name='add_hr'),
]


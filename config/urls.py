from django.contrib import admin
from django.urls import path

from presence.api import api
from presence.views import board

urlpatterns = [
    path("", board, name="board"),
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]

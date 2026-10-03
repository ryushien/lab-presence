from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def board(request):
    """ドア前のモニターに出す在室一覧。表示用アカウントでログインしたままにしておく。"""
    return render(request, "presence/board.html")

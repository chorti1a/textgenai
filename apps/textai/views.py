import requests
import json
import secrets
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.conf import settings
from .lowman_analyzer import LowmanAnalyzer

# Конфигурация Bungie OAuth
BUNGIE_CLIENT_ID = "52030"
BUNGIE_CLIENT_SECRET = "L-DNQAwMFdl-CSBKSTwIh70ZBfoGoEsBhYJPtHnK98I"
BUNGIE_API_KEY = "f459aa35317b424c9829706e1c32ee1c"
REDIRECT_URI = "https://textgenai.onrender.com/textai/auth/callback/"

# Хранилище токенов (в продакшене использовать БД)
user_tokens = {}


def bungie_login(request):
    """Перенаправляет на страницу авторизации Bungie"""
    state = secrets.token_urlsafe(32)
    request.session['oauth_state'] = state

    auth_url = (
        "https://www.bungie.net/en/OAuth/Authorize"
        f"?client_id={BUNGIE_CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}"
    )
    return redirect(auth_url)


def bungie_callback(request):
    """Обрабатывает ответ от Bungie OAuth"""
    code = request.GET.get('code')
    state = request.GET.get('state')

    if state != request.session.get('oauth_state'):
        return JsonResponse({'error': 'Invalid state'}, status=400)

    # Обмениваем code на токен
    token_url = "https://www.bungie.net/Platform/App/OAuth/Token/"

    import base64
    auth_string = base64.b64encode(f"{BUNGIE_CLIENT_ID}:{BUNGIE_CLIENT_SECRET}".encode()).decode()

    headers = {
        "Authorization": f"Basic {auth_string}",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-API-Key": BUNGIE_API_KEY
    }

    data = f"grant_type=authorization_code&code={code}&redirect_uri={REDIRECT_URI}"

    response = requests.post(token_url, headers=headers, data=data)

    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data['access_token']
        membership_id = token_data['membership_id']

        # Сохраняем токен в сессии
        request.session['bungie_token'] = access_token
        request.session['membership_id'] = membership_id

        # Получаем имя пользователя
        user_info = get_bungie_profile(access_token, membership_id)
        request.session['username'] = user_info.get('displayName', 'Guardian')

        return redirect('/textai/')
    else:
        return JsonResponse({'error': 'Failed to get token'}, status=400)


def get_bungie_profile(token, membership_id):
    """Получает профиль пользователя"""
    url = f"https://www.bungie.net/Platform/User/GetMembershipsById/{membership_id}/254/"
    headers = {
        "X-API-Key": BUNGIE_API_KEY,
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get('Response', {}).get('bungieNetUser'):
            return data['Response']['bungieNetUser']
    return {}


def bungie_logout(request):
    """Выход из системы"""
    request.session.flush()
    return redirect('/')


def auth_status(request):
    """Возвращает статус авторизации"""
    if request.session.get('bungie_token'):
        return JsonResponse({
            'authenticated': True,
            'username': request.session.get('username', 'Guardian')
        })
    return JsonResponse({'authenticated': False})


# Обновлённая основная вьюха
def textai_view(request):
    if request.method == 'GET':
        return render(request, "textai.html")

    if request.method == 'POST':
        user_prompt = request.POST.get('prompt')

        if not user_prompt:
            return JsonResponse({'error': 'Please enter a prompt'}, status=400)

        # Проверяем ссылку на Raid Report
        if 'raid.report' in user_prompt or 'raidhub.io' in user_prompt:
            # Проверяем авторизацию
            token = request.session.get('bungie_token')
            if not token:
                return JsonResponse({
                    'error': 'Требуется авторизация',
                    'redirect': '/auth/login/'
                }, status=401)

            # Анализируем с токеном
            analyzer = LowmanAnalyzer(api_key=BUNGIE_API_KEY)
            analyzer.set_oauth_token(token)

            try:
                result = analyzer.analyze_profile(user_prompt)
                return JsonResponse({'result': result})
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)

        # Обычный ИИ запрос (если нужно)
        return JsonResponse({'result': 'Отправьте ссылку на Raid Report для анализа лоуменов!'})

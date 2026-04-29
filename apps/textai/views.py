import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .lowman_analyzer import LowmanAnalyzer

@csrf_exempt
def raid_duality_check(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            bungie_id = data.get('bungie_id', '').strip()
            
            if not bungie_id:
                return JsonResponse({'error': 'Введите Bungie ID'})
            
            analyzer = LowmanAnalyzer(api_key="YOUR_API_KEY")
            # Установите OAuth токен если есть
            # analyzer.set_oauth_token(request.session.get('oauth_token'))
            
            results = analyzer.check_duality_weapons(bungie_id)
            return JsonResponse(results)
        
        except Exception as e:
            return JsonResponse({'error': str(e)})
    
    return JsonResponse({'error': 'POST only'})

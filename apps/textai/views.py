from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .lowman_analyzer import LowmanAnalyzer


def raid_duality_tracker(request):
    return render(request, 'raid_duality_tracker.html')


@csrf_exempt
def raid_duality_check(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    
    try:
        data = json.loads(request.body)
        bungie_id = data.get('bungie_id', '').strip()
        
        if not bungie_id:
            return JsonResponse({'error': 'Введите Bungie ID'})
        
        if '#' not in bungie_id:
            return JsonResponse({'error': 'Формат: name#1234'})
        
        analyzer = LowmanAnalyzer(api_key="ВАШ_API_КЛЮЧ")
        
        results = analyzer.check_duality_weapons(bungie_id)
        return JsonResponse(results)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Невалидный JSON'})
    except Exception as e:
        return JsonResponse({'error': str(e)})

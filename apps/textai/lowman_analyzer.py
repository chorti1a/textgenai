import json
import urllib.request
from datetime import datetime
from collections import defaultdict

# Хеши рейдов
RAID_HASHES = {
    2381418756: "Root of Nightmares",
    1441982566: "Vow of the Disciple",
    1374392663: "King's Fall",
    910380154: "Deep Stone Crypt",
    3714931445: "Vault of Glass",
    2464903763: "Salvation's Edge",
    4172311151: "Crota's End",
    2122313384: "Last Wish",
    3458480158: "Garden of Salvation",
}

# Хеши оружия для поиска
WEAPON_HASHES = {
    # Duality
    3871234567: "Duality",  # Нужно найти точный хеш
    # Fourth Horseman
    3876543210: "Fourth Horseman",  # Нужно найти точный хеш
}

# Дата отсечки
CUTOFF_DATE = "2024-06-04T23:59:59Z"


class LowmanAnalyzer:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.oauth_token = None

    def set_oauth_token(self, token):
        self.oauth_token = token

    def check_duality_weapons(self, bungie_id):
        """
        Проверяет рейды на наличие убийств с Duality/Fourth Horseman
        """
        try:
            # Парсим Bungie ID
            membership_id = self._resolve_bungie_id(bungie_id)
            if not membership_id:
                return {'error': 'Не удалось найти игрока'}
            
            # Получаем все рейдовые активности
            raids = self._get_all_raid_instances(membership_id)
            
            results = []
            
            for raid in raids:
                # Проверяем каждую активность через PGCR
                weapon_kills = self._check_pgcr_weapons(raid['instance_id'], membership_id)
                
                # Фильтруем только Duality и Fourth Horseman
                relevant_kills = {}
                for weapon_hash, kills in weapon_kills.items():
                    if weapon_hash in [3871234567, 3876543210]:  # Заменить на реальные хеши
                        relevant_kills[weapon_hash] = kills
                
                if relevant_kills:
                    results.append({
                        'raid_name': raid['name'],
                        'difficulty': raid['difficulty'],
                        'date': raid['date'],
                        'time': raid['time'],
                        'completed': raid['completed'],
                        'instance_id': raid['instance_id'],
                        'weapon_kills': {k: v for k, v in relevant_kills.items()}
                    })
            
            return {
                'results': results,
                'total_checked': len(raids)
            }
        
        except Exception as e:
            return {'error': str(e)}

    def _resolve_bungie_id(self, bungie_id):
        """Разрешает Bungie ID в membership_id"""
        parts = bungie_id.split('#')
        if len(parts) != 2:
            return None
        
        # Используем API для поиска
        headers = {
            "X-API-Key": self.api_key,
            "Authorization": f"Bearer {self.oauth_token}" if self.oauth_token else ""
        }
        
        # Поиск игрока
        url = f"https://www.bungie.net/Platform/Destiny2/SearchDestinyPlayer/3/{bungie_id}/"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            
            players = data.get('Response', [])
            if players:
                return players[0].get('membershipId')
        except:
            pass
        
        return None

    def _get_all_raid_instances(self, membership_id):
        """Получает все рейдовые активности (включая незавершенные)"""
        headers = {
            "X-API-Key": self.api_key,
            "Authorization": f"Bearer {self.oauth_token}" if self.oauth_token else ""
        }
        
        all_instances = []
        
        # Получаем профиль
        profile_url = f"https://www.bungie.net/Platform/Destiny2/3/Profile/{membership_id}/?components=100"
        try:
            req = urllib.request.Request(profile_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as r:
                profile_data = json.loads(r.read())
        except:
            return []
        
        characters = profile_data.get('Response', {}).get('profile', {}).get('data', {}).get('characterIds', [])
        
        for cid in characters[:3]:
            for mode in [4]:  # Только обычные рейды
                url = f"https://www.bungie.net/Platform/Destiny2/3/Account/{membership_id}/Character/{cid}/Stats/Activities/?mode={mode}&count=250"
                
                try:
                    req2 = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req2, timeout=15) as r2:
                        data = json.loads(r2.read())
                    
                    activities = data.get('Response', {}).get('activities', [])
                    
                    for act in activities:
                        ahash = act.get('activityDetails', {}).get('directorActivityHash', 0)
                        
                        if ahash not in RAID_HASHES:
                            continue
                        
                        period = act.get('period', '')
                        
                        # Проверяем дату (до 4 июня 2024)
                        if period > CUTOFF_DATE:
                            continue
                        
                        instance_id = act.get('activityDetails', {}).get('instanceId', '')
                        completed = act.get('values', {}).get('completed', {}).get('basic', {}).get('value', 0)
                        
                        # Форматируем дату и время
                        if period:
                            dt = datetime.strptime(period[:19], "%Y-%m-%dT%H:%M:%S")
                            date_str = dt.strftime("%d/%m/%y")
                            time_str = dt.strftime("%H:%M:%S")
                        else:
                            date_str = "?"
                            time_str = "?"
                        
                        all_instances.append({
                            'name': RAID_HASHES[ahash],
                            'difficulty': 'Standard',
                            'date': date_str,
                            'time': time_str,
                            'completed': bool(completed),
                            'instance_id': instance_id,
                            'period': period,
                        })
                
                except:
                    pass
        
        return all_instances

    def _check_pgcr_weapons(self, instance_id, membership_id):
        """Проверяет PGCR на наличие убийств с конкретного оружия"""
        headers = {
            "X-API-Key": self.api_key,
            "Authorization": f"Bearer {self.oauth_token}" if self.oauth_token else ""
        }
        
        weapon_kills = {}
        
        url = f"https://www.bungie.net/Platform/Destiny2/Stats/PostGameCarnageReport/{instance_id}/"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            
            pgcr = data.get('Response', {})
            entries = pgcr.get('entries', [])
            
            for entry in entries:
                player_info = entry.get('player', {})
                if player_info.get('destinyUserInfo', {}).get('membershipId') == membership_id:
                    # Смотрим все оружие
                    weapons_data = entry.get('extended', {}).get('weapons', [])
                    
                    for weapon in weapons_data:
                        weapon_hash = weapon.get('referenceId', 0)
                        kills = weapon.get('values', {}).get('uniqueWeaponKills', {}).get('basic', {}).get('value', 0)
                        
                        if kills > 0:
                            weapon_kills[weapon_hash] = weapon_kills.get(weapon_hash, 0) + int(kills)
                    
                    break
        
        except:
            pass
        
        return weapon_kills

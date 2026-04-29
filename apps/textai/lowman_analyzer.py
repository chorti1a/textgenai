import json
import urllib.request
from datetime import datetime

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

DUALITY_HASH = 3865729795
FOURTH_HORSEMAN_HASH = 3465319058
CUTOFF_DATE = "2024-06-04T23:59:59Z"


class LowmanAnalyzer:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.oauth_token = None

    def set_oauth_token(self, token):
        self.oauth_token = token

    def _get_headers(self):
        headers = {"X-API-Key": self.api_key}
        if self.oauth_token:
            headers["Authorization"] = f"Bearer {self.oauth_token}"
        return headers

    def check_duality_weapons(self, bungie_id):
        try:
            display_name, code = bungie_id.split('#')
            membership_id = self._search_player(display_name, code)
            
            if not membership_id:
                return {'error': 'Игрок не найден'}
            
            raids = self._get_raid_instances(membership_id)
            
            if not raids:
                return {'results': [], 'total_checked': 0}
            
            results = []
            for raid in raids:
                weapon_kills = self._check_pgcr_weapons(raid['instance_id'], membership_id)
                if weapon_kills:
                    results.append({
                        'raid_name': raid['name'],
                        'difficulty': 'Standard',
                        'date': raid['date'],
                        'time': raid['time'],
                        'completed': raid['completed'],
                        'instance_id': raid['instance_id'],
                        'weapons': weapon_kills
                    })
            
            return {'results': results, 'total_checked': len(raids)}
        
        except Exception as e:
            return {'error': str(e)}

    def _search_player(self, display_name, code):
        """Ищет игрока по Bungie ID"""
        headers = self._get_headers()
        
        # Пробуем все платформы
        for platform in [3, 1, 2]:  # Steam, Xbox, PSN
            # Кодируем # как %23
            url = f"https://www.bungie.net/Platform/Destiny2/SearchDestinyPlayer/{platform}/{display_name}%23{code}/"
            
            try:
                print(f"Searching: {url}")  # Отладка
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read())
                
                print(f"Response: {data}")  # Отладка
                
                players = data.get('Response', [])
                if players:
                    return players[0].get('membershipId')
            except Exception as e:
                print(f"Error: {e}")
                continue
        
        return None

    def _get_raid_instances(self, membership_id):
        profile_url = f"https://www.bungie.net/Platform/Destiny2/3/Profile/{membership_id}/?components=100"
        try:
            req = urllib.request.Request(profile_url, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=10) as r:
                profile_data = json.loads(r.read())
        except:
            return []
        
        characters = profile_data.get('Response', {}).get('profile', {}).get('data', {}).get('characterIds', [])
        if not characters:
            return []
        
        all_instances = []
        
        for cid in characters[:3]:
            url = f"https://www.bungie.net/Platform/Destiny2/3/Account/{membership_id}/Character/{cid}/Stats/Activities/?mode=4&count=250"
            try:
                req2 = urllib.request.Request(url, headers=self._get_headers())
                with urllib.request.urlopen(req2, timeout=15) as r2:
                    data = json.loads(r2.read())
                
                activities = data.get('Response', {}).get('activities', [])
                
                for act in activities:
                    ahash = act.get('activityDetails', {}).get('directorActivityHash', 0)
                    if ahash not in RAID_HASHES:
                        continue
                    
                    period = act.get('period', '')
                    if period > CUTOFF_DATE:
                        continue
                    
                    instance_id = act.get('activityDetails', {}).get('instanceId', '')
                    completed = act.get('values', {}).get('completed', {}).get('basic', {}).get('value', 0)
                    
                    if period:
                        try:
                            dt = datetime.strptime(period[:19], "%Y-%m-%dT%H:%M:%S")
                            date_str = dt.strftime("%d/%m/%y")
                            time_str = dt.strftime("%H:%M:%S")
                        except:
                            date_str = "?"
                            time_str = "?"
                    else:
                        date_str = "?"
                        time_str = "?"
                    
                    all_instances.append({
                        'name': RAID_HASHES[ahash],
                        'date': date_str,
                        'time': time_str,
                        'completed': bool(completed),
                        'instance_id': instance_id,
                    })
            except:
                pass
        
        return all_instances

    def _check_pgcr_weapons(self, instance_id, membership_id):
        url = f"https://www.bungie.net/Platform/Destiny2/Stats/PostGameCarnageReport/{instance_id}/"
        try:
            req = urllib.request.Request(url, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            
            pgcr = data.get('Response', {})
            entries = pgcr.get('entries', [])
            
            weapon_kills = {}
            
            for entry in entries:
                player_info = entry.get('player', {})
                if player_info.get('destinyUserInfo', {}).get('membershipId') == membership_id:
                    weapons_data = entry.get('extended', {}).get('weapons', [])
                    
                    for weapon in weapons_data:
                        weapon_hash = weapon.get('referenceId', 0)
                        kills = weapon.get('values', {}).get('uniqueWeaponKills', {}).get('basic', {}).get('value', 0)
                        
                        if weapon_hash == DUALITY_HASH and kills > 0:
                            weapon_kills['Duality'] = int(kills)
                        elif weapon_hash == FOURTH_HORSEMAN_HASH and kills > 0:
                            weapon_kills['Fourth Horseman'] = int(kills)
                    
                    break
            
            return weapon_kills
        except:
            return {}

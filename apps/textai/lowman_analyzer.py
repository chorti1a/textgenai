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

    def test(self):
        return "LowmanAnalyzer is working!"

    def check_duality_weapons(self, bungie_id):
        debug_info = []
        
        try:
            debug_info.append(f"Input: {bungie_id}")
            
            if '#' not in bungie_id:
                return {'error': 'Формат должен быть name#1234', 'debug': '\n'.join(debug_info)}
            
            display_name, code = bungie_id.split('#')
            debug_info.append(f"Name: {display_name}, Code: {code}")
            
            membership_id = self._search_player(display_name, code, debug_info)
            
            if not membership_id:
                return {'error': 'Игрок не найден', 'debug': '\n'.join(debug_info)}
            
            debug_info.append(f"Membership ID: {membership_id}")
            
            raids = self._get_raid_instances(membership_id)
            debug_info.append(f"Found raids: {len(raids)}")
            
            if not raids:
                return {'results': [], 'total_checked': 0, 'debug': '\n'.join(debug_info)}
            
            results = []
            for raid in raids[:10]:
                weapon_kills = self._check_pgcr_weapons(raid['instance_id'], membership_id)
                debug_info.append(f"Raid: {raid['name']} | {raid['date']} | Weapons: {weapon_kills}")
                
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
            
            return {
                'results': results,
                'total_checked': len(raids),
                'debug': '\n'.join(debug_info)
            }
        
        except Exception as e:
            return {'error': str(e), 'debug': '\n'.join(debug_info)}

    def _search_player(self, display_name, code, debug_info):
        headers = self._get_headers()
        
        for platform in [3, 1, 2]:
            platform_name = {3: "Steam", 1: "Xbox", 2: "PSN"}[platform]
            url = f"https://www.bungie.net/Platform/Destiny2/SearchDestinyPlayer/{platform}/{display_name}%23{code}/"
            
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read())
                
                players = data.get('Response', [])
                debug_info.append(f"{platform_name}: {len(players)} players")
                
                if players:
                    player = players[0]
                    debug_info.append(f"Found: {player.get('displayName')}#{player.get('bungieNetDisplayCode')}")
                    return player.get('membershipId')
            except Exception as e:
                debug_info.append(f"{platform_name}: Error - {str(e)}")
        
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

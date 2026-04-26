import json
import urllib.request
import re
from datetime import datetime
from collections import defaultdict

RAID_DATABASE = {
    2381418756: {"name": "Root of Nightmares", "has_master": True},
    1441982566: {"name": "Vow of the Disciple", "has_master": True},
    1374392663: {"name": "King's Fall", "has_master": True},
    910380154: {"name": "Deep Stone Crypt", "has_master": False},
    3714931445: {"name": "Vault of Glass", "has_master": True},
    2464903763: {"name": "Salvation's Edge", "has_master": False},
    4172311151: {"name": "Crota's End", "has_master": True},
    2122313384: {"name": "Last Wish", "has_master": False},
    3458480158: {"name": "Garden of Salvation", "has_master": False},
}

PLAYER_TYPE_MAP = {1: "solo", 2: "duo", 3: "trio"}

PRIORITY = {
    "solo_flawless": 1, "duo_flawless": 2, "trio_flawless": 3,
    "full_solo": 4, "full_duo": 5, "full_trio": 6,
    "solo_checkpoint": 7, "duo_checkpoint": 8, "trio_checkpoint": 9,
    "master_full_trio": 10, "master_full_duo": 11, "master_full_solo": 12,
    "master_trio_checkpoint": 13, "master_duo_checkpoint": 14, "master_solo_checkpoint": 15,
}


class LowmanAnalyzer:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.oauth_token = None
        self.debug_log = []

    def set_oauth_token(self, token):
        self.oauth_token = token

    def is_raid_report_url(self, text):
        return any(x in text.lower() for x in ['raid.report', 'raidhub.io'])

    def extract_profile(self, url):
        url = url.rstrip('/')
        if '?' in url:
            url = url.split('?')[0]

        if "raid.report" in url:
            parts = url.split('/')
            for i, part in enumerate(parts):
                if part.isdigit() and len(part) > 10:
                    membership_id = part
                    platform = parts[i - 1] if i > 0 else 'pc'
                    break
            else:
                raise Exception("Не удалось найти ID в ссылке")
            platform_map = {'ps': 2, 'psn': 2, 'xb': 1, 'xbox': 1, 'pc': 3, 'steam': 3}
            membership_type = platform_map.get(platform.lower(), 3)
            return membership_type, membership_id

        elif "raidhub.io" in url:
            parts = url.split('/')
            for part in parts:
                if part.isdigit() and len(part) > 10:
                    membership_id = part
                    break
            else:
                raise Exception("Не удалось найти ID в ссылке RaidHub")
            return 3, membership_id

        raise Exception("Неподдерживаемый формат ссылки")

    def analyze_profile(self, url):
        self.debug_log = []
        
        try:
            membership_type, membership_id = self.extract_profile(url)
            raids = self._fetch_all_raids(membership_type, membership_id)
            
            # ВРЕМЕННО: дебаг
            if self.debug_log:
                return f"🔍 DEBUG:\n\n" + "\n".join(self.debug_log[-50:])
            
            if not raids:
                return "❌ Не удалось загрузить рейды."
            
            achievements = self._process_raids(raids)
            return self._format_results(achievements)
        except Exception as e:
            debug_text = "\n".join(self.debug_log[-20:]) if self.debug_log else ""
            return f"❌ Ошибка: {str(e)}\n\n{debug_text}"

    def _fetch_all_raids(self, membership_type, membership_id):
        """Получает ВСЕ рейдовые активности через PGCR"""
        headers = {
            "X-API-Key": self.api_key,
            "Authorization": f"Bearer {self.oauth_token}"
        }
        
        # Получаем профиль
        profile_url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/?components=100"
        req = urllib.request.Request(profile_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            profile_data = json.loads(r.read())
        
        characters = profile_data.get('Response', {}).get('profile', {}).get('data', {}).get('characterIds', [])
        self.debug_log.append(f"Characters: {len(characters)}")
        
        if not characters:
            return []
        
        all_activities = []
        
        # Собираем активности со всех персонажей, все режимы
        for cid in characters[:3]:
            for mode in [4, 84]:  # Normal and Master raids
                page = 0
                while True:
                    url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Account/{membership_id}/Character/{cid}/Stats/Activities/?mode={mode}&count=250&page={page}"
                    try:
                        req2 = urllib.request.Request(url, headers=headers)
                        with urllib.request.urlopen(req2, timeout=15) as r2:
                            data = json.loads(r2.read())
                        
                        activities = data.get('Response', {}).get('activities', [])
                        if not activities:
                            break
                        
                        all_activities.extend(activities)
                        
                        if len(activities) < 250:
                            break
                        
                        page += 1
                    except Exception as e:
                        self.debug_log.append(f"Error page {page}, mode {mode}: {e}")
                        break
        
        self.debug_log.append(f"Total activities: {len(all_activities)}")
        
        # Фильтруем только рейдовые и завершенные
        completed_raids = []
        lowman_raids = []
        
        for act in all_activities:
            details = act.get('activityDetails', {})
            ahash = details.get('directorActivityHash', 0)
            
            if ahash not in RAID_DATABASE:
                continue
            
            # Проверяем что активность завершена
            completed = act.get('values', {}).get('completed', {}).get('basic', {}).get('value', 0)
            if completed != 1:  # 1 = Yes, 0 = No
                continue
            
            player_count = int(act.get('values', {}).get('playerCount', {}).get('basic', {}).get('value', 0))
            
            is_master = (details.get('mode', 4) == 84)
            
            # Получаем детали через PGCR
            instance_id = details.get('instanceId', '')
            pgcr_data = self._get_pgcr_details(instance_id) if instance_id else None
            
            if pgcr_data:
                # Проверяем flawless
                entries = pgcr_data.get('entries', [])
                flawless = False
                deaths = 0
                start_from_beginning = pgcr_data.get('activityWasStartedFromBeginning', False)
                
                for entry in entries:
                    player_info = entry.get('player', {})
                    if player_info.get('destinyUserInfo', {}).get('membershipId') == membership_id:
                        flawless = entry.get('values', {}).get('flawless', {}).get('basic', {}).get('value', False)
                        deaths = int(entry.get('values', {}).get('deaths', {}).get('basic', {}).get('value', 0))
                        break
                
                is_flawless = flawless or (deaths == 0 and start_from_beginning)
                is_full = start_from_beginning
            else:
                is_flawless = False
                is_full = False
            
            raid_entry = {
                'hash': ahash,
                'players': player_count,
                'is_full': is_full,
                'is_flawless': is_flawless,
                'is_master': is_master,
            }
            
            completed_raids.append(raid_entry)
            
            if player_count in [1, 2, 3]:
                raid_name = RAID_DATABASE[ahash]['name']
                self.debug_log.append(f"LOWMAN: {raid_name} p={player_count} master={is_master} full={is_full} flawless={is_flawless}")
                lowman_raids.append(raid_entry)
        
        self.debug_log.append(f"Completed raids: {len(completed_raids)}")
        self.debug_log.append(f"Lowman raids: {len(lowman_raids)}")
        
        return lowman_raids  # Возвращаем только лоумены

    def _get_pgcr_details(self, activity_id):
        """Получает детали активности через PGCR"""
        headers = {
            "X-API-Key": self.api_key,
            "Authorization": f"Bearer {self.oauth_token}"
        }
        
        url = f"https://www.bungie.net/Platform/Destiny2/Stats/PostGameCarnageReport/{activity_id}/"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            return data.get('Response', {})
        except:
            return None

    def _process_raids(self, raids):
        results = {}
        for raid in raids:
            h = raid['hash']
            p = raid['players']
            
            if h not in results:
                results[h] = {'name': RAID_DATABASE[h]['name'], 'achievements': []}
            
            ptype = PLAYER_TYPE_MAP[p]
            
            if raid['is_flawless']:
                atype = f"{ptype}_flawless"
            elif raid['is_full']:
                prefix = "master_full_" if raid['is_master'] else "full_"
                atype = f"{prefix}{ptype}"
            else:
                prefix = "master_" if raid['is_master'] else ""
                atype = f"{prefix}{ptype}_checkpoint"
            
            results[h]['achievements'].append({
                'type': atype, 'players': p, 'is_master': raid['is_master'],
                'is_flawless': raid['is_flawless'], 'is_full': raid['is_full'],
            })
        
        final = {}
        for h, data in results.items():
            best = {}
            for ach in data['achievements']:
                key = ach['type']
                if key not in best or PRIORITY.get(key, 99) < PRIORITY.get(best[key]['type'], 99):
                    best[key] = ach
            
            # Убираем дубликаты
            for key in list(best.keys()):
                if 'flawless' in key:
                    base = key.replace('_flawless', '')
                    for suffix in ['_full', '_checkpoint']:
                        dup_key = f"{base}{suffix}" if not best[key]['is_master'] else f"master_{base}{suffix}"
                        if dup_key in best:
                            del best[dup_key]
                elif 'full' in key:
                    base = key.replace('full_', '').replace('master_full_', '')
                    cp_key = f"{base}_checkpoint" if not best[key]['is_master'] else f"master_{base}_checkpoint"
                    if cp_key in best:
                        del best[cp_key]
            
            final[h] = {'name': data['name'], 'achievements': list(best.values())}
        
        return final

    def _format_results(self, data):
        if not data:
            return "😕 Не найдено ни одного лоумена в истории."
        
        lines = ["🎯 **ЛУЧШИЕ ЛОУМЕНЫ**\n"]
        total = sum(len(v['achievements']) for v in data.values())
        lines.append(f"Всего достижений: {total}\n")
        
        for h in sorted(data.keys(), key=lambda x: data[x]['name']):
            raid = data[h]
            lines.append(f"**{raid['name']}**")
            raid['achievements'].sort(key=lambda x: PRIORITY.get(x['type'], 99))
            
            for ach in raid['achievements']:
                p = ach['players']
                plabel = "Solo" if p == 1 else "Duo" if p == 2 else "Trio"
                parts = []
                if ach['is_master']:
                    parts.append("🔥 Master")
                if ach['is_flawless']:
                    parts.append(f"💎 {plabel} Flawless")
                elif ach['is_full']:
                    parts.append(f"🎯 Full {plabel}")
                else:
                    parts.append(f"⭐ {plabel}")
                lines.append(f"  • {' '.join(parts)}")
            
            lines.append("")
        
        return "\n".join(lines)

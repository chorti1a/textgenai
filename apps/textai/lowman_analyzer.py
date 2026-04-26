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
            raids = self._fetch_raids_via_bungie(membership_type, membership_id)
            
            # ВРЕМЕННО: показываем дебаг-лог
            if self.debug_log:
                debug_text = "\n".join(self.debug_log)
                if len(debug_text) > 8000:
                    debug_text = debug_text[:8000] + "\n... (truncated)"
                return f"🔍 DEBUG INFO:\n\n{debug_text}\n\n=== END DEBUG ==="
            
            if not raids:
                return "❌ Не удалось загрузить рейды."
            
            achievements = self._process_raids(raids)
            return self._format_results(achievements)
        except Exception as e:
            debug_text = "\n".join(self.debug_log) if self.debug_log else "No debug data"
            return f"❌ Ошибка анализа: {str(e)}\n\n🔍 DEBUG:\n{debug_text}"

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
        except Exception as e:
            self.debug_log.append(f"  PGCR error: {e}")
            return None

    def _fetch_raids_via_bungie(self, membership_type, membership_id):
        self.debug_log.append("=== FETCHING RAIDS ===")
        self.debug_log.append(f"Membership Type: {membership_type}")
        self.debug_log.append(f"Membership ID: {membership_id}")
        
        headers = {
            "X-API-Key": self.api_key,
            "Authorization": f"Bearer {self.oauth_token}"
        }
        
        # Получаем профиль
        profile_url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/?components=100"
        try:
            req = urllib.request.Request(profile_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as r:
                profile_data = json.loads(r.read())
        except Exception as e:
            self.debug_log.append(f"ERROR getting profile: {e}")
            return []
        
        characters = profile_data.get('Response', {}).get('profile', {}).get('data', {}).get('characterIds', [])
        self.debug_log.append(f"Characters found: {len(characters)}")
        
        if not characters:
            return []
        
        all_activities = []
        
        for cid in characters[:1]:  # Берем только первого персонажа для теста
            for mode in [4, 84]:
                mode_name = "Normal" if mode == 4 else "Master"
                url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Account/{membership_id}/Character/{cid}/Stats/Activities/?mode={mode}&count=250"
                
                try:
                    req2 = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req2, timeout=15) as r2:
                        data = json.loads(r2.read())
                    activities = data.get('Response', {}).get('activities', [])
                    self.debug_log.append(f"Char {cid[:8]}... mode {mode} ({mode_name}): {len(activities)} activities")
                    all_activities.extend(activities)
                except Exception as e:
                    self.debug_log.append(f"ERROR char {cid[:8]}... mode {mode}: {e}")
        
        self.debug_log.append(f"\nTotal activities: {len(all_activities)}")
        
        # Анализируем только рейдовые активности
        raid_activities = []
        for act in all_activities:
            details = act.get('activityDetails', {})
            ahash = details.get('directorActivityHash', 0)
            if ahash in RAID_DATABASE:
                raid_activities.append(act)
        
        self.debug_log.append(f"Raid activities: {len(raid_activities)}")
        
        # Показываем ВСЕ поля первой рейдовой активности
        if raid_activities:
            first = raid_activities[0]
            self.debug_log.append(f"\n=== FULL ACTIVITY STRUCTURE ===")
            self.debug_log.append(json.dumps(first, indent=2, default=str)[:3000])
            
            # Получаем PGCR для деталей
            instance_id = first.get('activityDetails', {}).get('instanceId', '')
            if instance_id:
                self.debug_log.append(f"\n=== PGCR for {instance_id} ===")
                pgcr = self._get_pgcr_details(instance_id)
                if pgcr:
                    # Показываем ключевые поля
                    self.debug_log.append(f"Period: {pgcr.get('period')}")
                    self.debug_log.append(f"Starting Phase: {pgcr.get('startingPhaseIndex')}")
                    self.debug_log.append(f"Activity Was Started From Beginning: {pgcr.get('activityWasStartedFromBeginning')}")
                    
                    entries = pgcr.get('entries', [])
                    self.debug_log.append(f"Players in PGCR: {len(entries)}")
                    
                    # Ищем нашего игрока
                    for entry in entries:
                        player_info = entry.get('player', {})
                        if player_info.get('destinyUserInfo', {}).get('membershipId') == membership_id:
                            self.debug_log.append(f"\nOur player entry:")
                            self.debug_log.append(f"  Completed: {entry.get('values', {}).get('completed', {}).get('basic', {}).get('value')}")
                            self.debug_log.append(f"  Deaths: {entry.get('values', {}).get('deaths', {}).get('basic', {}).get('value')}")
                            self.debug_log.append(f"  Completed encounters: {entry.get('values', {}).get('activityCompletions', {}).get('basic', {}).get('value')}")
                            self.debug_log.append(f"  Flawless: {entry.get('values', {}).get('flawless', {}).get('basic', {}).get('value')}")
                            self.debug_log.append(f"  Player count: {entry.get('values', {}).get('playerCount', {}).get('basic', {}).get('value')}")
                            break
        
        return []

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

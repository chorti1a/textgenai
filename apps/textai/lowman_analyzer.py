import json
import urllib.request
import re
from datetime import datetime
from collections import defaultdict

RAID_DATABASE = {
    2381418756: {
        "name": "Root of Nightmares",
        "has_master": True,
    },
    1441982566: {
        "name": "Vow of the Disciple",
        "has_master": True,
    },
    1374392663: {
        "name": "King's Fall",
        "has_master": True,
    },
    910380154: {
        "name": "Deep Stone Crypt",
        "has_master": False,
    },
    3714931445: {
        "name": "Vault of Glass",
        "has_master": True,
    },
    2464903763: {
        "name": "Salvation's Edge",
        "has_master": False,
    },
    4172311151: {
        "name": "Crota's End",
        "has_master": True,
    },
    2122313384: {
        "name": "Last Wish",
        "has_master": False,
    },
    3458480158: {
        "name": "Garden of Salvation",
        "has_master": False,
    },
}

PLAYER_TYPE_MAP = {
    1: "solo",
    2: "duo",
    3: "trio"
}

# Приоритеты: меньше = лучше
PRIORITY = {
    "solo_flawless": 1,
    "duo_flawless": 2,
    "trio_flawless": 3,
    "full_solo": 4,
    "full_duo": 5,
    "full_trio": 6,
    "solo_checkpoint": 7,
    "duo_checkpoint": 8,
    "trio_checkpoint": 9,
    "master_full_trio": 10,
    "master_full_duo": 11,
    "master_full_solo": 12,
    "master_trio_checkpoint": 13,
    "master_duo_checkpoint": 14,
    "master_solo_checkpoint": 15,
}


class LowmanAnalyzer:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.oauth_token = None

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
        try:
            membership_type, membership_id = self.extract_profile(url)
            raids = self._fetch_raids_via_bungie(membership_type, membership_id)
            if not raids:
                return "❌ Не удалось загрузить рейды."
            
            achievements = self._process_raids(raids)
            return self._format_results(achievements)
        except Exception as e:
            return f"❌ Ошибка анализа: {str(e)}"

    def _fetch_raids_via_bungie(self, membership_type, membership_id):
        headers = {
            "X-API-Key": self.api_key,
            "Authorization": f"Bearer {self.oauth_token}"
        }
        
        profile_url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/?components=100"
        req = urllib.request.Request(profile_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            profile_data = json.loads(r.read())
        
        characters = profile_data.get('Response', {}).get('profile', {}).get('data', {}).get('characterIds', [])
        if not characters:
            return []
        
        all_activities = []
        for cid in characters[:3]:
            for mode in [4, 84]:  # Normal and Master raids
                url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Account/{membership_id}/Character/{cid}/Stats/Activities/?mode={mode}&count=100"
                try:
                    req2 = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req2, timeout=15) as r2:
                        data = json.loads(r2.read())
                    all_activities.extend(data.get('Response', {}).get('activities', []))
                except:
                    pass
        
        raids = []
        for act in all_activities:
            details = act.get('activityDetails', {})
            ahash = details.get('directorActivityHash', 0)
            
            if ahash not in RAID_DATABASE:
                continue
            
            try:
                players = act.get('values', {}).get('playerCount', {}).get('basic', {}).get('value', 0)
            except:
                players = act.get('values', {}).get('playerCount', {}).get('value', 0)
            
            if players not in [1, 2, 3]:
                continue
            
            # Определяем тип прохождения
            is_master = (details.get('mode', 4) == 84)
            
            # Проверяем full clear
            completions = act.get('values', {}).get('activityCompletions', {}).get('basic', {}).get('value', 0)
            
            # Проверяем flawless
            flawless = act.get('values', {}).get('flawless', {}).get('basic', {}).get('value', False)
            deaths = act.get('values', {}).get('deaths', {}).get('basic', {}).get('value', -1)
            
            is_flawless = flawless or (deaths == 0)
            is_full = completions > 0
            
            raids.append({
                'hash': ahash,
                'players': players,
                'is_full': is_full,
                'is_flawless': is_flawless,
                'is_master': is_master,
            })
        
        return raids

    def _process_raids(self, raids):
        """Группирует и находит лучшие достижения"""
        results = {}
        
        for raid in raids:
            h = raid['hash']
            p = raid['players']
            
            if h not in results:
                results[h] = {
                    'name': RAID_DATABASE[h]['name'],
                    'achievements': []
                }
            
            # Определяем тип достижения
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
                'type': atype,
                'players': p,
                'is_master': raid['is_master'],
                'is_flawless': raid['is_flawless'],
                'is_full': raid['is_full'],
            })
        
        # Убираем дубликаты (оставляем лучшее)
        final = {}
        for h, data in results.items():
            best = {}
            for ach in data['achievements']:
                key = ach['type']
                if key not in best or PRIORITY.get(key, 99) < PRIORITY.get(best[key]['type'], 99):
                    best[key] = ach
            
            # Убираем full если есть flawless
            keys_to_remove = []
            for key in best:
                if 'flawless' not in key:
                    flawless_key = key.replace('full_', '').replace('master_full_', 'master_') + '_flawless'
                    if flawless_key in best or key.replace('checkpoint', 'flawless') in best:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del best[key]
            
            final[h] = {
                'name': data['name'],
                'achievements': list(best.values())
            }
        
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
            
            # Сортируем по приоритету
            raid['achievements'].sort(key=lambda x: PRIORITY.get(x['type'], 99))
            
            for ach in raid['achievements']:
                label = self._get_label(ach)
                lines.append(f"  • {label}")
            
            lines.append("")
        
        return "\n".join(lines)

    def _get_label(self, ach):
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
        
        return " ".join(parts)

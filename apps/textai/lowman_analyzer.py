import json
import urllib.request
import re
from datetime import datetime
from collections import defaultdict

RAID_DATABASE = {
    2381418756: {
        "name": "Root of Nightmares",
        "has_master": True,
        "encounters": 4,
    },
    1441982566: {
        "name": "Vow of the Disciple",
        "has_master": True,
        "encounters": 4,
    },
    1374392663: {
        "name": "King's Fall",
        "has_master": True,
        "encounters": 5,
    },
    910380154: {
        "name": "Deep Stone Crypt",
        "has_master": False,
        "encounters": 4,
    },
    3714931445: {
        "name": "Vault of Glass",
        "has_master": True,
        "encounters": 5,
    },
    2464903763: {
        "name": "Salvation's Edge",
        "has_master": False,
        "encounters": 5,
    },
    4172311151: {
        "name": "Crota's End",
        "has_master": True,
        "encounters": 4,
    },
    2122313384: {
        "name": "Last Wish",
        "has_master": False,
        "encounters": 6,
    },
    3458480158: {
        "name": "Garden of Salvation",
        "has_master": False,
        "encounters": 4,
    },
}

DISPLAY_ORDER = {
    "flawless": 1,
    "full": 2,
    "checkpoint": 3
}

PLAYER_TYPE_MAP = {
    1: "solo",
    2: "duo", 
    3: "trio"
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
            
            achievements = self._categorize_achievements(raids)
            return self._format_achievements(achievements)
        except Exception as e:
            return f"❌ Ошибка анализа: {str(e)}"

    def _parse_duration(self, time_str):
        """Парсер времени"""
        if not time_str:
            return 0
        
        hours = minutes = seconds = 0
        
        h_match = re.search(r'(\d+)\s*h', time_str)
        if h_match:
            hours = int(h_match.group(1))
        
        m_match = re.search(r'(\d+)\s*m', time_str)
        if m_match:
            minutes = int(m_match.group(1))
        
        s_match = re.search(r'(\d+)\s*s', time_str)
        if s_match:
            seconds = int(s_match.group(1))
        
        return hours * 3600 + minutes * 60 + seconds

    def _is_fresh_activity(self, activity):
        """Определяет fresh activity (полное прохождение с начала)"""
        # Проверяем startsFromBeginning
        starts_from_beginning = activity.get('values', {}).get('startsFromBeginning', {}).get('basic', {}).get('value', False)
        if starts_from_beginning:
            return True
        
        # Проверяем activityCompletions
        completions = activity.get('values', {}).get('activityCompletions', {}).get('basic', {}).get('value', 0)
        if completions > 0:
            return True
        
        # Проверяем время (если длинное - вероятно full clear)
        ahash = activity.get('activityDetails', {}).get('directorActivityHash', 0)
        raid_info = RAID_DATABASE.get(ahash)
        if raid_info:
            time_seconds = self._parse_duration(
                activity.get('values', {}).get('activityDurationBasic', {}).get('displayValue', '0s')
            )
            min_full_time = raid_info.get('encounters', 3) * 600
            if time_seconds > min_full_time:
                return True
        
        return False

    def _is_flawless(self, activity):
        """Определяет flawless (без смертей)"""
        # Прямой флаг flawless
        if activity.get('values', {}).get('flawless', {}).get('basic', {}).get('value', False):
            return True
        
        # Deaths = 0
        deaths = activity.get('values', {}).get('deaths', {}).get('basic', {}).get('value', -1)
        if deaths == 0:
            return True
        
        # completionReason = 0
        completion_reason = activity.get('values', {}).get('completionReason', {}).get('basic', {}).get('value', -1)
        if completion_reason == 0:
            return True
        
        return False

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
    RAID_HASHES = set(RAID_DATABASE.keys())
    modes = [4, 84]
    
    # ДЕБАГ: счетчики
    debug_counts = {h: 0 for h in RAID_HASHES}
    
    for cid in characters[:3]:
        for mode in modes:
            url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Account/{membership_id}/Character/{cid}/Stats/Activities/?mode={mode}&count=100"
            try:
                req2 = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req2, timeout=15) as r2:
                    data = json.loads(r2.read())
                activities = data.get('Response', {}).get('activities', [])
                
                # ДЕБАГ: логируем
                print(f"Char {cid}, mode {mode}: found {len(activities)} activities")
                
                all_activities.extend(activities)
            except Exception as e:
                print(f"Error char {cid}, mode {mode}: {e}")
    
    raids = []
    for act in all_activities:
        details = act.get('activityDetails', {})
        ahash = details.get('directorActivityHash', 0)
        
        if ahash not in RAID_HASHES:
            continue
        
        debug_counts[ahash] += 1
        
        # ДЕБАГ: сырые данные
        print(f"\n=== Activity: {RAID_DATABASE[ahash]['name']} ===")
        print(f"Hash: {ahash}")
        print(f"Mode: {details.get('mode')}")
        print(f"Instance: {details.get('instanceId')}")
        
        try:
            players = act.get('values', {}).get('playerCount', {}).get('basic', {}).get('value', 0)
        except:
            players = act.get('values', {}).get('playerCount', {}).get('value', 0)
        
        print(f"Players: {players}")
        
        # ДЕБАГ: все значения для определения fresh/flawless
        values = act.get('values', {})
        for key in ['startsFromBeginning', 'activityCompletions', 'flawless', 'deaths', 'completionReason']:
            val = values.get(key, {}).get('basic', {}).get('value', 'N/A')
            print(f"{key}: {val}")
        
        if players not in [1, 2, 3]:
            continue
        
        is_master = details.get('mode', 4) == 84
        is_fresh = self._is_fresh_activity(act)
        is_flawless = self._is_flawless(act)
        
        print(f"is_master: {is_master}")
        print(f"is_fresh: {is_fresh}")
        print(f"is_flawless: {is_flawless}")
        
        raids.append({
            'hash': ahash,
            'players': players,
            'date': act.get('period', ''),
            'is_fresh': is_fresh,
            'is_flawless': is_flawless,
            'is_master': is_master,
        })
    
    print(f"\n=== FINAL COUNTS ===")
    for h, count in debug_counts.items():
        if count > 0:
            print(f"{RAID_DATABASE[h]['name']}: {count} activities")
    
    return raids

    def _categorize_achievements(self, raids):
        """Категоризирует достижения по рейдам и типам"""
        achievements = defaultdict(dict)
        
        for raid in raids:
            h = raid['hash']
            p = raid['players']
            player_type = PLAYER_TYPE_MAP[p]
            
            # Определяем категорию
            if raid['is_flawless']:
                category = 'flawless'
            elif raid['is_fresh']:
                category = 'full'
            else:
                category = 'checkpoint'
            
            # Создаем ключ с учетом мастер-версии
            key = f"{'master_' if raid['is_master'] else ''}{player_type}_{category}"
            
            # Сохраняем только факт наличия достижения
            if key not in achievements[h]:
                achievements[h][key] = {
                    'players': p,
                    'category': category,
                    'is_master': raid['is_master'],
                    'is_flawless': raid['is_flawless'],
                    'is_fresh': raid['is_fresh'],
                    'raid_name': RAID_DATABASE[h]['name'],
                }
        
        return achievements

    def _get_achievement_label(self, achievement):
        """Создает читаемую метку достижения"""
        p = achievement['players']
        player_label = "Solo" if p == 1 else "Duo" if p == 2 else "Trio"
        
        parts = []
        
        if achievement['is_master']:
            parts.append("🔥 Master")
        
        if achievement['is_flawless']:
            parts.append(f"💎 {player_label} Flawless")
        elif achievement['is_fresh']:
            parts.append(f"🎯 Full {player_label}")
        else:
            parts.append(f"⭐ {player_label}")
        
        return " ".join(parts)

    def _format_achievements(self, achievements):
        if not achievements:
            return "😕 Не найдено ни одного лоумена в истории."
        
        lines = ["🎯 **ЛУЧШИЕ ЛОУМЕНЫ**\n"]
        
        total_achievements = sum(len(raid_achievements) for raid_achievements in achievements.values())
        lines.append(f"Всего достижений: {total_achievements}\n")
        
        # Сортируем рейды по имени
        for h in sorted(achievements.keys(), key=lambda x: achievements[x][list(achievements[x].keys())[0]]['raid_name']):
            raid_data = achievements[h]
            
            # Сортируем достижения: flawless > full > checkpoint, solo > duo > trio
            sorted_keys = sorted(raid_data.keys(), 
                               key=lambda k: (
                                   DISPLAY_ORDER[raid_data[k]['category']],
                                   -raid_data[k]['is_master'],
                                   raid_data[k]['players']
                               ))
            
            lines.append(f"**{raid_data[sorted_keys[0]]['raid_name']}**")
            
            for key in sorted_keys:
                achievement = raid_data[key]
                label = self._get_achievement_label(achievement)
                lines.append(f"  • {label}")
            
            lines.append("")
        
        return "\n".join(lines)


# Пример использования
if __name__ == "__main__":
    analyzer = LowmanAnalyzer(api_key="YOUR_API_KEY")
    analyzer.set_oauth_token("YOUR_OAUTH_TOKEN")
    
    result = analyzer.analyze_profile("https://raid.report/pc/4611686018468854902")
    print(result)

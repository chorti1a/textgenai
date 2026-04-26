import json
import urllib.request
import re
from datetime import datetime
from collections import defaultdict

# Группы оружия для отслеживания
WEAPON_GROUPS = {
    "Duality": ["Duality"],
    "Lorentz Driver": ["Lorentz Driver"],
    "Icebreaker": ["Icebreaker"],
    "Last Foray": ["Last Foray"],
    "Frozen Orbit": ["Frozen Orbit"],
    "Izanagi's Burden": ["Izanagi's Burden"],
    "Vigilance Wing": ["Vigilance Wing"],
}

# Хеши рейдов и данжей
ACTIVITY_HASHES = {
    # Рейды
    2381418756: "Root of Nightmares",
    1441982566: "Vow of the Disciple",
    1374392663: "King's Fall",
    910380154: "Deep Stone Crypt",
    3714931445: "Vault of Glass",
    2464903763: "Salvation's Edge",
    4172311151: "Crota's End",
    2122313384: "Last Wish",
    3458480158: "Garden of Salvation",
    # Данжи
    1262461612: "Warlord's Ruin",
    1071234643: "Ghosts of the Deep",
    2032534092: "Duality",
    4281577380: "Spire of the Watcher",
    3455876045: "Grasp of Avarice",
    3019314560: "Prophecy",
    1211552239: "Pit of Heresy",
    1860896583: "Shattered Throne",
}


class ActivityAnalyzer:
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
            
            # Получаем данные
            activities = self._fetch_completed_activities(membership_type, membership_id)
            weapon_stats = self._fetch_weapon_stats(membership_type, membership_id)
            
            if not activities and not weapon_stats:
                return "❌ Не удалось загрузить данные."
            
            return self._format_analysis(activities, weapon_stats)
        except Exception as e:
            return f"❌ Ошибка анализа: {str(e)}"

    def _fetch_completed_activities(self, membership_type, membership_id):
        """Получает завершенные рейды и данжи"""
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
        
        if not characters:
            return {}
        
        completed_activities = {}
        
        # Берем только первого персонажа для скорости
        for cid in characters[:1]:
            for mode in [4, 84]:  # Normal and Master raids
                url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Account/{membership_id}/Character/{cid}/Stats/Activities/?mode={mode}&count=100"
                
                try:
                    req2 = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req2, timeout=15) as r2:
                        data = json.loads(r2.read())
                    
                    activities = data.get('Response', {}).get('activities', [])
                    
                    for act in activities:
                        ahash = act.get('activityDetails', {}).get('directorActivityHash', 0)
                        
                        if ahash not in ACTIVITY_HASHES:
                            continue
                        
                        # Проверяем завершение
                        completed = act.get('values', {}).get('completed', {}).get('basic', {}).get('value', 0)
                        if completed != 1:
                            continue
                        
                        activity_name = ACTIVITY_HASHES[ahash]
                        player_count = int(act.get('values', {}).get('playerCount', {}).get('basic', {}).get('value', 0))
                        is_master = (act.get('activityDetails', {}).get('mode', 4) == 84)
                        
                        # Определяем тип активности
                        activity_type = "🔥 Master " if is_master else ""
                        activity_type += "Raid" if ahash in [2381418756, 1441982566, 1374392663, 910380154, 3714931445, 2464903763, 4172311151, 2122313384, 3458480158] else "Dungeon"
                        
                        # Сохраняем лучший результат (минимальное количество игроков)
                        if activity_name not in completed_activities or player_count < completed_activities[activity_name]['players']:
                            completed_activities[activity_name] = {
                                'players': player_count,
                                'type': activity_type,
                                'date': act.get('period', '')
                            }
                
                except Exception as e:
                    print(f"Error fetching activities: {e}")
        
        return completed_activities

    def _fetch_weapon_stats(self, membership_type, membership_id):
        """Получает статистику по оружию"""
        headers = {
            "X-API-Key": self.api_key,
            "Authorization": f"Bearer {self.oauth_token}"
        }
        
        weapon_stats = {}
        
        # Получаем профиль с characters
        profile_url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/?components=100"
        req = urllib.request.Request(profile_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            profile_data = json.loads(r.read())
        
        characters = profile_data.get('Response', {}).get('profile', {}).get('data', {}).get('characterIds', [])
        
        if not characters:
            return weapon_stats
        
        # Для каждого персонажа получаем статистику оружия
        for cid in characters[:1]:
            url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Account/{membership_id}/Character/{cid}/Stats/UniqueWeapons/"
            
            try:
                req2 = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req2, timeout=15) as r2:
                    data = json.loads(r2.read())
                
                weapons = data.get('Response', {}).get('weapons', [])
                
                for weapon in weapons:
                    weapon_name = weapon.get('referenceId', '')
                    
                    # Проверяем каждую группу оружия
                    for group_name, weapon_list in WEAPON_GROUPS.items():
                        if weapon_name in weapon_list:
                            kills = weapon.get('values', {}).get('uniqueWeaponKills', {}).get('basic', {}).get('value', 0)
                            
                            if group_name not in weapon_stats:
                                weapon_stats[group_name] = 0
                            weapon_stats[group_name] += int(kills)
            
            except Exception as e:
                print(f"Error fetching weapon stats: {e}")
        
        return weapon_stats

    def _format_analysis(self, activities, weapon_stats):
        lines = ["🎯 **АНАЛИЗ ПРОФИЛЯ**\n"]
        
        # Секция с активностями
        if activities:
            lines.append("**Завершенные рейды и данжи:**\n")
            
            # Сортируем по типу и имени
            sorted_activities = sorted(activities.items(), key=lambda x: (x[1]['type'], x[0]))
            
            current_type = ""
            for name, info in sorted_activities:
                if info['type'] != current_type:
                    current_type = info['type']
                    lines.append(f"\n{current_type}:")
                
                lines.append(f"  • {name} ({info['players']} игроков)")
        
        # Секция с оружием
        if weapon_stats:
            lines.append("\n\n**Оружие и убийства:**\n")
            
            # Группа 1
            group1 = ["Duality", "Lorentz Driver", "Icebreaker", "Last Foray", "Frozen Orbit"]
            group1_stats = []
            for weapon in group1:
                if weapon in weapon_stats:
                    group1_stats.append(f"{weapon}: {weapon_stats[weapon]} kills")
            
            if group1_stats:
                lines.append("• " + " | ".join(group1_stats))
            
            # Группа 2
            group2 = ["Izanagi's Burden", "Vigilance Wing"]
            group2_stats = []
            for weapon in group2:
                if weapon in weapon_stats:
                    group2_stats.append(f"{weapon}: {weapon_stats[weapon]} kills")
            
            if group2_stats:
                lines.append("• " + " | ".join(group2_stats))
        
        if not activities and not weapon_stats:
            return "😕 Не найдено завершенных активностей или статистики оружия."
        
        return "\n".join(lines)

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
        "solo": {"excellent": 1500, "good": 2400, "decent": 3600},
        "duo": {"excellent": 1800, "good": 2700, "decent": 4200},
        "trio": {"excellent": 1500, "good": 2400, "decent": 3600},
        "best_class": "Warlock (Well of Radiance)"
    },
    1441982566: {
        "name": "Vow of the Disciple",
        "has_master": True,
        "encounters": 4,
        "solo": {"excellent": 5400, "good": 7200, "decent": 10800},
        "duo": {"excellent": 2700, "good": 4200, "decent": 6000},
        "trio": {"excellent": 2400, "good": 3600, "decent": 5400},
        "best_class": "Hunter (Void invis)"
    },
    1374392663: {
        "name": "King's Fall",
        "has_master": True,
        "encounters": 5,
        "solo": {"excellent": 6000, "good": 9000, "decent": 14400},
        "duo": {"excellent": 3600, "good": 5400, "decent": 7200},
        "trio": {"excellent": 3000, "good": 4800, "decent": 6600},
        "best_class": "Titan (Solar bonk)"
    },
    910380154: {
        "name": "Deep Stone Crypt",
        "has_master": False,
        "encounters": 4,
        "solo": {"excellent": 2400, "good": 4200, "decent": 6000},
        "duo": {"excellent": 1800, "good": 3000, "decent": 4800},
        "trio": {"excellent": 1500, "good": 2700, "decent": 4200},
        "best_class": "Hunter (Shatterskate)"
    },
    3714931445: {
        "name": "Vault of Glass",
        "has_master": True,
        "encounters": 5,
        "solo": {"excellent": 3600, "good": 5400, "decent": 7200},
        "duo": {"excellent": 2400, "good": 3600, "decent": 5400},
        "trio": {"excellent": 1800, "good": 3000, "decent": 4800},
        "best_class": "Warlock (Well skate)"
    },
    2464903763: {
        "name": "Salvation's Edge",
        "has_master": False,
        "encounters": 5,
        "solo": {"excellent": 7200, "good": 10800, "decent": 14400},
        "duo": {"excellent": 4800, "good": 7200, "decent": 10800},
        "trio": {"excellent": 3600, "good": 5400, "decent": 9000},
        "best_class": "Titan (Banner of War)"
    },
    4172311151: {
        "name": "Crota's End",
        "has_master": True,
        "encounters": 4,
        "solo": {"excellent": 2400, "good": 4200, "decent": 6000},
        "duo": {"excellent": 1800, "good": 3000, "decent": 4800},
        "trio": {"excellent": 1500, "good": 2400, "decent": 3600},
        "best_class": "Warlock (Well)"
    },
    2122313384: {
        "name": "Last Wish",
        "has_master": False,
        "encounters": 6,
        "solo": {"excellent": 5400, "good": 9000, "decent": 12600},
        "duo": {"excellent": 3600, "good": 5400, "decent": 7200},
        "trio": {"excellent": 2400, "good": 4200, "decent": 6000},
        "best_class": "Hunter (Shatterskate)"
    },
    3458480158: {
        "name": "Garden of Salvation",
        "has_master": False,
        "encounters": 4,
        "solo": {"excellent": 4200, "good": 6000, "decent": 9000},
        "duo": {"excellent": 2400, "good": 3600, "decent": 5400},
        "trio": {"excellent": 1800, "good": 3000, "decent": 4800},
        "best_class": "Warlock (Well)"
    },
}

# Приоритеты для сортировки (только для порядка отображения)
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
        """Улучшенный парсер времени"""
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
        # 1. Проверяем startsFromBeginning в extended данные
        starts_from_beginning = activity.get('values', {}).get('startsFromBeginning', {}).get('basic', {}).get('value', False)
        
        # 2. Проверяем activityCompletions - если 1 и больше, значит это полное прохождение
        completions = activity.get('values', {}).get('activityCompletions', {}).get('basic', {}).get('value', 0)
        if completions > 0:
            return True
        
        # 3. Дополнительная проверка - время прохождения
        # Если время больше минимального порога для этого рейда, вероятно это full clear
        ahash = activity.get('activityDetails', {}).get('directorActivityHash', 0)
        raid_info = RAID_DATABASE.get(ahash)
        if raid_info:
            time_seconds = self._parse_duration(
                activity.get('values', {}).get('activityDurationBasic', {}).get('displayValue', '0s')
            )
            # Минимальное время для full clear (примерно 10 минут на энкаунтер)
            min_full_time = raid_info.get('encounters', 3) * 600  # 10 минут на энкаунтер
            if time_seconds > min_full_time:
                return True
        
        return False

    def _is_flawless(self, activity):
        """Определяет flawless (без смертей)"""
        # 1. Прямой флаг flawless
        if activity.get('values', {}).get('flawless', {}).get('basic', {}).get('value', False):
            return True
        
        # 2. Проверка deaths = 0
        deaths = activity.get('values', {}).get('deaths', {}).get('basic', {}).get('value', -1)
        if deaths == 0:
            return True
        
        # 3. Проверка completionReason = 0 (успешное завершение без вайпов)
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
        
        # Режимы: 4 = Raid, 84 = Master Raid
        modes = [4, 84]
        
        for cid in characters[:3]:
            for mode in modes:
                url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Account/{membership_id}/Character/{cid}/Stats/Activities/?mode={mode}&count=100"
                try:
                    req2 = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req2, timeout=15) as r2:
                        data = json.loads(r2.read())
                    all_activities.extend(data.get('Response', {}).get('activities', []))
                except Exception as e:
                    print(f"Error char {cid}, mode {mode}: {e}")
        
        raids = []
        for act in all_activities:
            details = act.get('activityDetails', {})
            ahash = details.get('directorActivityHash', 0)
            
            if ahash not in RAID_HASHES:
                continue
            
            time_str = act.get('values', {}).get('activityDurationBasic', {}).get('displayValue', '0s')
            total_seconds = self._parse_duration(time_str)
            
            try:
                players = act.get('values', {}).get('playerCount', {}).get('basic', {}).get('value', 0)
            except:
                players = act.get('values', {}).get('playerCount', {}).get('value', 0)
            
            if players not in [1, 2, 3]:
                continue
            
            is_master = details.get('mode', 4) == 84
            
            raids.append({
                'hash': ahash,
                'time': total_seconds,
                'players': players,
                'date': act.get('period', ''),
                'is_fresh': self._is_fresh_activity(act),
                'is_flawless': self._is_flawless(act),
                'is_master': is_master,
                'raw_activity': act  # Сохраняем для дебага
            })
        
        return raids

    def _categorize_achievements(self, raids):
        """Категоризирует достижения по рейдам и типам"""
        # Структура: {raid_hash: {player_count: {clear_type: best_raid}}}
        achievements = defaultdict(lambda: defaultdict(dict))
        
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
            
            # Сохраняем лучшее время в категории
            if key not in achievements[h] or raid['time'] < achievements[h][key]['time']:
                achievements[h][key] = {
                    'time': raid['time'],
                    'players': p,
                    'category': category,
                    'is_master': raid['is_master'],
                    'is_flawless': raid['is_flawless'],
                    'is_fresh': raid['is_fresh'],
                    'raid_name': RAID_DATABASE[h]['name'],
                    'best_class': RAID_DATABASE[h]['best_class'],
                    'benchmarks': RAID_DATABASE[h][player_type]
                }
        
        return achievements

    def _format_time(self, seconds):
        if seconds == 0:
            return "0:00"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def _get_achievement_label(self, achievement):
        """Создает читаемую метку достижения"""
        p = achievement['players']
        player_label = "Solo" if p == 1 else "Duo" if p == 2 else "Trio"
        
        parts = []
        
        # Мастер-сложность
        if achievement['is_master']:
            parts.append("🔥 Master")
        
        # Основной тип
        if achievement['is_flawless']:
            parts.append(f"💎 {player_label} Flawless")
        elif achievement['is_fresh']:
            parts.append(f"🎯 Full {player_label}")
        else:
            parts.append(f"⭐ {player_label} (Checkpoint)")
        
        return " ".join(parts)

    def _get_time_rating(self, time_seconds, benchmarks):
        """Оценивает время"""
        exc = benchmarks.get('excellent', float('inf'))
        good = benchmarks.get('good', float('inf'))
        
        if time_seconds <= exc:
            return "💎 ОТЛИЧНОЕ ВРЕМЯ"
        elif time_seconds <= good:
            return "✅ ХОРОШЕЕ ВРЕМЯ"
        else:
            return "⚠️ МОЖНО УЛУЧШИТЬ"

    def _format_achievements(self, achievements):
        if not achievements:
            return "😕 Не найдено ни одного лоумена в истории."
        
        lines = ["🎯 **ЛУЧШИЕ ЛОУМЕНЫ**\n"]
        
        total_achievements = sum(len(raid_achievements) for raid_achievements in achievements.values())
        lines.append(f"Всего достижений: {total_achievements}\n")
        
        # Сортируем рейды по имени
        for h in sorted(achievements.keys(), key=lambda x: achievements[x][list(achievements[x].keys())[0]]['raid_name']):
            raid_data = achievements[h]
            
            # Сортируем достижения внутри рейда: flawless > full > checkpoint
            sorted_keys = sorted(raid_data.keys(), 
                               key=lambda k: (
                                   DISPLAY_ORDER[raid_data[k]['category']],
                                   -raid_data[k]['is_master'],  # мастер выше
                                   raid_data[k]['players']  # solo > duo > trio
                               ))
            
            for i, key in enumerate(sorted_keys):
                achievement = raid_data[key]
                
                if i == 0:
                    lines.append(f"**{achievement['raid_name']}**")
                
                label = self._get_achievement_label(achievement)
                time_str = self._format_time(achievement['time'])
                rating = self._get_time_rating(achievement['time'], achievement['benchmarks'])
                
                lines.append(f"  • {label}")
                lines.append(f"    ⏱ {time_str} | {rating}")
                
                # Показываем лучший класс только для первого достижения в рейде
                if i == 0 and achievement.get('best_class'):
                    lines.append(f"    💡 Лучший класс: {achievement['best_class']}")
            
            lines.append("")  # Разделитель между рейдами
        
        return "\n".join(lines)

# Пример использования
if __name__ == "__main__":
    analyzer = LowmanAnalyzer(api_key="YOUR_API_KEY")
    analyzer.set_oauth_token("YOUR_OAUTH_TOKEN")
    
    # Тест
    result = analyzer.analyze_profile("https://raid.report/pc/4611686018468854902")
    print(result)

# apps/textai/lowman_analyzer.py
import json
import urllib.request
import base64
from datetime import datetime

# База знаний по рейдам (сокращённая версия для демо)
RAID_DATABASE = {
    # Root of Nightmares
    2381418756: {
        "name": "Root of Nightmares",
        "solo": {"excellent": 1500, "good": 2400, "decent": 3600},
        "duo": {"excellent": 1800, "good": 2700, "decent": 4200},
        "trio": {"excellent": 1500, "good": 2400, "decent": 3600},
        "best_class": "Warlock (Well of Radiance)"
    },
    # Vow of the Disciple
    1441982566: {
        "name": "Vow of the Disciple",
        "solo": {"excellent": 5400, "good": 7200, "decent": 10800},
        "duo": {"excellent": 2700, "good": 4200, "decent": 6000},
        "trio": {"excellent": 2400, "good": 3600, "decent": 5400},
        "best_class": "Hunter (Void invis)"
    },
    # King's Fall
    1374392663: {
        "name": "King's Fall",
        "solo": {"excellent": 6000, "good": 9000, "decent": 14400},
        "duo": {"excellent": 3600, "good": 5400, "decent": 7200},
        "trio": {"excellent": 3000, "good": 4800, "decent": 6600},
        "best_class": "Titan (Solar bonk)"
    },
    # Deep Stone Crypt
    910380154: {
        "name": "Deep Stone Crypt",
        "solo": {"excellent": 2400, "good": 4200, "decent": 6000},
        "duo": {"excellent": 1800, "good": 3000, "decent": 4800},
        "trio": {"excellent": 1500, "good": 2700, "decent": 4200},
        "best_class": "Hunter (Shatterskate)"
    },
    # Vault of Glass
    3714931445: {
        "name": "Vault of Glass",
        "solo": {"excellent": 3600, "good": 5400, "decent": 7200},
        "duo": {"excellent": 2400, "good": 3600, "decent": 5400},
        "trio": {"excellent": 1800, "good": 3000, "decent": 4800},
        "best_class": "Warlock (Well skate)"
    },
    # Salvation's Edge
    2464903763: {
        "name": "Salvation's Edge",
        "solo": {"excellent": 7200, "good": 10800, "decent": 14400},
        "duo": {"excellent": 4800, "good": 7200, "decent": 10800},
        "trio": {"excellent": 3600, "good": 5400, "decent": 9000},
        "best_class": "Titan (Banner of War)"
    },
    # Crota's End
    4172311151: {
        "name": "Crota's End",
        "solo": {"excellent": 2400, "good": 4200, "decent": 6000},
        "duo": {"excellent": 1800, "good": 3000, "decent": 4800},
        "trio": {"excellent": 1500, "good": 2400, "decent": 3600},
        "best_class": "Warlock (Well)"
    },
    # Last Wish
    2122313384: {
        "name": "Last Wish",
        "solo": {"excellent": 5400, "good": 9000, "decent": 12600},
        "duo": {"excellent": 3600, "good": 5400, "decent": 7200},
        "trio": {"excellent": 2400, "good": 4200, "decent": 6000},
        "best_class": "Hunter (Shatterskate)"
    },
    # Garden of Salvation
    3458480158: {
        "name": "Garden of Salvation",
        "solo": {"excellent": 4200, "good": 6000, "decent": 9000},
        "duo": {"excellent": 2400, "good": 3600, "decent": 5400},
        "trio": {"excellent": 1800, "good": 3000, "decent": 4800},
        "best_class": "Warlock (Well)"
    },
}

DUNGEON_DATABASE = {
    1262461612: {"name": "Warlord's Ruin", "target": 2700, "class": "Titan"},
    1071234643: {"name": "Ghosts of the Deep", "target": 3600, "class": "Warlock"},
    2032534092: {"name": "Duality", "target": 2400, "class": "Hunter"},
}


class LowmanAnalyzer:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.oauth_token = None
        self.use_mock = False

    def set_oauth_token(self, token):
        """Устанавливает OAuth токен для запросов"""
        self.oauth_token = token

    def is_raid_report_url(self, text):
        return any(x in text.lower() for x in ['raid.report', 'raidhub.io'])

    def extract_profile(self, url):
        """Извлекает тип платформы и ID из ссылки"""
        url = url.rstrip('/')

        if '?' in url:
            url = url.split('?')[0]

        # Raid Report ссылка
        if "raid.report" in url:
            parts = url.split('/')

            for i, part in enumerate(parts):
                if part.isdigit() and len(part) > 10:
                    membership_id = part
                    if i > 0:
                        platform = parts[i - 1]
                    else:
                        platform = 'pc'
                    break
            else:
                raise Exception("Не удалось найти ID в ссылке")

            platform_map = {'ps': 2, 'psn': 2, 'xb': 1, 'xbox': 1, 'pc': 3, 'steam': 3}
            membership_type = platform_map.get(platform.lower(), 3)

            print(f"✅ Извлечено: platform={platform} -> type={membership_type}, id={membership_id}")
            return membership_type, membership_id

        # RaidHub ссылка
        elif "raidhub.io" in url:
            parts = url.split('/')
            for part in parts:
                if part.isdigit() and len(part) > 10:
                    membership_id = part
                    break
            else:
                raise Exception("Не удалось найти ID в ссылке RaidHub")

            membership_type = 3
            print(f"✅ RaidHub: type={membership_type}, id={membership_id}")
            return membership_type, membership_id

        raise Exception("Неподдерживаемый формат ссылки")

    def analyze_profile(self, url):
        """Основной метод анализа профиля"""
        try:
            membership_type, membership_id = self.extract_profile(url)
            print(f"🔍 Извлечено: type={membership_type}, id={membership_id}")

            try:
                raids = self._fetch_raids_from_bungie(membership_type, membership_id)
            except Exception as e:
                print(f"⚠️ Bungie API не сработал: {e}")
                raids = []

            if not raids:
                return "❌ Не удалось загрузить рейды.\n\nПроверьте:\n• Приватность профиля (должен быть открыт)\n• Правильность ссылки\n• Наличие рейдов в истории"

            analysis = self._analyze_raids(raids)
            return self._format_advice(analysis)

        except Exception as e:
            return f"❌ Ошибка анализа: {str(e)}"

    def _fetch_raids_from_bungie(self, membership_type, membership_id):
        """Загружает рейды через Bungie API"""
        
        headers = {
            "X-API-Key": self.api_key,
            "Authorization": f"Bearer {self.oauth_token}"
        }
        
        # Получаем список персонажей
        profile_url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Profile/{membership_id}/?components=100"
        req = urllib.request.Request(profile_url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=10) as response:
            profile_data = json.loads(response.read())
        
        characters = profile_data.get('Response', {}).get('profile', {}).get('data', {}).get('characterIds', [])
        
        if not characters:
            print("❌ Не найдено персонажей")
            return []
        
        # Берём всех персонажей (не только первого)
        all_activities = []
        for character_id in characters[:3]:  # Берём до 3 персонажей
            activity_url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Account/{membership_id}/Character/{character_id}/Stats/Activities/?mode=4&count=50"
            req2 = urllib.request.Request(activity_url, headers=headers)
            
            try:
                with urllib.request.urlopen(req2, timeout=10) as resp2:
                    activity_data = json.loads(resp2.read())
                all_activities.extend(activity_data.get('Response', {}).get('activities', []))
            except Exception as e:
                print(f"⚠️ Ошибка для персонажа {character_id}: {e}")
        
        print(f"📊 Всего активностей: {len(all_activities)}")
        
        # Хеши рейдов
        RAID_HASHES = {
            1374392663: "King's Fall",
            1441982566: "Vow of the Disciple",
            2381418756: "Root of Nightmares",
            910380154: "Deep Stone Crypt",
            3714931445: "Vault of Glass",
            2464903763: "Salvation's Edge",
            4172311151: "Crota's End",
            2122313384: "Last Wish",
            3458480158: "Garden of Salvation",
        }
        
        raids = []
        for act in all_activities:
            activity_hash = act.get('activityDetails', {}).get('directorActivityHash', 0)
            
            if activity_hash in RAID_HASHES:
                time_str = act.get('values', {}).get('activityDurationBasic', {}).get('displayValue', '0h 0m 0s')
                
                # Конвертируем "0h 23m 45s" в секунды
                parts = time_str.replace('h', '').replace('m', '').replace('s', '').split()
                if len(parts) == 3:
                    hours, minutes, seconds = map(int, parts)
                elif len(parts) == 2:
                    hours = 0
                    minutes, seconds = map(int, parts)
                else:
                    continue
                
                total_seconds = hours * 3600 + minutes * 60 + seconds
                player_count = act.get('values', {}).get('playerCount', {}).get('basic', {}).get('value', 0)
                
                raids.append({
                    'hash': activity_hash,
                    'time': total_seconds,
                    'players': player_count,
                    'date': act.get('period', '')
                })
        
        print(f"📊 Найдено рейдов: {len(raids)}")
        return raids

    def _analyze_raids(self, raids):
        """Анализирует рейды и находит лучшие времена"""
        best_times = {}
        print(f"🔍 Анализирую {len(raids)} рейдов...")

        for raid in raids:
            hash_key = raid['hash']
            print(f"  • Рейд с хешем {hash_key}, игроков: {raid['players']}, время: {raid['time']}с")

            if hash_key not in RAID_DATABASE:
                print(f"    ⚠️ Хеш {hash_key} не найден в базе")
                continue

            players = raid['players']
            time_sec = raid['time']

            if players == 1:
                lowman_type = 'solo'
            elif players == 2:
                lowman_type = 'duo'
            elif players == 3:
                lowman_type = 'trio'
            else:
                continue

            key = f"{hash_key}_{lowman_type}"
            if key not in best_times or time_sec < best_times[key]['time']:
                best_times[key] = {
                    'raid_name': RAID_DATABASE[hash_key]['name'],
                    'type': lowman_type,
                    'time': time_sec,
                    'benchmarks': RAID_DATABASE[hash_key][lowman_type],
                    'best_class': RAID_DATABASE[hash_key]['best_class']
                }

        return best_times

    def _format_time(self, seconds):
        """Форматирует секунды в ММ:СС"""
        return f"{seconds // 60}:{seconds % 60:02d}"

    def _format_advice(self, analysis):
        """Форматирует результат анализа в читаемый текст"""
        if not analysis:
            return "😕 Не найдено ни одного лоумена в истории. Попробуйте пройти соло/дуо/трио рейды!"

        lines = ["🎯 **АНАЛИЗ ЛОУМЕНОВ**\n"]
        lines.append(f"Найдено лоуменов: {len(analysis)}\n")

        needs_improve = []
        good_runs = []

        for key, data in analysis.items():
            time_str = self._format_time(data['time'])
            excellent = data['benchmarks']['excellent']
            good = data['benchmarks']['good']

            if data['time'] <= excellent:
                status = "💎 ОТЛИЧНО"
                good_runs.append((data['raid_name'], data['type'], time_str))
            elif data['time'] <= good:
                status = "✅ ХОРОШО"
                needs_improve.append((data['raid_name'], data['type'], time_str,
                                      self._format_time(excellent)))
            else:
                status = "⚠️ МОЖНО ЛУЧШЕ"
                needs_improve.append((data['raid_name'], data['type'], time_str,
                                      self._format_time(good)))

            lines.append(f"• {data['raid_name']} ({data['type']}): {time_str} — {status}")

        if needs_improve:
            lines.append("\n📈 **МОЖНО УЛУЧШИТЬ:**")
            for raid_name, ltype, current, target in needs_improve[:3]:
                lines.append(f"• {raid_name} {ltype}: {current} → цель {target}")

        completed_raids = set(data['raid_name'] for data in analysis.values())
        missing = [r for r in RAID_DATABASE.values() if r['name'] not in completed_raids]

        if missing:
            lines.append("\n🎯 **РЕКОМЕНДУЮ ПОПРОБОВАТЬ:**")
            for raid in missing[:2]:
                lines.append(f"• {raid['name']} соло на {raid['best_class']}")

        if len(analysis) >= 3:
            lines.append("\n💡 Ты уже неплохо шаришь! Попробуй соло Vow of the Disciple на Хантере с инвизом.")
        else:
            lines.append("\n💡 Начни с Deep Stone Crypt — самый простой рейд для соло.")

        return "\n".join(lines)

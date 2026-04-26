import json
import urllib.request
import base64
from datetime import datetime

# База знаний по рейдам (сокращённая версия для демо)
RAID_DATABASE = {
    2381418756: {
        "name": "Root of Nightmares",
        "solo": {"excellent": 1500, "good": 2400, "decent": 3600},
        "duo": {"excellent": 1800, "good": 2700, "decent": 4200},
        "trio": {"excellent": 1500, "good": 2400, "decent": 3600},
        "best_class": "Warlock (Well of Radiance)"
    },
    1441982566: {
        "name": "Vow of the Disciple",
        "solo": {"excellent": 5400, "good": 7200, "decent": 10800},
        "duo": {"excellent": 2700, "good": 4200, "decent": 6000},
        "trio": {"excellent": 2400, "good": 3600, "decent": 5400},
        "best_class": "Hunter (Void invis)"
    },
    1374392663: {
        "name": "King's Fall",
        "solo": {"excellent": 6000, "good": 9000, "decent": 14400},
        "duo": {"excellent": 3600, "good": 5400, "decent": 7200},
        "trio": {"excellent": 3000, "good": 4800, "decent": 6600},
        "best_class": "Titan (Solar bonk)"
    },
    910380154: {
        "name": "Deep Stone Crypt",
        "solo": {"excellent": 2400, "good": 4200, "decent": 6000},
        "duo": {"excellent": 1800, "good": 3000, "decent": 4800},
        "trio": {"excellent": 1500, "good": 2700, "decent": 4200},
        "best_class": "Hunter (Shatterskate)"
    },
    3714931445: {
        "name": "Vault of Glass",
        "solo": {"excellent": 3600, "good": 5400, "decent": 7200},
        "duo": {"excellent": 2400, "good": 3600, "decent": 5400},
        "trio": {"excellent": 1800, "good": 3000, "decent": 4800},
        "best_class": "Warlock (Well skate)"
    },
    2464903763: {
        "name": "Salvation's Edge",
        "solo": {"excellent": 7200, "good": 10800, "decent": 14400},
        "duo": {"excellent": 4800, "good": 7200, "decent": 10800},
        "trio": {"excellent": 3600, "good": 5400, "decent": 9000},
        "best_class": "Titan (Banner of War)"
    },
    4172311151: {
        "name": "Crota's End",
        "solo": {"excellent": 2400, "good": 4200, "decent": 6000},
        "duo": {"excellent": 1800, "good": 3000, "decent": 4800},
        "trio": {"excellent": 1500, "good": 2400, "decent": 3600},
        "best_class": "Warlock (Well)"
    },
    2122313384: {
        "name": "Last Wish",
        "solo": {"excellent": 5400, "good": 9000, "decent": 12600},
        "duo": {"excellent": 3600, "good": 5400, "decent": 7200},
        "trio": {"excellent": 2400, "good": 4200, "decent": 6000},
        "best_class": "Hunter (Shatterskate)"
    },
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
                return "❌ Не удалось загрузить рейды. Проверьте приватность профиля."
            analysis = self._analyze_raids(raids)
            return self._format_advice(analysis)
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
            url = f"https://www.bungie.net/Platform/Destiny2/{membership_type}/Account/{membership_id}/Character/{cid}/Stats/Activities/?mode=4&count=50"
            req2 = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req2, timeout=15) as r2:
                    data = json.loads(r2.read())
                all_activities.extend(data.get('Response', {}).get('activities', []))
            except Exception as e:
                print(f"Error char {cid}: {e}")
        RAID_HASHES = {
            1374392663, 1441982566, 2381418756, 910380154,
            3714931445, 2464903763, 4172311151, 2122313384, 3458480158
        }
        raids = []
        for act in all_activities:
            ahash = act.get('activityDetails', {}).get('directorActivityHash', 0)
            if ahash not in RAID_HASHES:
                continue
            time_str = act.get('values', {}).get('activityDurationBasic', {}).get('displayValue', '0h 0m 0s')
            parts = time_str.replace('h','').replace('m','').replace('s','').split()
            if len(parts) < 2:
                continue
            hours = int(parts[0]) if len(parts) == 3 else 0
            minutes = int(parts[-2])
            seconds = int(parts[-1])
            total = hours * 3600 + minutes * 60 + seconds
            try:
                players = act.get('values', {}).get('playerCount', {}).get('basic', {}).get('value', 0)
            except:
                players = act.get('values', {}).get('playerCount', {}).get('value', 0)
            raids.append({
                'hash': ahash,
                'time': total,
                'players': players,
                'date': act.get('period', '')
            })
        return raids

    def _analyze_raids(self, raids):
        best_times = {}
        for raid in raids:
            h = raid['hash']
            if h not in RAID_DATABASE:
                continue
            p = raid['players']
            if p == 1:
                lt = 'solo'
            elif p == 2:
                lt = 'duo'
            elif p == 3:
                lt = 'trio'
            else:
                continue
            key = f"{h}_{lt}"
            if key not in best_times or raid['time'] < best_times[key]['time']:
                best_times[key] = {
                    'raid_name': RAID_DATABASE[h]['name'],
                    'type': lt,
                    'time': raid['time'],
                    'benchmarks': RAID_DATABASE[h][lt],
                    'best_class': RAID_DATABASE[h]['best_class']
                }
        return best_times

    def _format_time(self, seconds):
        return f"{seconds // 60}:{seconds % 60:02d}"

    def _format_advice(self, analysis):
        if not analysis:
            return "😕 Не найдено ни одного лоумена в истории."
        lines = ["🎯 **АНАЛИЗ ЛОУМЕНОВ**\n", f"Найдено лоуменов: {len(analysis)}\n"]
        for key, data in analysis.items():
            t = self._format_time(data['time'])
            exc = data['benchmarks']['excellent']
            good = data['benchmarks']['good']
            if data['time'] <= exc:
                s = "💎 ОТЛИЧНО"
            elif data['time'] <= good:
                s = "✅ ХОРОШО"
            else:
                s = "⚠️ МОЖНО ЛУЧШЕ"
            lines.append(f"• {data['raid_name']} ({data['type']}): {t} — {s}")
        return "\n".join(lines)

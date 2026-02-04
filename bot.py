from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Discord Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import random
from datetime import datetime, timedelta
import os
import ssl
import certifi

# SSL 인증서 문제 해결 (Mac Python 3.13)
ssl_context = ssl.create_default_context(cafile=certifi.where())
discord.http.ssl_context = ssl_context

# ─────────────────────────────────────
# 운영자 설정
# ─────────────────────────────────────
ADMIN_IDS = [
    846266562267840512,
    1269794941450715297,
    1247101832040288287,
]

# 봇 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ─────────────────────────────────────
# 데이터 파일
# ─────────────────────────────────────
INVENTORY_FILE = 'inventories.json'
DANGER_FILE    = 'danger_levels.json'
GROUPS_FILE    = 'groups.json'

# ─────────────────────────────────────
# 게임 데이터
# ─────────────────────────────────────
ZONES = {
    'A': {
        'name': 'A 구역 - 폐허가 된 병원',
        'description': '깨진 유리창 사이로 바람이 불어온다. 의료 물품이 남아있을지도...',
        'unique_item': 'a아이템',
        'unique_chance': 0.15
    },
    'B': {
        'name': 'B 구역 - 버려진 연구소',
        'description': '어둡고 음산한 복도가 이어진다. 연구 자료가 있을 수 있다.',
        'unique_item': 'b아이템',
        'unique_chance': 0.15
    },
    'C': {
        'name': 'C 구역 - 황폐한 상점가',
        'description': '약탈당한 흔적이 역력하다. 하지만 아직 남은 물건이 있을지도.',
        'unique_item': 'c아이템',
        'unique_chance': 0.15
    }
}

COMMON_ITEMS = ['통조림', '붕대', '생수', '손전등 배터리', '로프', '구급상자']

EXPLORATION_CHOICES = {
    'A': [
        {'emoji': '🚪', 'label': '병실 문 열기',       'description': '삐걱거리는 병실 문을 조심스럽게 연다'},
        {'emoji': '💊', 'label': '약품 보관함 뒤지기', 'description': '의약품이 남아있을지 모른다'},
        {'emoji': '🔬', 'label': '검사실 확인하기',    'description': '실험 장비와 샘플이 있을 수 있다'}
    ],
    'B': [
        {'emoji': '💻', 'label': '컴퓨터 확인하기',    'description': '연구 데이터가 남아있을지도'},
        {'emoji': '📋', 'label': '서류 캐비닛 조사',   'description': '중요한 문서를 찾을 수 있다'},
        {'emoji': '🧪', 'label': '실험대 뒤지기',      'description': '연구 자료와 시약이 있을 것이다'}
    ],
    'C': [
        {'emoji': '🛒', 'label': '진열대 확인하기',    'description': '쓸만한 물건이 남아있을까'},
        {'emoji': '📦', 'label': '창고 뒤지기',        'description': '보관된 물품이 있을 수 있다'},
        {'emoji': '🏪', 'label': '계산대 서랍 열기',   'description': '숨겨둔 물건이 있을지도'}
    ]
}

# ─────────────────────────────────────
# 공통 유틸리티
# ─────────────────────────────────────
def load_json(filename, default=None):
    if default is None:
        default = {}
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def today_str() -> str:
    return datetime.now().strftime('%Y-%m-%d')

# ─────────────────────────────────────
# 인벤토리 관리
# ─────────────────────────────────────
def get_inventory(user_id):
    inventories = load_json(INVENTORY_FILE)
    user_id = str(user_id)
    if user_id not in inventories:
        inventories[user_id] = {}
    return inventories[user_id]

def add_item(user_id, item_name, quantity=1):
    inventories = load_json(INVENTORY_FILE)
    user_id = str(user_id)
    if user_id not in inventories:
        inventories[user_id] = {}
    if item_name in inventories[user_id]:
        inventories[user_id][item_name] += quantity
    else:
        inventories[user_id][item_name] = quantity
    save_json(INVENTORY_FILE, inventories)

def remove_item(user_id, item_name, quantity=1):
    inventories = load_json(INVENTORY_FILE)
    user_id = str(user_id)
    if user_id not in inventories or item_name not in inventories[user_id]:
        return False
    if inventories[user_id][item_name] < quantity:
        return False
    inventories[user_id][item_name] -= quantity
    if inventories[user_id][item_name] <= 0:
        del inventories[user_id][item_name]
    save_json(INVENTORY_FILE, inventories)
    return True

# ─────────────────────────────────────
# 그룹 관리
# ─────────────────────────────────────
def load_groups() -> dict:
    return load_json(GROUPS_FILE, {})

def save_groups(groups: dict):
    save_json(GROUPS_FILE, groups)

def get_group_names() -> list[str]:
    return list(load_groups().keys())

# ─────────────────────────────────────
# 위험도
# ─────────────────────────────────────
def get_danger_levels():
    danger_data = load_json(DANGER_FILE, {'levels': {}, 'last_update': None})
    today = today_str()
    if danger_data['last_update'] != today:
        danger_data['levels'] = {
            'A': random.randint(1, 5),
            'B': random.randint(1, 5),
            'C': random.randint(1, 5)
        }
        danger_data['last_update'] = today
        save_json(DANGER_FILE, danger_data)
    return danger_data['levels']

def get_mob_chance(danger_level):
    return danger_level * 0.15

# ─────────────────────────────────────
# 탐색 결과 계산
# ─────────────────────────────────────
def calculate_exploration_result(zone, danger_level):
    mob_chance = get_mob_chance(danger_level)
    if random.random() < mob_chance:
        return {
            'type': 'mob',
            'message': '⚠️ **몹과 조우했습니다!**\n좀비 무리가 당신을 발견했다! 황급히 도망쳤지만 아이템을 얻지 못했습니다.',
            'items': []
        }

    items_found = []
    common_item_count = random.randint(1, 3)
    for _ in range(common_item_count):
        if random.random() < 0.7:
            items_found.append(random.choice(COMMON_ITEMS))
    if random.random() < ZONES[zone]['unique_chance']:
        items_found.append(ZONES[zone]['unique_item'])

    if items_found:
        return {
            'type': 'success',
            'message': '✅ **탐색 성공!**\n조심스럽게 주변을 뒤져 물건을 찾았습니다.',
            'items': items_found
        }
    return {
        'type': 'nothing',
        'message': '😕 **아무것도 찾지 못했습니다.**\n이미 누군가 다녀간 것 같습니다.',
        'items': []
    }

exploring_users = set()

# ─────────────────────────────────────
# 간단한 봇 이벤트와 커맨드만 포함
# ─────────────────────────────────────
@bot.event
async def on_ready():
    print(f'{bot.user} 봇이 준비되었습니다!')
    try:
        synced = await bot.tree.sync()
        print(f'{len(synced)}개의 슬래시 커맨드가 동기화되었습니다.')
    except Exception as e:
        print(f'커맨드 동기화 실패: {e}')

@bot.tree.command(name="핑", description="봇 응답 테스트")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! 봇이 정상 작동 중입니다.")

@bot.tree.command(name="인벤토리", description="자신의 인벤토리를 확인합니다")
async def inventory(interaction: discord.Interaction):
    user_inventory = get_inventory(interaction.user.id)
    embed = discord.Embed(
        title=f"🎒 {interaction.user.display_name}의 인벤토리",
        color=discord.Color.gold()
    )
    if not user_inventory:
        embed.description = "인벤토리가 비어있습니다."
    else:
        items_text = ""
        for item, quantity in sorted(user_inventory.items()):
            items_text += f"• **{item}** x{quantity}\n"
        embed.description = items_text
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="위험도", description="오늘의 구역별 위험도를 확인합니다")
async def danger(interaction: discord.Interaction):
    danger_levels = get_danger_levels()
    embed = discord.Embed(
        title="⚠️ 오늘의 구역별 위험도",
        description="위험도는 매일 자정에 갱신됩니다.",
        color=discord.Color.orange()
    )
    for zone, level in danger_levels.items():
        stars = '⭐' * level
        mob_chance = int(get_mob_chance(level) * 100)
        embed.add_field(
            name=f"{ZONES[zone]['name']}",
            value=f"{stars} ({level}/5)\n몹 조우 확률: {mob_chance}%",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

# ─────────────────────────────────────
# 봇 실행
# ─────────────────────────────────────
if __name__ == "__main__":
    keep_alive()  # Flask HTTP 서버 시작
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print(" notocken ")
        exit(1)
    bot.run(TOKEN)

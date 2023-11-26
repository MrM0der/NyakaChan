import discord
from discord.ext import commands
from discord import Message
from anime_muip import AnimeMUIP
import json
import time
import docker
from threading import Thread
from discord_webhook import DiscordWebhook
from dotenv import load_dotenv
import os
from jishaku.cog import Jishaku
import asyncio

load_dotenv()

GIO_SECRET_TOKEN = os.getenv('GIO_SECRET_TOKEN')
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
BOT_PREFIX = '`'

# Загрузка userdb из JSON файла при запуске
try:
    with open('userdb.json', 'r') as f:
        userdb = {int(k): v for k, v in json.load(f).items()}
except FileNotFoundError:
    userdb = {}
# Сохранение userdb в JSON файл при каждом его обновлении


def save_userdb():
    with open('userdb.json', 'w') as f:
        json.dump(userdb, f)


intents = discord.Intents.all()
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)
bot.remove_command('help')

# Создаем клиент AnimeMUIP
client = AnimeMUIP(GIO_SECRET_TOKEN, ip='10.242.1.1')

# Создаем клиент Docker
docker_client = docker.from_env()


def get_container_id(name):
    client = docker.from_env()
    containers = client.containers.list(all=True)
    for container in containers:
        if container.name == name:
            return container.id[:12]
    return None


# Список контейнеров
gio_docker_names = ['32_dev-redis-1', '32_dev-mysql-1', '32_dev-sdk-1', '32_dev-adminer-1', '32_dev-dispatch-1', '32_dev-phpmyadmin-1',
                    '32_dev-nodeserver-1', '32_dev-dbgate-1', '32_dev-gateserver-1', '32_dev-multiserver-1', '32_dev-muipserver-1', '32_dev-gameserver-1']
containers = []

for i in gio_docker_names:
    containers.append(get_container_id(i))

# print(containers)

# Словарь сообщений
messages = {
    'recv from nodeserver timeout': 'Мне воздуху этот предмет давать? Или ты всё-таки зайдёшь в игру?',
    'succ': 'Я выполнила твой запрос :heart:',
    'RET_FAIL': 'Ты чё колдун? Я просила команду, а ты хуячишь заклинание.'
}


@bot.command()
async def help(ctx):
    await ctx.send(f'Нету хелпа, есть только {BOT_PREFIX}give')
    if await bot.is_owner(ctx.author):
        await ctx.send(f'А для тебя, владелец, есть команда {BOT_PREFIX}_help')


@bot.command()
async def give(ctx, command: str = None, id: str = None, count='1'):
    if command is None or id is None:
        await ctx.send('**Использование команды `give <command> <id> [count]`**: \n'
                       '- `<command>` - это команда, которую вы хотите выполнить (`item`, `avatar`, `mcoin`),\n'
                       '- `<id>` - это ID предмета или аватара (Для mcoin не указывать!),\n'
                       '- `[count]` - это количество, которое вы хотите добавить (по умолчанию 1).\n')
        return

    if ctx.author.id in userdb:
        uid = userdb[ctx.author.id]
        if command in ['item', 'avatar', 'mcoin']:
            if command == 'mcoin':
                await ctx.send(f'Передан UID: {uid}, Количество: {id}.')
                msg = f'{command} {id}'
            else:
                await ctx.send(f'Передан UID: {uid}, ID предмета: {id}, Количество: {count}.')
                msg = f'{command} add {id} {count}'
            response = client.muip_client(uid, msg)
            res = json.loads(response)
            if res['msg'] in messages:
                await ctx.send(messages[res['msg']])
            else:
                await ctx.send(res['msg'])
        else:
            await ctx.send('Такой команды не существует.')
    else:
        await ctx.send('Ваш дискорд аккаунт не привязан к аккаунту GIO. Обратитесь к администратору.')


@bot.command()
@commands.is_owner()
async def muip(ctx, number: int, *args):
    command = ' '.join(args)
    await ctx.send(f"Передан UID: {number}, команда: {command}")
    await ctx.send(client.muip_client(number, command))


@bot.command()
@commands.is_owner()
async def _help(ctx, arg=None):
    if arg is not None:
        await ctx.send_help(arg)
    else:
        await ctx.send_help()


@bot.command()
@commands.is_owner()
async def shutdown(ctx):
    await ctx.send("Выключаюсь...")
    await bot.close()


def dockerlogs_discord(container_id):
    # print(container_id)
    try:
        container = docker_client.containers.get(container_id)
        containername = container.attrs['Name']

        for line in container.logs(stream=True, tail=0):
            webhook = DiscordWebhook(
                url=WEBHOOK_URL, content=f'```bash\n{str(containername + " >>> " + line.strip().decode())}\n```')
            response = webhook.execute()
            time.sleep(2)
    except Exception as e:
        print(f"Error::: {e}")


async def bot_status():
    while True:
        try:
            await bot.change_presence(activity=discord.Streaming(name="Genshin Impact Offline", url="https://www.twitch.tv//"))
        except Exception as e:
            print(f"error:::: {e}")
        await asyncio.sleep(10)


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    await bot.add_cog(Jishaku(bot=bot))
    asyncio.create_task(bot_status())
    try:
        for i in containers:
            th = Thread(target=dockerlogs_discord, args=(i, ))
            th.start()
    except:
        pass

bot.run(DISCORD_BOT_TOKEN)

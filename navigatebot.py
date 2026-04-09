import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Button, View, Select
from typing import Optional
from types import SimpleNamespace
import os
import re
import json
import time
import asyncio
import random
import secrets
import zipfile
import io
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
import aiohttp

from bot_modules import crypto_tools, mail_tools, steam_tools, upload_tools

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN', '').strip()
BOT_NAME = os.getenv('BOT_NAME', 'navigatebot').strip() or 'navigatebot'

WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '').strip()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.voice_states = True
intents.guilds = True
intents.moderation = True

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)  
bot.remove_command('help')

CATEGORIA_ARQUIVO = 'categorias/racismo.txt'
STATS_FILE = 'stats.json'
IMUNE_FILE = 'imune.json'
PUNIDOS_FILE = 'punidos.json'
LIMITES_FILE = 'limites.json'
PURGE_FILE = 'purge.json'
SORTEIO_FILE = 'sorteio.json'
SORTEIOS_ATIVOS_FILE = 'sorteios_ativos.json'
CONFIG_FILE = 'config.json'
UPLOADS_DIR = "uploads"
RESENHA_FILE = 'resenha.json'
EMAILS_DIR = "emails"          
EMAILS_EXPIRATION_HOURS = 24   
STEAM_LINKS_FILE = 'steam_links.json'
MAILTM_ACCOUNTS_FILE = 'mailtm_accounts.json'

CONFIG_FILE = crypto_tools.CONFIG_FILE
STEAM_LINKS_FILE = steam_tools.STEAM_LINKS_FILE
MAILTM_ACCOUNTS_FILE = mail_tools.MAILTM_ACCOUNTS_FILE
EMAILS_EXPIRATION_HOURS = mail_tools.EMAILS_EXPIRATION_HOURS

config = crypto_tools.config
ultima_analise = {}
ultima_atualizacao = None

upload_para_catbox = upload_tools.upload_para_catbox
salvar_metadados = upload_tools.salvar_metadados
carregar_metadados = upload_tools.carregar_metadados

load_steam_links = steam_tools.load_steam_links
save_steam_links = steam_tools.save_steam_links
save_steam_link = steam_tools.save_steam_link
get_steam_link = steam_tools.get_steam_link
remove_steam_link = steam_tools.remove_steam_link
build_steam_embed_from_info = steam_tools.build_steam_embed_from_info
create_steam_verification_code = steam_tools.create_steam_verification_code
get_pending_steam_code = steam_tools.get_pending_steam_code
clear_pending_steam_code = steam_tools.clear_pending_steam_code
extract_steam_id_from_payload = steam_tools.extract_steam_id_from_payload
steam_get_user_info = steam_tools.steam_get_user_info
verify_steam_profile_code = steam_tools.verify_steam_profile_code
get_steam_settings = steam_tools.get_steam_settings
update_steam_settings = steam_tools.update_steam_settings
build_styled_steam_embed = steam_tools.build_styled_steam_embed
refresh_linked_steam = steam_tools.refresh_linked_steam

enviar_email = mail_tools.enviar_email
listar_emails = mail_tools.listar_emails
ler_email = mail_tools.ler_email
excluir_email = mail_tools.excluir_email
load_mailtm_accounts = mail_tools.load_mailtm_accounts
save_mailtm_accounts = mail_tools.save_mailtm_accounts
get_mailtm_account = mail_tools.get_mailtm_account
save_mailtm_account = mail_tools.save_mailtm_account
delete_mailtm_account = mail_tools.delete_mailtm_account
mailtm_create_account_for_user = mail_tools.mailtm_create_account_for_user
mailtm_list_messages = mail_tools.mailtm_list_messages
mailtm_get_message = mail_tools.mailtm_get_message
mailtm_delete_message = mail_tools.mailtm_delete_message
obter_recomendacoes = crypto_tools.obter_recomendacoes
validar_cripto = crypto_tools.validar_cripto

PEXELS_API_KEY = os.getenv('PEXELS_API_KEY', '').strip()
GIPHY_API_KEY = os.getenv('GIPHY_API_KEY', '').strip()

STEAM_API_KEY = os.getenv('STEAM_API_KEY')
STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"
steam_login_states = {}  

start_time = time.time()

palavras_racismo = set()
bot_voice_client = None
purge_mode = False
purge_expira = 0

gif_cache = {}  
img_cache = {}  

def carregar_resenha():
    if not os.path.exists(RESENHA_FILE):
        return {}
    with open(RESENHA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def salvar_resenha(resenha):
    with open(RESENHA_FILE, 'w', encoding='utf-8') as f:
        json.dump(resenha, f, indent=4, ensure_ascii=False)

def eh_video(filename):
    video_ext = ('.mp4', '.mov', '.avi', '.webm', '.mkv', '.flv', '.wmv')
    return filename.lower().endswith(video_ext)

def eh_gif(filename):
    return filename.lower().endswith('.gif')

def eh_imagem(filename):
    image_ext = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')
    return filename.lower().endswith(image_ext)

def extrair_id_tweet(url):
    if not url:
        return None
    match = re.search(r'(?:twitter\.com|x\.com)/(?:i/web|[^/]+)/status/(\d+)', url, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r'(?:twitter\.com|x\.com)/i/status/(\d+)', url, re.IGNORECASE)
    return match.group(1) if match else None

def coletar_variantes_video_twitter(payload):
    variantes = []

    def adicionar_variante(url, bitrate=None):
        if not url or '.mp4' not in url.lower():
            return
        bitrate_limpo = 0
        if isinstance(bitrate, (int, float)):
            bitrate_limpo = int(bitrate)
        elif isinstance(bitrate, str) and bitrate.isdigit():
            bitrate_limpo = int(bitrate)
        variantes.append({
            "url": url.replace("&amp;", "&"),
            "bitrate": bitrate_limpo
        })

    def percorrer(item):
        if isinstance(item, dict):
            variants = item.get("variants")
            if isinstance(variants, list):
                for variant in variants:
                    if not isinstance(variant, dict):
                        continue
                    url = variant.get("url")
                    content_type = variant.get("content_type", "")
                    if url and (not content_type or "video/mp4" in content_type):
                        adicionar_variante(url, variant.get("bitrate", 0))
            media_url = item.get("media_url_https") or item.get("media_url")
            if isinstance(media_url, str) and media_url.lower().endswith(".mp4"):
                adicionar_variante(media_url)
            for value in item.values():
                percorrer(value)
        elif isinstance(item, list):
            for value in item:
                percorrer(value)

    percorrer(payload)

    unicas = {}
    for variante in variantes:
        url = variante["url"]
        if url not in unicas or variante["bitrate"] > unicas[url]["bitrate"]:
            unicas[url] = variante
    return sorted(unicas.values(), key=lambda item: item["bitrate"], reverse=True)

async def obter_variantes_video_twitter(tweet_id):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/html"
    }
    urls_json = [
        f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&lang=pt",
        f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}"
    ]
    urls_html = [
        f"https://x.com/i/status/{tweet_id}",
        f"https://twitter.com/i/status/{tweet_id}"
    ]

    async with aiohttp.ClientSession(headers=headers) as session:
        for url in urls_json:
            try:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        continue
                    payload = await resp.json(content_type=None)
                    variantes = coletar_variantes_video_twitter(payload)
                    if variantes:
                        return variantes
            except Exception as e:
                pass
        for url in urls_html:
            try:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        continue
                    html = await resp.text()
                    matches = re.findall(r'https://video\.twimg\.com/[^"\'>\s]+', html, re.IGNORECASE)
                    if matches:
                        variantes = [{"url": m.replace("&amp;", "&"), "bitrate": 0} for m in matches if ".mp4" in m.lower()]
                        if variantes:
                            return variantes
            except Exception as e:
                pass
    return []

async def baixar_arquivo_por_url(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, timeout=30) as resp:
            if resp.status != 200:
                raise RuntimeError(f"download HTTP {resp.status}")
            return await resp.read()

async def buscar_giphy_aleatorio(termo):
    if not GIPHY_API_KEY:
        return None
    
    url = "https://api.giphy.com/v1/gifs/search"
    params = {
        "api_key": GIPHY_API_KEY,
        "q": termo,
        "limit": 50,
        "rating": "pg-13"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data["data"]:
                    ultimo = gif_cache.get(termo)
                    opcoes = [gif for gif in data["data"] if gif["images"]["original"]["url"] != ultimo]
                    if not opcoes:
                        opcoes = data["data"]
                    gif_escolhido = random.choice(opcoes)
                    url_gif = gif_escolhido["images"]["original"]["url"]
                    gif_cache[termo] = url_gif
                    return url_gif
    return None

async def buscar_pexels_aleatorio(termo):
    if not PEXELS_API_KEY:
        return None
    
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": termo, "per_page": 20}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data["photos"]:
                    ultimo = img_cache.get(termo)
                    opcoes = [foto["src"]["original"] for foto in data["photos"] if foto["src"]["original"] != ultimo]
                    if not opcoes:
                        opcoes = [foto["src"]["original"] for foto in data["photos"]]
                    if opcoes:
                        escolhida = random.choice(opcoes)
                        img_cache[termo] = escolhida
                        return escolhida
    return None

async def email_command(ctx, action: str = None, *args):
    
    if action is None:
        embed = discord.Embed(
            title="📧 Caixa interna",
            description="Troque mensagens internas sem sair do servidor.",
            color=discord.Color.blue()
        )
        embed.add_field(name="/email list", 
                       value="Lista seus emails (não lidos destacados).", 
                       inline=False)
        embed.add_field(name="/email read <id>", 
                       value="Lê um email específico (marca como lido).", 
                       inline=False)
        embed.add_field(name="/email send <@user> <assunto> <corpo>", 
                       value="Envia um email para outro usuário.", 
                       inline=False)
        embed.add_field(name="/email delete <id>", 
                       value="Exclui um email.", 
                       inline=False)
        embed.set_footer(text=f"Os emails expiram em {EMAILS_EXPIRATION_HOURS} horas.")
        await ctx.send(embed=embed)
        return

    if action == 'list':
        emails = listar_emails(ctx.author.id)
        if not emails:
            await ctx.send("📭 Nenhum email encontrado.")
            return
        embed = discord.Embed(
            title="📧 Sua caixa de entrada",
            description=f"Você tem {len(emails)} email(s):",
            color=discord.Color.green()
        )
        for i, e in enumerate(emails, 1):
            status = "🔴 NÃO LIDO" if not e.get("lido", False) else "✅ LIDO"
            remetente = bot.get_user(e["de"])
            remetente_nome = remetente.display_name if remetente else f"Usuário {e['de']}"
            embed.add_field(
                name=f"{i} - {e['assunto']}",
                value=f"De: {remetente_nome}\nID: `{e['id']}`\nData: {e['data'][:19]}\nStatus: {status}",
                inline=False
            )
        embed.set_footer(text="Use /email read <id> para ler um email.")
        await ctx.send(embed=embed)

    elif action == 'read':
        if not args:
            await ctx.send("❌ Use: `/email read <id>`")
            return
        email_id = args[0]
        email = ler_email(ctx.author.id, email_id)
        if not email:
            await ctx.send("❌ Email não encontrado.")
            return
        remetente = bot.get_user(email["de"])
        remetente_nome = remetente.display_name if remetente else f"Usuário {email['de']}"
        embed = discord.Embed(
            title=f"📧 Email de {remetente_nome}",
            description=f"**Assunto:** {email['assunto']}\n**Data:** {email['data']}\n**ID:** {email['id']}",
            color=discord.Color.purple()
        )
        corpo = email["corpo"]
        if len(corpo) > 1024:
            partes = [corpo[i:i+1024] for i in range(0, len(corpo), 1024)]
            embed.add_field(name="Conteúdo", value=partes[0], inline=False)
            await ctx.send(embed=embed)
            for parte in partes[1:]:
                await ctx.send(f"```{parte}```")
        else:
            embed.add_field(name="Conteúdo", value=corpo, inline=False)
            await ctx.send(embed=embed)

    elif action == 'send':
        if len(args) < 3:
            await ctx.send("❌ Use: `/email send <@user> <assunto> <corpo>`")
            return
        
        target = args[0]
        
        try:
            if target.isdigit():
                user_id = int(target)
                destinatario = bot.get_user(user_id)
            else:
                
                match = re.match(r'<@!?(\d+)>', target)
                if match:
                    user_id = int(match.group(1))
                    destinatario = bot.get_user(user_id)
                else:
                    destinatario = None
        except:
            destinatario = None

        if not destinatario:
            
            member = discord.utils.get(ctx.guild.members, name=target)
            if member:
                destinatario = member
            else:
                await ctx.send("❌ Usuário não encontrado.")
                return

        assunto = args[1]
        corpo = ' '.join(args[2:])
        if len(corpo) > 2000:
            await ctx.send("❌ O corpo do email excede 2000 caracteres.")
            return

        success, msg = enviar_email(ctx.author.id, destinatario.id, assunto, corpo)
        if success:
            await ctx.send(f"✅ Email enviado para {destinatario.mention}.")
        else:
            await ctx.send(f"❌ {msg}")

    elif action == 'delete':
        if not args:
            await ctx.send("❌ Use: `/email delete <id>`")
            return
        email_id = args[0]
        if excluir_email(ctx.author.id, email_id):
            await ctx.send("✅ Email excluído com sucesso.")
        else:
            await ctx.send("❌ Email não encontrado.")

    else:
        await ctx.send("❌ Ação inválida. Use `list`, `read`, `send` ou `delete`.")

async def criar_backup():
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        arquivos = [STATS_FILE, IMUNE_FILE, PUNIDOS_FILE, LIMITES_FILE, PURGE_FILE,
                    SORTEIO_FILE, SORTEIOS_ATIVOS_FILE, CONFIG_FILE, RESENHA_FILE]
        for arquivo in arquivos:
            if os.path.exists(arquivo):
                zipf.write(arquivo)
        if os.path.exists(UPLOADS_DIR):
            for root, dirs, files in os.walk(UPLOADS_DIR):
                for file in files:
                    caminho = os.path.join(root, file)
                    zipf.write(caminho)
        if os.path.exists(EMAILS_DIR):
            for root, dirs, files in os.walk(EMAILS_DIR):
                for file in files:
                    caminho = os.path.join(root, file)
                    zipf.write(caminho)
    zip_buffer.seek(0)
    return zip_buffer

async def restaurar_backup(zip_bytes):
    
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zipf:
            zipf.extractall('.')
        return True, None
    except Exception as e:
        return False, str(e)

async def ip_lookup(ip):
    
    url = f"http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,zip,lat,lon,isp,org,as,query"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get('status') == 'success':
                    return data, None
                else:
                    return None, data.get('message', 'Erro desconhecido')
            else:
                return None, f"Erro HTTP {resp.status}"
    return None, "Erro de conexão"

spam_cache = {}
SPAM_MAX_MSGS = 5
SPAM_INTERVAL = 5
SPAM_TIMEOUT = 60

def limpar_cache_antigo(guild_id, user_id):
    if guild_id not in spam_cache:
        return
    if user_id not in spam_cache[guild_id]:
        return
    agora = time.time()
    spam_cache[guild_id][user_id] = [
        (ts, mid) for ts, mid in spam_cache[guild_id][user_id]
        if agora - ts <= SPAM_INTERVAL
    ]

async def tratar_spam(guild_id, user_id, channel, message):
    if guild_id in spam_cache and user_id in spam_cache[guild_id]:
        for ts, mid in spam_cache[guild_id][user_id]:
            try:
                msg = await channel.fetch_message(mid)
                await msg.delete()
            except:
                pass
        spam_cache[guild_id][user_id] = []

    member = channel.guild.get_member(user_id)
    if member:
        try:
            await member.timeout(discord.utils.utcnow() + timedelta(seconds=SPAM_TIMEOUT), reason="Spam")
            pass
        except Exception as e:
            pass

async def enviar_log_webhook(embed: discord.Embed = None, content: str = None):
    if not WEBHOOK_URL:
        return
    try:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(WEBHOOK_URL, session=session)
            await webhook.send(content=content, embed=embed, username=BOT_NAME)
    except Exception as e:
        pass

def carregar_palavras():
    global palavras_racismo
    palavras_racismo.clear()
    os.makedirs('categorias', exist_ok=True)
    if not os.path.exists(CATEGORIA_ARQUIVO):
        with open(CATEGORIA_ARQUIVO, 'w', encoding='utf-8') as f:
            f.write('# Adicione uma palavra por linha\n')
        pass
        return
    try:
        with open(CATEGORIA_ARQUIVO, 'r', encoding='utf-8') as f:
            for linha in f:
                palavra = linha.strip().lower()
                if palavra and not palavra.startswith('#'):
                    palavras_racismo.add(palavra)
        pass
    except Exception as e:
        pass
def carregar_stats():
    if not os.path.exists(STATS_FILE):
        return {}
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def salvar_stats(stats):
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=4, ensure_ascii=False)

def incrementar_contagem(guild_id, user_id, incremento=1):
    stats = carregar_stats()
    guild_id = str(guild_id)
    user_id = str(user_id)
    if guild_id not in stats:
        stats[guild_id] = {}
    if user_id not in stats[guild_id]:
        stats[guild_id][user_id] = 0
    stats[guild_id][user_id] += incremento
    salvar_stats(stats)
    pass
def obter_contagem_usuario(guild_id, user_id):
    stats = carregar_stats()
    return stats.get(str(guild_id), {}).get(str(user_id), 0)

def obter_ranking(guild_id, limite=10):
    stats = carregar_stats().get(str(guild_id), {})
    ranking = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    return [(int(uid), cont) for uid, cont in ranking[:limite]]

def carregar_imunes():
    if not os.path.exists(IMUNE_FILE):
        return []
    try:
        with open(IMUNE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def salvar_imunes(imunes):
    with open(IMUNE_FILE, 'w', encoding='utf-8') as f:
        json.dump(imunes, f, indent=4)

def adicionar_imune(user_id):
    user_id = str(user_id)
    imunes = carregar_imunes()
    if user_id not in imunes:
        imunes.append(user_id)
        salvar_imunes(imunes)
        return True
    return False

def remover_imune(user_id):
    user_id = str(user_id)
    imunes = carregar_imunes()
    if user_id in imunes:
        imunes.remove(user_id)
        salvar_imunes(imunes)
        return True
    return False

def is_imune(user_id):
    return str(user_id) in carregar_imunes()

def carregar_punidos():
    if not os.path.exists(PUNIDOS_FILE):
        return {}
    try:
        with open(PUNIDOS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def salvar_punidos(punidos):
    with open(PUNIDOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(punidos, f, indent=4)

@tasks.loop(seconds=30)
async def verificar_punidos():
    punidos = carregar_punidos()
    agora = time.time()
    alterado = False
    for user_id, dados in list(punidos.items()):
        if dados["expira"] <= agora:
            guild = bot.get_guild(int(dados["guild"]))
            if guild:
                member = guild.get_member(int(user_id))
                if member:
                    cargos = [discord.Object(id=rid) for rid in dados["cargos"]]
                    try:
                        await member.add_roles(*cargos, reason="Fim da punição anti-raid")
                        pass
                        embed = discord.Embed(title="Cargos Restaurados", description=f"{member.mention} teve seus cargos restaurados (fim da punição).", color=discord.Color.green())
                        pass
                    except Exception as e:
                        pass
            del punidos[user_id]
            alterado = True
    if alterado:
        salvar_punidos(punidos)

@verificar_punidos.before_loop
async def before_verificar():
    await bot.wait_until_ready()

def carregar_limites():
    if not os.path.exists(LIMITES_FILE):
        return {}
    try:
        with open(LIMITES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def salvar_limites(limites):
    with open(LIMITES_FILE, 'w', encoding='utf-8') as f:
        json.dump(limites, f, indent=4)

def semana_atual():
    hoje = datetime.utcnow()
    dias_para_segunda = (hoje.weekday()) % 7
    inicio_semana = datetime(hoje.year, hoje.month, hoje.day, 0, 0, 0) - timedelta(days=dias_para_segunda)
    return int(inicio_semana.timestamp())

def verificar_limite(guild_id, user_id, tipo):
    limites = carregar_limites()
    guild_id = str(guild_id)
    user_id = str(user_id)
    semana = semana_atual()
    
    if guild_id not in limites:
        limites[guild_id] = {}
    if user_id not in limites[guild_id]:
        limites[guild_id][user_id] = {"bans": 0, "kicks": 0, "semana": semana}
    else:
        if limites[guild_id][user_id]["semana"] != semana:
            limites[guild_id][user_id] = {"bans": 0, "kicks": 0, "semana": semana}
    
    usados = limites[guild_id][user_id][tipo]
    limite_max = 2 if tipo == "bans" else 5
    pode_usar = usados < limite_max
    salvar_limites(limites)
    return pode_usar, usados, limite_max

def incrementar_limite(guild_id, user_id, tipo):
    limites = carregar_limites()
    guild_id = str(guild_id)
    user_id = str(user_id)
    semana = semana_atual()
    
    if guild_id not in limites:
        limites[guild_id] = {}
    if user_id not in limites[guild_id]:
        limites[guild_id][user_id] = {"bans": 0, "kicks": 0, "semana": semana}
    else:
        if limites[guild_id][user_id]["semana"] != semana:
            limites[guild_id][user_id] = {"bans": 0, "kicks": 0, "semana": semana}
    
    limites[guild_id][user_id][tipo] += 1
    salvar_limites(limites)
    pass
def obter_limites_usuario(guild_id, user_id):
    limites = carregar_limites()
    guild_id = str(guild_id)
    user_id = str(user_id)
    semana = semana_atual()
    
    if guild_id not in limites:
        return 0, 2, 0, 5
    if user_id not in limites[guild_id]:
        return 0, 2, 0, 5
    dados = limites[guild_id][user_id]
    if dados.get("semana", 0) != semana:
        return 0, 2, 0, 5
    return dados.get("bans", 0), 2, dados.get("kicks", 0), 5

def resetar_limite_usuario(guild_id, user_id):
    limites = carregar_limites()
    guild_id = str(guild_id)
    user_id = str(user_id)
    semana = semana_atual()
    
    if guild_id not in limites:
        limites[guild_id] = {}
    limites[guild_id][user_id] = {"bans": 0, "kicks": 0, "semana": semana}
    salvar_limites(limites)
    pass

def carregar_purge():
    global purge_mode, purge_expira
    if not os.path.exists(PURGE_FILE):
        purge_mode = False
        purge_expira = 0
        return
    try:
        with open(PURGE_FILE, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            purge_mode = dados.get("modo", False)
            purge_expira = dados.get("expira", 0)
    except Exception:
        purge_mode = False
        purge_expira = 0

def salvar_purge():
    with open(PURGE_FILE, 'w', encoding='utf-8') as f:
        json.dump({"modo": purge_mode, "expira": purge_expira}, f, indent=4)

@tasks.loop(seconds=10)
async def verificar_purge():
    global purge_mode, purge_expira
    if purge_mode and time.time() >= purge_expira:
        purge_mode = False
        purge_expira = 0
        salvar_purge()
        pass
@verificar_purge.before_loop
async def before_purge():
    await bot.wait_until_ready()

def carregar_participantes_sorteio():
    if not os.path.exists(SORTEIO_FILE):
        return []
    try:
        with open(SORTEIO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def carregar_sorteios_ativos():
    if not os.path.exists(SORTEIOS_ATIVOS_FILE):
        return []
    try:
        with open(SORTEIOS_ATIVOS_FILE, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            novos = [s for s in dados if "fim_inscricao" in s and "fim_sorteio" in s]
            if len(novos) != len(dados):
                salvar_sorteios_ativos(novos)
            return novos
    except Exception:
        return []

def salvar_sorteios_ativos(sorteios):
    with open(SORTEIOS_ATIVOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(sorteios, f, indent=4)

@tasks.loop(seconds=30)
async def verificar_sorteios():
    sorteios = carregar_sorteios_ativos()
    agora = time.time()
    novos_sorteios = []
    for sorteio in sorteios:
        if "fim_inscricao" not in sorteio or "fim_sorteio" not in sorteio:
            continue

        if sorteio["fim_inscricao"] <= agora < sorteio["fim_sorteio"]:
            guild = bot.get_guild(sorteio["guild_id"])
            if guild:
                channel = guild.get_channel(sorteio["channel_id"])
                if channel:
                    try:
                        msg = await channel.fetch_message(sorteio["message_id"])
                        if msg.components:
                            embed = msg.embeds[0]
                            desc = embed.description
                            linhas = desc.split('\n')
                            novas_linhas = []
                            for linha in linhas:
                                if "Inscrições até:" in linha:
                                    novas_linhas.append("**Inscrições encerradas!**")
                                else:
                                    novas_linhas.append(linha)
                            embed.description = '\n'.join(novas_linhas)
                            await msg.edit(embed=embed, view=None)
                    except Exception as e:
                        pass
            novos_sorteios.append(sorteio)

        elif sorteio["fim_sorteio"] <= agora:
            guild = bot.get_guild(sorteio["guild_id"])
            if guild:
                channel = guild.get_channel(sorteio["channel_id"])
                if channel:
                    try:
                        msg = await channel.fetch_message(sorteio["message_id"])
                        vencedor_id = random.choice(sorteio["vencedores_predefinidos"])
                        vencedor = guild.get_member(vencedor_id)
                        if vencedor:
                            vencedor_mention = vencedor.mention
                        else:
                            vencedor_mention = f"<@{vencedor_id}>"
                        embed = discord.Embed(
                            title="🎉 Sorteio finalizado!",
                            description=f"**Descrição:** {sorteio['descricao']}\n"
                                        f"**Total de participantes:** {len(sorteio['participantes_ids'])}\n"
                                        f"**Vencedor:** {vencedor_mention}",
                            color=discord.Color.green()
                        )
                        await msg.edit(embed=embed, view=None)
                        await channel.send(f"Parabéns {vencedor_mention}! Você venceu o sorteio: {sorteio['descricao']}")
                    except Exception as e:
                        pass
        else:
            novos_sorteios.append(sorteio)

    if len(novos_sorteios) != len(sorteios):
        salvar_sorteios_ativos(novos_sorteios)

@verificar_sorteios.before_loop
async def before_sorteios():
    await bot.wait_until_ready()

async def punir_admin(member: discord.Member, motivo: str, bot_user: discord.User = None):
    global purge_mode
    if purge_mode:
        pass
        return False

    if is_imune(member.id):
        pass
        return False

    if member.top_role >= member.guild.me.top_role:
        pass
        await member.guild.owner.send(f"⚠️ Tentativa de kick em {member.mention} falhou devido à hierarquia de cargos.")
        return False

    if not member.guild.me.guild_permissions.kick_members:
        pass
        return False

    try:
        await member.kick(reason=f"Anti-raid: {motivo}")
        pass
    except Exception as e:
        pass
        return False

    if bot_user:
        try:
            await member.guild.ban(bot_user, reason=f"Anti-raid: bot adicionado por {member} (já kickado)")
            pass
        except Exception as e:
            pass
    embed = discord.Embed(
        title="🚨 Anti-Raid - Usuário Kickado",
        description=f"**Usuário:** {member} (`{member.id}`)\n**Motivo:** {motivo}\n**Ação:** Kick",
        color=discord.Color.red()
    )
    pass
    return True

@bot.event
async def on_audit_log_entry_create(entry):
    if entry.action != discord.AuditLogAction.ban:
        return

    guild = entry.guild
    if purge_mode:
        return

    if entry.user.id == bot.user.id:
        return

    if is_imune(entry.user.id):
        return

    executor = guild.get_member(entry.user.id)
    if not executor:
        return

    vítima = entry.target
    if isinstance(vítima, discord.User):
        try:
            await guild.unban(vítima, reason="Ban manual não autorizado (anti-raid)")
            pass
        except Exception as e:
            pass
    await punir_admin(executor, "Ban manual não autorizado (anti-raid)")

async def atualizar_periodicamente():
    global ultima_analise, ultima_atualizacao
    while True:
        pass
        try:
            nova_analise = await obter_recomendacoes()
            if nova_analise:
                ultima_analise = nova_analise
                ultima_atualizacao = datetime.now()
                pass
            else:
                pass
        except Exception as e:
            pass
        await asyncio.sleep(config["intervalo_minutos"] * 60)

@bot.event
async def on_ready():
    pass
    try:
        await bot.tree.sync()
        pass
    except Exception as e:
        pass
    carregar_palavras()
    carregar_purge()
    verificar_punidos.start()
    verificar_purge.start()
    verificar_sorteios.start()
    bot.loop.create_task(atualizar_periodicamente())
    bot.loop.create_task(poll_real_email_notifications())
    pass
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    
    if message.guild is None:
        await bot.process_commands(message)
        return

    await bot.process_commands(message)

    
    guild_id = message.guild.id
    user_id = message.author.id
    channel = message.channel

    if guild_id not in spam_cache:
        spam_cache[guild_id] = {}
    if user_id not in spam_cache[guild_id]:
        spam_cache[guild_id][user_id] = []

    agora = time.time()
    spam_cache[guild_id][user_id].append((agora, message.id))

    limpar_cache_antigo(guild_id, user_id)

    if len(spam_cache[guild_id][user_id]) > SPAM_MAX_MSGS:
        await tratar_spam(guild_id, user_id, channel, message)
        spam_cache[guild_id][user_id] = []
        return

    
    if not palavras_racismo:
        return
    palavras = re.findall(r'\b\w+\b', message.content.lower())
    if not palavras:
        return
    count = sum(1 for p in palavras if p in palavras_racismo)
    if count > 0:
        pass
        incrementar_contagem(message.guild.id, message.author.id, count)

@bot.event
async def on_member_join(member):
    if not member.bot:
        return
    if purge_mode:
        return
    guild = member.guild
    try:
        async for entry in guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
            if entry.target.id == member.id:
                adder = entry.user
                if not is_imune(adder.id):
                    await punir_admin(adder, "Adicionou um bot (anti-raid)", bot_user=member)
                break
    except Exception as e:
        pass
@bot.event
async def on_guild_channel_delete(channel):
    if purge_mode:
        return
    guild = channel.guild
    try:
        async for entry in guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
            if entry.target.id == channel.id:
                deleter = entry.user
                if not is_imune(deleter.id):
                    try:
                        nome = channel.name
                        tipo = channel.type
                        categoria = channel.category
                        posicao = channel.position
                        overwrites = channel.overwrites

                        if tipo == discord.ChannelType.text:
                            novo_canal = await guild.create_text_channel(
                                name=nome,
                                category=categoria,
                                position=posicao,
                                overwrites=overwrites,
                                reason=f"Recriação automática (deletado por {deleter})"
                            )
                        elif tipo == discord.ChannelType.voice:
                            novo_canal = await guild.create_voice_channel(
                                name=nome,
                                category=categoria,
                                position=posicao,
                                overwrites=overwrites,
                                reason=f"Recriação automática (deletado por {deleter})"
                            )
                        else:
                            novo_canal = None

                        if novo_canal:
                            pass
                    except Exception as e:
                        pass
                    await punir_admin(deleter, "Deletou um canal (anti-raid)")
                break
    except Exception as e:
        pass

@bot.command(name='count')
async def count(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author
    contagem = obter_contagem_usuario(ctx.guild.id, member.id)
    embed = discord.Embed(
        title="📊 Contagem de Palavras Racistas",
        color=discord.Color.blue()
    )
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.add_field(name="Total", value=f"**{contagem}** ocorrência(s)", inline=False)
    embed.set_footer(text="Use /ranking para ver o ranking.")
    await ctx.send(embed=embed)

@bot.command(name='ranking')
async def ranking(ctx):
    ranking_data = obter_ranking(ctx.guild.id, limite=10)
    embed = discord.Embed(
        title="🏆 Ranking de Palavras Racistas",
        description="Top 10 usuários",
        color=discord.Color.red()
    )
    if not ranking_data:
        embed.add_field(name="Nenhum dado", value="Ainda não há registros.", inline=False)
    else:
        for i, (user_id, contagem) in enumerate(ranking_data, 1):
            user = ctx.guild.get_member(user_id)
            mention = user.mention if user else f"<@{user_id}>"
            embed.add_field(
                name=f"{i}º",
                value=f"{mention} – **{contagem}** ocorrência(s)",
                inline=False
            )
    await ctx.send(embed=embed)

@bot.command(name='serverinfo')
async def serverinfo(ctx):
    guild = ctx.guild
    total_membros = guild.member_count
    online = sum(1 for m in guild.members if m.status != discord.Status.offline)
    em_call = 0
    for voice in guild.voice_channels:
        em_call += len(voice.members)
    bots = sum(1 for m in guild.members if m.bot)
    embed = discord.Embed(
        title=f"📈 Estatísticas do Servidor {guild.name}",
        color=discord.Color.green()
    )
    embed.add_field(name="Total de Membros", value=str(total_membros), inline=True)
    embed.add_field(name="Online", value=str(online), inline=True)
    embed.add_field(name="Em Call", value=str(em_call), inline=True)
    embed.add_field(name="Bots", value=str(bots), inline=True)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await ctx.send(embed=embed)

@bot.command(name='uptime')
async def uptime(ctx):
    tempo = time.time() - start_time
    dias = int(tempo // 86400)
    horas = int((tempo % 86400) // 3600)
    minutos = int((tempo % 3600) // 60)
    segundos = int(tempo % 60)
    embed = discord.Embed(
        title=f"⏱ Tempo online do {BOT_NAME}",
        description=f"Estou online há **{dias}d {horas}h {minutos}m {segundos}s**",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping(ctx):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"**Latência:** {latency}ms",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='help')
async def help_public(ctx):
    embed = discord.Embed(
        title=f"📚 O que o {BOT_NAME} faz",
        description="Separei abaixo os comandos que fazem mais sentido no dia a dia.",
        color=discord.Color.blurple()
    )
    embed.add_field(name="/count [@usuário]", value="Mostra sua contagem ou de outro usuário.", inline=False)
    embed.add_field(name="/ranking", value="Exibe o ranking de palavras racistas.", inline=False)
    embed.add_field(name="/serverinfo", value="Estatísticas do servidor.", inline=False)
    embed.add_field(name="/uptime", value=f"Mostra há quanto tempo o {BOT_NAME} está rodando.", inline=False)
    embed.add_field(name="/ping", value=f"Mostra a latência atual do {BOT_NAME}.", inline=False)
    embed.add_field(name="/ajuda", value="Mostra esta mensagem.", inline=False)
    embed.add_field(name="/resenha", value="Exibe os itens da resenha.", inline=False)
    embed.add_field(name="/upload", value="Envia um arquivo e devolve o link direto.", inline=False)
    embed.add_field(name="/twittervideo <link>", value="Baixa um vídeo de tweet/post do X e envia o arquivo ou link.", inline=False)
    embed.add_field(name="/gif <termo>", value="Procura um GIF pelo termo informado.", inline=False)
    embed.add_field(name="/img <termo>", value="Procura uma imagem pelo termo informado.", inline=False)
    await ctx.send(embed=embed)

CRYPTOS_DISPONIVEIS = [
    "bitcoin", "ethereum", "ripple", "cardano", "solana",
    "dogecoin", "polkadot", "litecoin", "tron", "usd-coin",
    "tether", "binancecoin", "chainlink", "stellar", "monero",
    "ethereum-classic", "vechain", "tezos", "eos", "neo",
    "iota", "dash", "zcash", "decred", "ravencoin",
    "cosmos", "algorand", "avalanche-2", "polygon", "uniswap",
    "aave", "compound-ether", "maker", "sushi", "yearn-finance",
    "theta-token", "filecoin", "gala", "axie-infinity", "the-sandbox",
    "decentraland", "enjincoin", "basic-attention-token",
    "pancakeswap-token", "fantom", "near", "elrond-erd-2", "hedera-hashgraph"
]

class PaginatedCryptoSelect(View):
    def __init__(self, cryptos_disponiveis, selecionadas_atuais):
        super().__init__(timeout=180)
        self.cryptos_disponiveis = cryptos_disponiveis
        self.selecionadas_atuais = selecionadas_atuais
        self.page = 0
        self.items_por_pagina = 25
        self.max_page = (len(cryptos_disponiveis) - 1) // self.items_por_pagina
        self._update_items()

    def _update_items(self):
        self.clear_items()
        start = self.page * self.items_por_pagina
        end = min(start + self.items_por_pagina, len(self.cryptos_disponiveis))
        page_options = self.cryptos_disponiveis[start:end]

        options = []
        for crypto in page_options:
            default = crypto in self.selecionadas_atuais
            options.append(
                discord.SelectOption(
                    label=crypto.capitalize(),
                    value=crypto,
                    default=default,
                    emoji="✅" if default else "⬜"
                )
            )

        select = Select(
            placeholder=f"Página {self.page+1}/{self.max_page+1} - Selecione...",
            min_values=0,
            max_values=len(options),
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)

        if self.page > 0:
            btn_prev = Button(label="◀ Anterior", style=discord.ButtonStyle.secondary)
            btn_prev.callback = self.prev_page
            self.add_item(btn_prev)
        if self.page < self.max_page:
            btn_next = Button(label="Próxima ▶", style=discord.ButtonStyle.secondary)
            btn_next.callback = self.next_page
            self.add_item(btn_next)

        btn_confirm = Button(label="✅ Confirmar Seleção", style=discord.ButtonStyle.success)
        btn_confirm.callback = self.confirm_selection
        self.add_item(btn_confirm)

    async def select_callback(self, interaction: discord.Interaction):
        self.selecionadas_atuais = self.select.values
        await interaction.response.defer()

    async def prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        self._update_items()
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self._update_items()
        await interaction.response.edit_message(view=self)

    async def confirm_selection(self, interaction: discord.Interaction):
        config["cryptos"] = self.selecionadas_atuais
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

        embed = discord.Embed(
            title="✅ Lista atualizada",
            description=f"Moedas monitoradas: {', '.join(self.selecionadas_atuais)}",
            color=0x00ff00
        )
        await interaction.response.edit_message(embed=embed, view=None)

@bot.command(name='menu')
async def menu_principal(ctx):
    embed = discord.Embed(
        title=f"🪙 Central de cripto do {BOT_NAME}",
        description="Escolha como quer acompanhar o mercado agora.",
        color=0x3498db
    )
    view = View()
    btn_invest = Button(label="📊 Ver Recomendações", style=discord.ButtonStyle.primary, emoji="📈")
    btn_config = Button(label="⚙️ Configurar Moedas", style=discord.ButtonStyle.secondary, emoji="🪙")
    btn_status = Button(label="ℹ️ Status Cripto", style=discord.ButtonStyle.success, emoji="🤖")

    async def invest_callback(interaction):
        if not ultima_analise:
            await interaction.response.send_message("⏳ Ainda estou juntando a primeira leitura do mercado...", ephemeral=True)
            return
        embed = discord.Embed(
            title="📊 Recomendações de Investimento",
            color=0x00ff00,
            timestamp=ultima_atualizacao or datetime.now()
        )
        for crypto, dados in list(ultima_analise.items())[:10]:
            embed.add_field(
                name=f"{crypto.upper()}",
                value=(
                    f"💰 Preço: ${dados['preco']:.2f}\n"
                    f"📈 Variação 24h: {dados['variacao']:.2f}%\n"
                    f"💡 {dados['recomendacao']}"
                ),
                inline=True
            )
        embed.set_footer(text=f"Atualizado a cada {config['intervalo_minutos']} minutos")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def config_callback(interaction):
        view = PaginatedCryptoSelect(CRYPTOS_DISPONIVEIS, config["cryptos"])
        embed = discord.Embed(
            title="🪙 Configurar Moedas Monitoradas",
            description="Navegue pelas páginas e selecione as moedas desejadas. Confirme ao final.",
            color=0xf1c40f
        )
        embed.add_field(name="Atuais", value=", ".join(config["cryptos"]) or "Nenhuma", inline=False)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def status_callback(interaction):
        embed = discord.Embed(title="ℹ️ Status Cripto", color=0x3498db)
        embed.add_field(name="Moedas monitoradas", value=len(config["cryptos"]), inline=True)
        embed.add_field(name="Lista", value=", ".join(config["cryptos"][:5]) + ("..." if len(config["cryptos"]) > 5 else ""), inline=True)
        embed.add_field(name="Intervalo", value=f"{config['intervalo_minutos']} min", inline=True)
        embed.add_field(name="Limite", value=f"${config['limite_investimento']}", inline=True)
        embed.add_field(name="API Principal", value=config["api_priority"][0], inline=True)
        if ultima_atualizacao:
            embed.add_field(name="Última atualização", value=f"<t:{int(ultima_atualizacao.timestamp())}:R>", inline=False)
        else:
            embed.add_field(name="Última atualização", value="Nunca", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    btn_invest.callback = invest_callback
    btn_config.callback = config_callback
    btn_status.callback = status_callback

    view.add_item(btn_invest)
    view.add_item(btn_config)
    view.add_item(btn_status)

    await ctx.send(embed=embed, view=view)

@bot.command(name='invest')
async def invest_simples(ctx):
    if not ultima_analise:
        await ctx.send("⏳ Ainda estou juntando a primeira leitura do mercado...")
        return
    embed = discord.Embed(
        title="📊 Recomendações de Investimento",
        color=0x00ff00,
        timestamp=ultima_atualizacao or datetime.now()
    )
    for crypto, dados in list(ultima_analise.items())[:10]:
        embed.add_field(
            name=f"{crypto.upper()}",
            value=(
                f"💰 Preço: ${dados['preco']:.2f}\n"
                f"📈 Variação 24h: {dados['variacao']:.2f}%\n"
                f"💡 {dados['recomendacao']}"
            ),
            inline=True
        )
    embed.set_footer(text=f"Atualizado a cada {config['intervalo_minutos']} minutos")
    await ctx.send(embed=embed)

@bot.command(name='cripto')
async def adicionar_cripto(ctx, *, nome: str):
    nome = nome.strip().lower()
    if nome in config["cryptos"]:
        await ctx.send(f"⚠️ `{nome}` já está na lista.")
        return
    valido = await validar_cripto(nome)
    if not valido:
        await ctx.send(f"❌ Não foi possível validar `{nome}`. Verifique o nome.")
        return
    config["cryptos"].append(nome)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    await ctx.send(f"✅ `{nome}` adicionada! Use `/menu` para ver as opções.")

@bot.command(name='remover')
async def remover_cripto(ctx, *, nome: str):
    nome = nome.strip().lower()
    if nome not in config["cryptos"]:
        await ctx.send(f"⚠️ `{nome}` não está na lista.")
        return
    config["cryptos"].remove(nome)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    await ctx.send(f"✅ `{nome}` removida.")

@bot.command(name='intervalo')
async def alterar_intervalo(ctx, minutos: int):
    if minutos < 1:
        await ctx.send("❌ Intervalo mínimo: 1 minuto.")
        return
    config["intervalo_minutos"] = minutos
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    await ctx.send(f"⏱️ Intervalo alterado para {minutos} minutos.")

@bot.command(name='limite')
async def alterar_limite(ctx, valor: float):
    if valor <= 0:
        await ctx.send("❌ Valor deve ser positivo.")
        return
    config["limite_investimento"] = valor
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    await ctx.send(f"💰 Limite alterado para ${valor:.2f}")

@bot.command(name='upload')
async def upload_publico(ctx):
    
    if not ctx.message.attachments:
        await ctx.send("❌ Você precisa anexar um arquivo para fazer upload.")
        return

    attachment = ctx.message.attachments[0]
    filename = attachment.filename
    file_size = attachment.size

    if file_size > 200 * 1024 * 1024:
        await ctx.send("❌ Arquivo muito grande. O limite é 200 MB.")
        return

    await ctx.send("⏳ Fazendo upload para o Catbox...")

    try:
        arquivo_bytes = await attachment.read()
        url = await upload_para_catbox(arquivo_bytes, filename)

        if url:
            salvar_metadados(ctx.author.id, filename, url)
            
            if eh_video(filename):
                tipo = "🎬 Vídeo"
            elif eh_gif(filename):
                tipo = "🎞️ GIF"
            elif eh_imagem(filename):
                tipo = "🖼️ Imagem"
            else:
                tipo = "📁 Arquivo"
            
            embed = discord.Embed(
                title="✅ Upload realizado!",
                description=f"**Arquivo:** {filename}\n**Tipo:** {tipo}\n**Link:** {url}",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Erro ao fazer upload. Tente novamente mais tarde.")
    except Exception as e:
        pass
        await ctx.send(f"❌ Erro: {e}")

@bot.command(name='uploadc')
async def upload_para_resenha(ctx):
    
    if not is_imune(ctx.author.id):
        await ctx.send("❌ Você não tem permissão para usar este comando. Apenas usuários imunes podem adicionar à resenha.")
        return

    if not ctx.message.attachments:
        await ctx.send("❌ Você precisa anexar um arquivo para fazer upload para a resenha.")
        return

    attachment = ctx.message.attachments[0]
    filename = attachment.filename
    file_size = attachment.size

    if file_size > 200 * 1024 * 1024:
        await ctx.send("❌ Arquivo muito grande. O limite é 200 MB.")
        return

    await ctx.send("⏳ Fazendo upload para o Catbox...")

    async def perguntar_categoria():
        await ctx.send("Digite o nome da categoria para este item:")
        try:
            msg = await bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=30)
            return msg.content.strip()
        except asyncio.TimeoutError:
            await ctx.send("Tempo esgotado. Operação cancelada.")
            return None

    try:
        arquivo_bytes = await attachment.read()
        url = await upload_para_catbox(arquivo_bytes, filename)

        if url:
            salvar_metadados(ctx.author.id, filename, url)
            
            if eh_video(filename):
                tipo = "🎬 Vídeo"
            elif eh_gif(filename):
                tipo = "🎞️ GIF"
            elif eh_imagem(filename):
                tipo = "🖼️ Imagem"
            else:
                tipo = "📁 Arquivo"

            categoria = await perguntar_categoria()
            if categoria:
                resenha = carregar_resenha()
                if categoria not in resenha:
                    resenha[categoria] = []
                resenha[categoria].append(url)
                salvar_resenha(resenha)
                embed = discord.Embed(
                    title="✅ Adicionado à resenha!",
                    description=f"**Arquivo:** {filename}\n**Tipo:** {tipo}\n**Categoria:** {categoria}\n**Link:** {url}",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Categoria não fornecida. Item não adicionado à resenha.")
        else:
            await ctx.send("❌ Erro ao fazer upload. Tente novamente mais tarde.")
    except Exception as e:
        pass
        await ctx.send(f"❌ Erro: {e}")

@bot.command(name='meusarquivos')
async def meus_arquivos(ctx):
    arquivos = carregar_metadados(ctx.author.id)
    if not arquivos:
        await ctx.send("📭 Você ainda não fez nenhum upload.")
        return

    try:
        dm = await ctx.author.create_dm()
        for i in range(0, len(arquivos), 5):
            embed = discord.Embed(
                title=f"Seus Uploads (página {i//5 + 1})",
                color=discord.Color.blue()
            )
            for arq in arquivos[i:i+5]:
                embed.add_field(
                    name=arq["nome"],
                    value=f"URL: {arq['url']}\nData: {arq['data'][:10]}",
                    inline=False
                )
            await dm.send(embed=embed)
        await ctx.send("✅ Lista enviada no seu DM.")
    except discord.Forbidden:
        await ctx.send("❌ Não consegui enviar DM. Verifique se você permite mensagens de estranhos.")

@bot.command(name='gif')
async def gif_command(ctx, *, termo: str):
    
    if not termo:
        await ctx.send("❌ Use: `/gif <termo de busca>`")
        return

    await ctx.send(f"🎞️ Buscando GIF para '{termo}'...")
    url = await buscar_giphy_aleatorio(termo)
    if url:
        embed = discord.Embed(title=f"🎞️ GIF: {termo}", color=discord.Color.green())
        embed.set_image(url=url)
        embed.set_footer(text="Powered by GIPHY")
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Nenhum GIF encontrado para '{termo}'. Tente outro termo.")

@bot.command(name='img', aliases=['imagem', 'image'])
async def image_command(ctx, *, termo: str):
    
    if not termo:
        await ctx.send("❌ Use: `/img <termo de busca>`")
        return

    await ctx.send(f"🖼️ Buscando imagem para '{termo}'...")
    url = await buscar_pexels_aleatorio(termo)
    if url:
        embed = discord.Embed(title=f"🖼️ Imagem: {termo}", color=discord.Color.blue())
        embed.set_image(url=url)
        embed.set_footer(text="Powered by Pexels")
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Nenhuma imagem encontrada para '{termo}'. Tente outro termo.")

@bot.command(name='twittervideo', aliases=['twvideo', 'xvideo'])
async def twitter_video_command(ctx, url: str = None):
    
    if not url:
        await ctx.send("❌ Use: `/twittervideo <link do tweet/post>`")
        return

    tweet_id = extrair_id_tweet(url)
    if not tweet_id:
        await ctx.send("❌ Link inválido. Envie uma URL de tweet/post do Twitter/X.")
        return

    await ctx.send("⏳ Localizando o vídeo do tweet...")

    try:
        variantes = await obter_variantes_video_twitter(tweet_id)
        if not variantes:
            await ctx.send("❌ Não encontrei um vídeo nesse tweet/post ou o X bloqueou a captura.")
            return

        melhor = variantes[0]
        video_bytes = await baixar_arquivo_por_url(melhor["url"])
        tamanho = len(video_bytes)

        if tamanho > 200 * 1024 * 1024:
            await ctx.send("❌ O vídeo excede o limite de 200 MB.")
            return

        nome_arquivo = f"twitter_{tweet_id}.mp4"
        salvar_metadados(ctx.author.id, nome_arquivo, melhor["url"])

        if tamanho > 25 * 1024 * 1024:
            await ctx.send("⏳ Vídeo acima do limite do Discord, enviando para o Catbox...")
            url_catbox = await upload_para_catbox(video_bytes, nome_arquivo)
            if not url_catbox:
                await ctx.send("❌ Falhei ao enviar o vídeo para o Catbox.")
                return

            embed = discord.Embed(
                title="✅ Vídeo do Twitter/X baixado",
                description=f"**Tweet ID:** {tweet_id}\n**Tamanho:** {tamanho / (1024 * 1024):.2f} MB\n**Link:** {url_catbox}",
                color=discord.Color.green()
            )
            if melhor["bitrate"]:
                embed.set_footer(text=f"Bitrate detectado: {melhor['bitrate']} kbps")
            await ctx.send(embed=embed)
            return

        arquivo = discord.File(io.BytesIO(video_bytes), filename=nome_arquivo)
        embed = discord.Embed(
            title="✅ Vídeo do Twitter/X baixado",
            description=f"**Tweet ID:** {tweet_id}\n**Tamanho:** {tamanho / (1024 * 1024):.2f} MB",
            color=discord.Color.green()
        )
        if melhor["bitrate"]:
            embed.set_footer(text=f"Bitrate detectado: {melhor['bitrate']} kbps")
        await ctx.send(embed=embed, file=arquivo)
    except Exception as e:
        pass
        await ctx.send(f"❌ Erro ao baixar o vídeo: {e}")

@bot.command(name='resenha')
async def resenha(ctx):
    
    resenha = carregar_resenha()
    if not resenha:
        await ctx.send("📭 Nenhum item cadastrado na resenha ainda.")
        return

    class ResenhaView(View):
        def __init__(self):
            super().__init__(timeout=60)
            options = [discord.SelectOption(label=cat, value=cat) for cat in resenha.keys()]
            select = Select(placeholder="Escolha uma categoria", options=options)
            select.callback = self.select_callback
            self.add_item(select)

        async def select_callback(self, interaction: discord.Interaction):
            categoria = interaction.data['values'][0]
            urls = resenha[categoria]
            if not urls:
                await interaction.response.send_message(f"Nenhum item na categoria '{categoria}'.", ephemeral=True)
                return
            page = 0
            total = len(urls)

            class PaginationView(View):
                def __init__(self):
                    super().__init__(timeout=60)
                    self.page = page
                    self.urls = urls

                async def update(self, interaction):
                    embed = discord.Embed(
                        title=f"🎬 Resenha - {categoria}",
                        description=f"Item {self.page+1}/{total}\n{self.urls[self.page]}",
                        color=discord.Color.purple()
                    )
                    await interaction.response.edit_message(embed=embed, view=self)

                @discord.ui.button(label="◀ Anterior", style=discord.ButtonStyle.secondary)
                async def prev(self, interaction: discord.Interaction, button: Button):
                    if self.page > 0:
                        self.page -= 1
                        await self.update(interaction)
                    else:
                        await interaction.response.send_message("Primeiro item.", ephemeral=True)

                @discord.ui.button(label="Próxima ▶", style=discord.ButtonStyle.secondary)
                async def next(self, interaction: discord.Interaction, button: Button):
                    if self.page < total - 1:
                        self.page += 1
                        await self.update(interaction)
                    else:
                        await interaction.response.send_message("Último item.", ephemeral=True)

            pag_view = PaginationView()
            embed = discord.Embed(
                title=f"🎬 Resenha - {categoria}",
                description=f"Item 1/{total}\n{urls[0]}",
                color=discord.Color.purple()
            )
            await interaction.response.send_message(embed=embed, view=pag_view, ephemeral=True)

    view = ResenhaView()
    await ctx.send("Selecione uma categoria:", view=view)

@bot.command(name='connect')
@commands.has_permissions(administrator=True)
async def connect(ctx, channel_id: int):
    global bot_voice_client
    if bot_voice_client and bot_voice_client.is_connected():
        await ctx.send("❌ O navigatebot já está em um canal de voz. Use /disconnect antes de tentar de novo.")
        return
    channel = bot.get_channel(channel_id)
    if not channel or not isinstance(channel, discord.VoiceChannel):
        await ctx.send("❌ ID de canal de voz inválido.")
        return
    try:
        bot_voice_client = await channel.connect()
        await bot_voice_client.guild.change_voice_state(
            channel=channel,
            self_mute=True,
            self_deaf=False
        )
        await ctx.send(f"✅ Conectado ao canal **{channel.name}** e mutado.")
        pass
    except Exception as e:
        await ctx.send(f"❌ Erro ao conectar: {e}")

@bot.command(name='disconnect')
@commands.has_permissions(administrator=True)
async def disconnect(ctx):
    global bot_voice_client
    if bot_voice_client and bot_voice_client.is_connected():
        await bot_voice_client.disconnect()
        bot_voice_client = None
        await ctx.send("✅ O navigatebot saiu do canal de voz.")
        pass
    else:
        await ctx.send("❌ O navigatebot não está conectado a nenhum canal de voz.")

@bot.command(name='setrole')
@commands.has_permissions(administrator=True)
async def setrole(ctx, role: discord.Role, member: discord.Member):
    try:
        await member.add_roles(role, reason=f"Comando /setrole por {ctx.author}")
        await ctx.send(f"✅ Cargo {role.mention} atribuído a {member.mention}.")
        pass
    except Exception as e:
        await ctx.send(f"❌ Erro ao atribuir cargo: {e}")

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, user_id: int, *, motivo="Não especificado"):
    pode, usados, limite = verificar_limite(ctx.guild.id, ctx.author.id, "bans")
    if not pode:
        await ctx.send(f"❌ Você já usou seus {limite} bans desta semana. Limite atingido.")
        return

    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.ban(user, reason=f"{motivo} (por {ctx.author})")
        incrementar_limite(ctx.guild.id, ctx.author.id, "bans")
        await ctx.send(f"✅ Usuário {user} (ID: {user_id}) foi banido. Motivo: {motivo}")
        pass
    except Exception as e:
        await ctx.send(f"❌ Erro ao banir: {e}")

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, motivo="Não especificado"):
    pode, usados, limite = verificar_limite(ctx.guild.id, ctx.author.id, "kicks")
    if not pode:
        await ctx.send(f"❌ Você já usou seus {limite} kicks desta semana. Limite atingido.")
        return

    try:
        await member.kick(reason=f"{motivo} (por {ctx.author})")
        incrementar_limite(ctx.guild.id, ctx.author.id, "kicks")
        await ctx.send(f"✅ {member.mention} foi expulso. Motivo: {motivo}")
        pass
    except Exception as e:
        await ctx.send(f"❌ Erro ao expulsar: {e}")

@bot.command(name='unban')
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        await ctx.send(f"✅ Usuário {user} (ID: {user_id}) foi desbanido.")
        pass
    except Exception as e:
        await ctx.send(f"❌ Erro ao desbanir: {e}")

@bot.command(name='restart')
@commands.has_permissions(administrator=True)
async def restart(ctx):
    embed = discord.Embed(
        title=f"🔄 Reiniciar o {BOT_NAME}?",
        description=f"Confirma a reinicialização do {BOT_NAME}?",
        color=discord.Color.orange()
    )
    class Confirm(View):
        def __init__(self):
            super().__init__(timeout=30)
        @discord.ui.button(label="Sim", style=discord.ButtonStyle.green)
        async def confirm(self, interaction: discord.Interaction, button: Button):
            if interaction.user != ctx.author:
                await interaction.response.send_message("Apenas o autor do comando pode confirmar.", ephemeral=True)
                return
            await interaction.response.edit_message(content="🔄 Reiniciando...", view=None, embed=None)
            pass
            await bot.close()
        @discord.ui.button(label="Não", style=discord.ButtonStyle.red)
        async def cancel(self, interaction: discord.Interaction, button: Button):
            if interaction.user != ctx.author:
                await interaction.response.send_message("Apenas o autor do comando pode cancelar.", ephemeral=True)
                return
            await interaction.response.edit_message(content="❌ Reinicialização cancelada.", view=None, embed=None)
    await ctx.send(embed=embed, view=Confirm())

@bot.command(name='recarregar')
@commands.has_permissions(administrator=True)
async def recarregar(ctx):
    carregar_palavras()
    await ctx.send("✅ Lista de palavras recarregada.")
    pass
@bot.command(name='nuke')
@commands.has_permissions(administrator=True)
async def nuke(ctx):
    channel = ctx.channel
    if not isinstance(channel, discord.TextChannel):
        await ctx.send("❌ Este comando só pode ser usado em canais de texto.")
        return

    embed = discord.Embed(
        title="💣 Nuke no Canal",
        description=f"Tem certeza que deseja **nukar** o canal {channel.mention}?\n"
                    "Isso irá apagá-lo e recriá-lo com as mesmas configurações (nome, categoria, permissões).",
        color=discord.Color.red()
    )
    class NukeConfirm(View):
        def __init__(self):
            super().__init__(timeout=30)
        @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: Button):
            if interaction.user != ctx.author:
                await interaction.response.send_message("Apenas o autor do comando pode confirmar.", ephemeral=True)
                return
            await interaction.response.edit_message(content="💥 Nukando...", view=None, embed=None)
            try:
                nome = channel.name
                categoria = channel.category
                posicao = channel.position
                overwrites = channel.overwrites
                topic = channel.topic
                slowmode_delay = channel.slowmode_delay
                nsfw = channel.nsfw

                await channel.delete()
                novo_canal = await ctx.guild.create_text_channel(
                    name=nome,
                    category=categoria,
                    position=posicao,
                    overwrites=overwrites,
                    topic=topic,
                    slowmode_delay=slowmode_delay,
                    nsfw=nsfw,
                    reason=f"Nuke por {ctx.author}"
                )
                await novo_canal.send("✅ Canal recriado com sucesso!")
                pass
            except Exception as e:
                await ctx.author.send(f"❌ Erro ao nukar o canal: {e}")
        @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: Button):
            if interaction.user != ctx.author:
                await interaction.response.send_message("Apenas o autor do comando pode cancelar.", ephemeral=True)
                return
            await interaction.response.edit_message(content="❌ Nuke cancelado.", view=None, embed=None)

    await ctx.send(embed=embed, view=NukeConfirm())

@bot.command(name='tt')
@commands.has_permissions(administrator=True)
async def tt(ctx, target=None):
    if target is None:
        user_id = ctx.author.id
        bans_usados, bans_limite, kicks_usados, kicks_limite = obter_limites_usuario(ctx.guild.id, user_id)
        member = ctx.author
        nome = member.mention
        embed = discord.Embed(
            title="📊 Limites Semanais",
            description=f"Usuário: {nome}",
            color=discord.Color.purple()
        )
        embed.add_field(name="Bans", value=f"{bans_usados}/{bans_limite}", inline=True)
        embed.add_field(name="Kicks", value=f"{kicks_usados}/{kicks_limite}", inline=True)
        await ctx.send(embed=embed)
        return

    role = None
    try:
        role = await commands.RoleConverter().convert(ctx, target)
    except commands.RoleNotFound:
        pass

    if role is not None:
        membros = role.members
        if not membros:
            await ctx.send(f"ℹ️ Nenhum membro com o cargo {role.mention}.")
            return

        mostrar = membros[:10]
        total = len(membros)
        desc = f"Mostrando limites de {len(mostrar)} membros do cargo {role.mention}"
        if total > 10:
            desc += f" (total {total}, exibindo apenas os primeiros 10)"

        embed = discord.Embed(
            title="📊 Limites Semanais por Cargo",
            description=desc,
            color=role.color if role.color.value != 0 else discord.Color.purple()
        )
        for member in mostrar:
            bans_usados, bans_limite, kicks_usados, kicks_limite = obter_limites_usuario(ctx.guild.id, member.id)
            embed.add_field(
                name=member.display_name,
                value=f"Bans: {bans_usados}/{bans_limite} | Kicks: {kicks_usados}/{kicks_limite}",
                inline=False
            )
        await ctx.send(embed=embed)
        return

    try:
        member = await commands.MemberConverter().convert(ctx, target)
        user_id = member.id
        nome = member.mention
    except commands.MemberNotFound:
        try:
            user_id = int(target)
            member = ctx.guild.get_member(user_id)
            nome = member.mention if member else f"ID: {user_id}"
        except ValueError:
            await ctx.send("❌ Argumento inválido. Use um ID de usuário, menção de usuário ou menção de cargo.")
            return

    bans_usados, bans_limite, kicks_usados, kicks_limite = obter_limites_usuario(ctx.guild.id, user_id)
    embed = discord.Embed(
        title="📊 Limites Semanais",
        description=f"Usuário: {nome}",
        color=discord.Color.purple()
    )
    embed.add_field(name="Bans", value=f"{bans_usados}/{bans_limite}", inline=True)
    embed.add_field(name="Kicks", value=f"{kicks_usados}/{kicks_limite}", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='resetlimit')
async def resetlimit(ctx, user_id: int):
    if not is_imune(ctx.author.id):
        await ctx.send("❌ Você não tem permissão para usar este comando.")
        return

    resetar_limite_usuario(ctx.guild.id, user_id)

    member = ctx.guild.get_member(user_id)
    nome = member.mention if member else f"ID: {user_id}"

    await ctx.send(f"✅ Limites de bans/kicks resetados para {nome}.")
    pass
def parse_tempo(tempo_str: str) -> int:
    tempo_str = tempo_str.strip()
    if tempo_str[-1].isdigit():
        return int(tempo_str)
    unidade = tempo_str[-1].lower()
    valor = int(tempo_str[:-1])
    if unidade == 's':
        return valor
    elif unidade == 'm':
        return valor * 60
    elif unidade == 'h':
        return valor * 3600
    elif unidade == 'd':
        return valor * 86400
    else:
        raise ValueError("Unidade inválida. Use s, m, h ou d.")

@bot.command(name='purge')
async def purge(ctx, tempo: str):
    if not (await bot.is_owner(ctx.author) or is_imune(ctx.author.id)):
        await ctx.send("❌ Você não tem permissão para usar este comando.")
        return

    global purge_mode, purge_expira
    if purge_mode:
        await ctx.send("⚠️ Modo purge já está ativo. Use /unpurge para desativar.")
        return

    try:
        segundos = parse_tempo(tempo)
    except ValueError as e:
        await ctx.send(f"❌ {e}")
        return

    purge_mode = True
    purge_expira = time.time() + segundos
    salvar_purge()
    await ctx.send(f"🛡️ Modo purge ativado por {tempo}. Sistemas de defesa desativados.")
    pass
@bot.command(name='unpurge')
@commands.is_owner()
async def unpurge(ctx):
    global purge_mode, purge_expira
    if not purge_mode:
        await ctx.send("⚠️ Modo purge não está ativo.")
        return
    purge_mode = False
    purge_expira = 0
    salvar_purge()
    await ctx.send("🛡️ Modo purge desativado. Sistemas de defesa reativados.")
    pass
@bot.command(name='sorteio')
@commands.has_permissions(administrator=True)
async def sorteio(ctx, tempo_inscricao: str, tempo_sorteio: str, *, descricao: str):
    try:
        seg_inscricao = parse_tempo(tempo_inscricao)
        seg_sorteio = parse_tempo(tempo_sorteio)
    except ValueError as e:
        await ctx.send(f"❌ {e}")
        return

    participantes_predefinidos = carregar_participantes_sorteio()
    if not participantes_predefinidos:
        await ctx.send("❌ Não há participantes cadastrados no arquivo `sorteio.json`.")
        return

    participantes_predefinidos_ids = [int(pid) for pid in participantes_predefinidos]

    fim_inscricao = time.time() + seg_inscricao
    fim_sorteio = fim_inscricao + seg_sorteio

    embed = discord.Embed(
        title="🎉 Sorteio!",
        description=f"**Descrição:** {descricao}\n\n"
                    f"**Inscrições até:** <t:{int(fim_inscricao)}:R>\n"
                    f"**Resultado em:** <t:{int(fim_sorteio)}:R>\n"
                    f"**Participantes:** 0",
        color=discord.Color.gold()
    )

    class SorteioView(View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="🎉 Participar", style=discord.ButtonStyle.primary)
        async def participar(self, interaction: discord.Interaction, button: Button):
            sorteios = carregar_sorteios_ativos()
            for s in sorteios:
                if s["message_id"] == interaction.message.id:
                    if time.time() > s["fim_inscricao"]:
                        await interaction.response.send_message("⏰ As inscrições já encerraram.", ephemeral=True)
                        return
                    if interaction.user.id not in s["participantes_ids"]:
                        s["participantes_ids"].append(interaction.user.id)
                        salvar_sorteios_ativos(sorteios)
                        embed = interaction.message.embeds[0]
                        embed.description = embed.description.replace(
                            f"**Participantes:** {len(s['participantes_ids'])-1}",
                            f"**Participantes:** {len(s['participantes_ids'])}"
                        )
                        await interaction.message.edit(embed=embed)
                        await interaction.response.send_message("✅ Você entrou no sorteio!", ephemeral=True)
                    else:
                        await interaction.response.send_message("Você já está participando.", ephemeral=True)
                    return
            await interaction.response.send_message("Sorteio não encontrado.", ephemeral=True)

    view = SorteioView()
    msg = await ctx.send(embed=embed, view=view)

    sorteios = carregar_sorteios_ativos()
    sorteios.append({
        "guild_id": ctx.guild.id,
        "channel_id": ctx.channel.id,
        "message_id": msg.id,
        "descricao": descricao,
        "fim_inscricao": fim_inscricao,
        "fim_sorteio": fim_sorteio,
        "participantes_ids": [],
        "vencedores_predefinidos": participantes_predefinidos_ids
    })
    salvar_sorteios_ativos(sorteios)

    pass
@bot.command(name='padd')
@commands.is_owner()
async def padd(ctx, user_id: int):
    if adicionar_imune(user_id):
        await ctx.send(f"✅ Usuário ID `{user_id}` adicionado à lista de imunes.")
        pass
    else:
        await ctx.send(f"ℹ️ Usuário ID `{user_id}` já está na lista de imunes.")

@bot.command(name='remove')
@commands.is_owner()
async def remove_imune(ctx, user_id: int):
    if remover_imune(user_id):
        await ctx.send(f"✅ Usuário ID `{user_id}` removido da lista de imunes.")
        pass
    else:
        await ctx.send(f"ℹ️ Usuário ID `{user_id}` não estava na lista de imunes.")

@bot.command(name='helpadm')
@commands.has_permissions(administrator=True)
async def help_admin(ctx):
    embed = discord.Embed(
        title=f"🛠 Administração do {BOT_NAME}",
        description="Esses atalhos ficam disponíveis só para quem administra o servidor.",
        color=discord.Color.dark_red()
    )
    embed.add_field(name="/connect <id_canal>", value="Faz o bot entrar em uma call (mutado).", inline=False)
    embed.add_field(name="/disconnect", value="Desconecta o bot da call.", inline=False)
    embed.add_field(name="/setrole @cargo @membro", value="Atribui um cargo.", inline=False)
    embed.add_field(name="/ban <user_id> [motivo]", value="Bane um usuário (limite 2/semana).", inline=False)
    embed.add_field(name="/kick @membro [motivo]", value="Expulsa um membro do servidor (limite 5/semana).", inline=False)
    embed.add_field(name="/unban <user_id>", value="Desbane um usuário.", inline=False)
    embed.add_field(name="/nuke", value="Recria o canal atual (com confirmação).", inline=False)
    embed.add_field(name="/tt [@user | ID | @cargo]", value="Mostra limites de bans/kicks.", inline=False)
    embed.add_field(name="/resetlimit <user_id>", value="Reseta limites de bans/kicks (apenas imunes).", inline=False)
    embed.add_field(name="/purge <tempo>", value="Desativa defesas por um tempo (ex: 30m, 2h, 1d). Owner e imunes.", inline=False)
    embed.add_field(name="/unpurge", value="Desativa modo purge (apenas owner).", inline=False)
    embed.add_field(name="/sorteio <tempo_insc> <tempo_sorteio> <descrição>", value="Inicia sorteio com botão e vencedor do JSON.", inline=False)
    embed.add_field(name="/restart", value="Reinicia o navigatebot (com confirmação).", inline=False)
    embed.add_field(name="/recarregar", value="Recarrega a lista de palavras.", inline=False)
    embed.add_field(name="/helpadm", value="Mostra esta mensagem.", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='comandos')
async def enviar_comandos(ctx):
    
    if not is_imune(ctx.author.id):
        await ctx.send("❌ Você não tem permissão para usar este comando.")
        return

    embed = discord.Embed(
        title="📚 Guia completo de comandos",
        description="Separei tudo por categoria para ficar mais fácil de achar o que você precisa.",
        color=discord.Color.blue()
    )

    publicos = (
        "`/count [@usuário]` - Mostra contagem de palavras racistas\n"
        "`/ranking` - Top 10 do ranking\n"
        "`/serverinfo` - Estatísticas do servidor\n"
        "`/uptime` - Tempo online do bot\n"
        "`/ping` - Latência\n"
        "`/ajuda` - Ajuda pública\n"
        "`/upload` - Upload público (vídeo/GIF/imagem) retorna link do Catbox\n"
        "`/twittervideo <link>` - Baixa vídeo de tweet/post do X\n"
        "`/gif <termo>` - Procura um GIF pelo termo informado no GIPHY\n"
        "`/img <termo>` - Procura uma imagem pelo termo informado no Pexels\n"
        "`/resenha` - Exibe os itens da resenha"
    )
    embed.add_field(name="👥 Públicos", value=publicos, inline=False)

    cripto = (
        "`/menu` - Menu interativo com botões\n"
        "`/invest` - Recomendações atuais\n"
        "`/cripto <nome>` - Adiciona moeda\n"
        "`/removercripto <nome>` - Remove moeda\n"
        "`/intervalo <min>` - Altera intervalo\n"
        "`/limite <valor>` - Altera limite"
    )
    embed.add_field(name="🪙 Criptomoedas", value=cripto, inline=False)

    upload_resenha = (
        "`/uploadc` - Adiciona arquivo à resenha (imunes). Usa Catbox.\n"
        "`/meusarquivos` - Mostra os arquivos que você já enviou (DM)"
    )
    embed.add_field(name="📤 Upload para Resenha", value=upload_resenha, inline=False)

    admin = (
        "`/connect <id>` - Entrar em call\n"
        "`/disconnect` - Sair da call\n"
        "`/setrole @cargo @membro` - Atribuir cargo\n"
        "`/ban <id> [motivo]` - Banir (limite 2/semana)\n"
        "`/kick @membro [motivo]` - Expulsar (limite 5/semana)\n"
        "`/unban <id>` - Desbanir\n"
        "`/nuke` - Recriar canal\n"
        "`/tt [user/cargo]` - Ver limites\n"
        "`/resetlimit <id>` - Resetar limites (imunes)\n"
        "`/purge <tempo>` - Ativar modo purge\n"
        "`/unpurge` - Desativar purge\n"
        "`/sorteio <t1> <t2> <desc>` - Criar sorteio\n"
        "`/restart` - Reiniciar bot\n"
        "`/recarregar` - Recarregar palavras\n"
        "`/padd <id>` - Adicionar imune (owner)\n"
        "`/removeimune <id>` - Remover imune (owner)\n"
        "`/helpadm` - Ajuda administrativa"
    )
    embed.add_field(name="🛠 Administrativos", value=admin, inline=False)

    
    novos = (
        "`/steamlogin` - Gera link de login Steam\n"
        "`/steamlogin <código>` - Completa login (receba o código do link)\n"
        "`/email <list|read|send|delete>` - Sistema de email interno\n"
        "`/iplookup <IP>` - Geolocalização de IP\n"
        "`/backup` - Cria backup dos dados (apenas imunes)\n"
        "`/restore` - Restaura backup (anexe o .zip no DM)"
    )
    embed.add_field(name="🆕 Novos Comandos", value=novos, inline=False)

    embed.set_footer(text="Use os slash commands (/) para interagir com o bot.")

    try:
        await ctx.author.send(embed=embed)
        await ctx.send("✅ Lista de comandos enviada no seu DM.")
    except discord.Forbidden:
        await ctx.send("❌ Não foi possível enviar DM. Verifique se você permite mensagens de estranhos.")

async def steam_login_openid_legacy(ctx, code: str = None):
    
    is_dm = isinstance(ctx.channel, discord.DMChannel)

    if code is None:
        url, nonce = await steam_generate_login_url()
        steam_login_states[ctx.author.id] = {"nonce": nonce, "created_at": time.time()}
        embed = discord.Embed(
            title="🔐 Vincular Steam",
            description=(
                "1. Clique no link abaixo e faça login na Steam.\n"
                "2. O navegador vai tentar abrir `https://localhost/...` e provavelmente vai dar erro — isso é esperado.\n"
                "3. Copie a URL COMPLETA da barra de endereço dessa página.\n"
                "4. Me envie a URL no privado usando `/steamlogin codigo:<url completa>`."
            ),
            color=discord.Color.blue()
        )
        embed.add_field(name="Link de login", value=url, inline=False)
        embed.set_footer(text="O vínculo pode ser finalizado sem STEAM_API_KEY usando o perfil XML público da Steam.")

        if is_dm:
            await ctx.send(embed=embed)
        else:
            await ctx.send("📬 Te enviei as instruções no privado para vincular sua Steam.", ephemeral=True if hasattr(ctx, 'interaction') else False)
            try:
                await ctx.author.send(embed=embed)
            except discord.Forbidden:
                await ctx.send("❌ Não consegui te enviar DM. Ative mensagens privadas e tente novamente.")
        return

    if ctx.author.id not in steam_login_states:
        await ctx.send("❌ Nenhum login iniciado. Use `/steamlogin` primeiro.")
        return

    steam_id = extract_steam_id_from_payload(code)
    if not steam_id:
        await ctx.send("❌ Não encontrei um Steam ID válido. Envie a URL completa da página final do login ou o SteamID64.")
        return

    user_info = await steam_get_user_info(steam_id)
    if user_info:
        save_steam_link(ctx.author.id, user_info)
        steam_data_file = f"steam_{ctx.author.id}.json"
        with open(steam_data_file, 'w', encoding='utf-8') as f:
            json.dump(user_info, f, indent=4, ensure_ascii=False)

        embed = discord.Embed(
            title="✅ Steam vinculada com sucesso",
            description=(
                f"**Nome:** {user_info.get('personaname', 'Desconhecido')}\n"
                f"**Steam ID:** {steam_id}\n"
                f"**Perfil:** {user_info.get('profileurl', f'https://steamcommunity.com/profiles/{steam_id}')}"
            ),
            color=discord.Color.green()
        )
        avatar = user_info.get('avatarfull') or user_info.get('avatarmedium') or user_info.get('avatar')
        if avatar:
            embed.set_thumbnail(url=avatar)
        location = user_info.get('location')
        if location:
            embed.add_field(name="Localização", value=location, inline=False)
        privacy = user_info.get('visibilitystate')
        if privacy:
            embed.add_field(name="Visibilidade", value=privacy, inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Não foi possível obter os dados desse perfil Steam. Verifique se o perfil é público ou tente novamente com a URL completa do retorno.")

@bot.command(name='iplookup')
async def ip_lookup_command(ctx, ip: str):
    
    if not ip:
        await ctx.send("❌ Use: `/iplookup <IP>`")
        return
    data, err = await ip_lookup(ip)
    if err:
        await ctx.send(f"❌ Erro: {err}")
        return
    embed = discord.Embed(
        title=f"🌐 Informações do IP {ip}",
        color=discord.Color.gold()
    )
    embed.add_field(name="País", value=data.get('country', 'N/A'), inline=True)
    embed.add_field(name="Região", value=data.get('regionName', 'N/A'), inline=True)
    embed.add_field(name="Cidade", value=data.get('city', 'N/A'), inline=True)
    embed.add_field(name="CEP", value=data.get('zip', 'N/A'), inline=True)
    embed.add_field(name="Lat/Lon", value=f"{data.get('lat')}, {data.get('lon')}", inline=True)
    embed.add_field(name="ISP", value=data.get('isp', 'N/A'), inline=True)
    embed.add_field(name="Organização", value=data.get('org', 'N/A'), inline=True)
    embed.add_field(name="AS", value=data.get('as', 'N/A'), inline=True)
    await ctx.send(embed=embed)

@bot.command(name='backup')
async def backup_command(ctx):
    
    if not is_imune(ctx.author.id):
        await ctx.send("❌ Você não tem permissão para usar este comando.")
        return

    await ctx.send("⏳ Criando backup...")
    zip_buffer = await criar_backup()
    file_size = zip_buffer.getbuffer().nbytes
    if file_size > 25 * 1024 * 1024:
        
        url = await upload_para_catbox(zip_buffer.getvalue(), "backup_bot.zip")
        if url:
            await ctx.author.send(f"✅ Backup criado. Como excede 25MB, link do Catbox:\n{url}")
        else:
            await ctx.author.send("❌ Erro ao fazer upload do backup para Catbox.")
    else:
        await ctx.author.send(
            "✅ Backup criado!",
            file=discord.File(zip_buffer, filename="backup_bot.zip")
        )
    await ctx.send("✅ Backup enviado no seu DM.")

@bot.command(name='restore')
async def restore_command(ctx):
    
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("❌ Este comando só pode ser usado em DM por segurança.")
        return
    if not is_imune(ctx.author.id):
        await ctx.send("❌ Você não tem permissão para usar este comando.")
        return
    if not ctx.message.attachments:
        await ctx.send("❌ Anexe o arquivo de backup (.zip) a esta mensagem.")
        return

    attachment = ctx.message.attachments[0]
    if not attachment.filename.endswith('.zip'):
        await ctx.send("❌ O arquivo deve ser um .zip.")
        return

    await ctx.send("⏳ Restaurando backup... Isso pode sobrescrever dados existentes.")
    zip_bytes = await attachment.read()
    success, err = await restaurar_backup(zip_bytes)
    if success:
        await ctx.send("✅ Backup restaurado com sucesso! Reinicie o bot para aplicar todas as alterações.")
        pass
    else:
        await ctx.send(f"❌ Erro ao restaurar: {err}")

@connect.error
@disconnect.error
@setrole.error
@ban.error
@kick.error
@unban.error
@restart.error
@recarregar.error
@nuke.error
@tt.error
@resetlimit.error
@padd.error
@remove_imune.error
@purge.error
@unpurge.error
@sorteio.error
async def permission_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão para usar este comando.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Argumento inválido. Verifique os IDs ou menções.")
    elif isinstance(error, commands.NotOwner):
        await ctx.send("❌ Apenas o dono do bot pode usar este comando.")
    else:
        await ctx.send(f"❌ Ocorreu um erro: {error}")

class SlashCtx:
    def __init__(self, interaction: discord.Interaction, attachments=None):
        self.interaction = interaction
        self.author = interaction.user
        self.guild = interaction.guild
        self.channel = interaction.channel
        self.message = SimpleNamespace(attachments=attachments or [])

    async def send(self, content=None, **kwargs):
        if not self.interaction.response.is_done():
            await self.interaction.response.send_message(content=content, **kwargs)
        else:
            await self.interaction.followup.send(content=content, **kwargs)

def make_slash_ctx(interaction: discord.Interaction, attachments=None):
    return SlashCtx(interaction, attachments=attachments)

async def owner_only(interaction: discord.Interaction) -> bool:
    return await bot.is_owner(interaction.user)

async def immune_only(interaction: discord.Interaction) -> bool:
    return is_imune(interaction.user.id)

class BaseOwnerView(discord.ui.View):
    def __init__(self, owner_id: int, timeout: int = 300):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message('❌ Esse painel não é seu.', ephemeral=True)
            return False
        return True

class BaseOwnerView(discord.ui.View):
    def __init__(self, owner_id: int, timeout: int = 300):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message('❌ Esse painel não é seu.', ephemeral=True)
            return False
        return True

class SteamProfileModal(discord.ui.Modal, title='Vincular conta Steam'):
    profile_input = discord.ui.TextInput(
        label='URL do perfil ou SteamID64',
        placeholder='https://steamcommunity.com/id/seu_perfil ou 7656119...',
        style=discord.TextStyle.paragraph,
        min_length=3,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        pending = get_pending_steam_code(interaction.user.id)
        if not pending:
            await interaction.response.send_message('❌ Primeiro gere um código no painel Steam.', ephemeral=True)
            return
        info, error = await verify_steam_profile_code(str(self.profile_input), pending)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        save_steam_link(interaction.user.id, info)
        clear_pending_steam_code(interaction.user.id)
        await interaction.response.send_message(embed=build_steam_embed_from_info(info, title='✅ Steam vinculada com sucesso'), ephemeral=True)

class SteamPanelView(BaseOwnerView):
    @discord.ui.button(label='🔑 Gerar código', style=discord.ButtonStyle.success)
    async def generate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        code = create_steam_verification_code(interaction.user.id)
        embed = discord.Embed(
            title='🎮 Verificação Steam',
            description=(
                'Cole este código no **Resumo do Perfil** ou no **Nome temporariamente** na Steam, salve, e depois clique em **Vincular perfil**.\n\n'
                f'**Código:** `{code}`\n\n'
                'Esse método evita o erro de Access Denied do OpenID e não depende de `STEAM_API_KEY`.'
            ),
            color=discord.Color.dark_blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        try:
            await interaction.user.send(embed=embed)
        except discord.Forbidden:
            pass

    @discord.ui.button(label='🔗 Vincular perfil', style=discord.ButtonStyle.primary)
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SteamProfileModal())

    @discord.ui.button(label='👤 Ver vínculo', style=discord.ButtonStyle.secondary)
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        steam_info = get_steam_link(interaction.user.id)
        if not steam_info:
            await interaction.response.send_message('ℹ️ Você ainda não vinculou uma conta Steam.', ephemeral=True)
            return
        await interaction.response.send_message(embed=build_steam_embed_from_info(steam_info), ephemeral=True)

    @discord.ui.button(label='🗑 Desvincular', style=discord.ButtonStyle.danger)
    async def unlink_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if remove_steam_link(interaction.user.id):
            clear_pending_steam_code(interaction.user.id)
            await interaction.response.send_message('✅ Sua conta Steam foi desvinculada.', ephemeral=True)
        else:
            await interaction.response.send_message('ℹ️ Você não possui uma Steam vinculada.', ephemeral=True)

class EmailDeleteModal(discord.ui.Modal, title='Excluir email real'):
    message_id = discord.ui.TextInput(label='ID da mensagem', placeholder='Cole o ID do email aqui', max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        account = get_mailtm_account(interaction.user.id)
        if not account:
            await interaction.response.send_message('❌ Você ainda não tem uma caixa criada.', ephemeral=True)
            return
        ok, err = await mailtm_delete_message(account, str(self.message_id).strip())
        if ok:
            await interaction.response.send_message('✅ Email excluído com sucesso.', ephemeral=True)
        else:
            await interaction.response.send_message(f'❌ Falha ao excluir: {err}', ephemeral=True)

class EmailPanelView(BaseOwnerView):
    @discord.ui.button(label='📬 Criar/mostrar caixa', style=discord.ButtonStyle.success)
    async def mailbox_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        account = get_mailtm_account(interaction.user.id)
        if not account:
            account, err = await mailtm_create_account_for_user(interaction.user.id)
            if err:
                await interaction.response.send_message(f'❌ {err}', ephemeral=True)
                return
        embed = discord.Embed(title='📧 Caixa real criada', description=f"**Endereço:** `{account['address']}`", color=discord.Color.green())
        embed.add_field(name='Senha', value=f"`{account['password']}`", inline=False)
        embed.set_footer(text='As novas mensagens serão verificadas automaticamente e você receberá alerta por DM.')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='📥 Atualizar inbox', style=discord.ButtonStyle.primary)
    async def inbox_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        account = get_mailtm_account(interaction.user.id)
        if not account:
            await interaction.response.send_message('❌ Crie uma caixa primeiro.', ephemeral=True)
            return
        messages, err = await mailtm_list_messages(account)
        if err:
            await interaction.response.send_message(f'❌ {err}', ephemeral=True)
            return
        if not messages:
            await interaction.response.send_message(f'📭 Sua caixa `{account["address"]}` está vazia.', ephemeral=True)
            return
        embed = discord.Embed(title='📥 Inbox real', description=f"Caixa: `{account['address']}`\nMensagens: **{len(messages)}**", color=discord.Color.blurple())
        for i, msg in enumerate(messages[:10], 1):
            embed.add_field(name=f'{i}. {msg.get("subject") or "(sem assunto)"}', value=f"**ID:** `{msg.get('id')}`\n**De:** {msg.get('from', {}).get('address', 'desconhecido')}\n**Data:** {msg.get('createdAt', 'N/A')}", inline=False)
        embed.set_footer(text='Use /email read para abrir uma mensagem ou o botão Excluir email.')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='🗑 Excluir email', style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmailDeleteModal())

async def poll_real_email_notifications():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            accounts = load_mailtm_accounts()
            changed = False
            for user_id_str, account in accounts.items():
                user_id = int(user_id_str)
                messages, err = await mailtm_list_messages(account)
                if err:
                    continue
                current_ids = [m.get('id') for m in messages if m.get('id')]
                notified = set(account.get('notified_message_ids', []))
                notified = {mid for mid in notified if mid in current_ids}
                for msg in messages:
                    mid = msg.get('id')
                    if not mid or mid in notified:
                        continue
                    sender = msg.get('from', {}).get('address', 'desconhecido')
                    subject = msg.get('subject') or '(sem assunto)'
                    user = bot.get_user(user_id)
                    if user is None:
                        try:
                            user = await bot.fetch_user(user_id)
                        except Exception:
                            user = None
                    if user:
                        embed = discord.Embed(
                            title='📨 Novo email recebido',
                            description=f"**Para:** `{account['address']}`\n**De:** {sender}\n**Assunto:** {subject}\n**ID:** `{mid}`",
                            color=discord.Color.gold()
                        )
                        embed.set_footer(text='O email permanece na caixa até você excluir.')
                        try:
                            await user.send(embed=embed)
                            notified.add(mid)
                            changed = True
                        except discord.Forbidden:
                            pass
                if set(account.get('notified_message_ids', [])) != notified:
                    account['notified_message_ids'] = sorted(notified)
                    account['seen_message_ids'] = current_ids
                    accounts[user_id_str] = account
                    changed = True
            if changed:
                save_mailtm_accounts(accounts)
        except Exception as e:
            pass
        await asyncio.sleep(45)

email_group = app_commands.Group(name="email", description="Caixa de email real temporária")
bot.tree.add_command(email_group)

@email_group.command(name="criar", description="Cria ou mostra seu endereço de email real")
async def email_create_real(interaction: discord.Interaction):
    account = get_mailtm_account(interaction.user.id)
    if not account:
        account, err = await mailtm_create_account_for_user(interaction.user.id)
        if err:
            await interaction.response.send_message(f'❌ {err}', ephemeral=True)
            return
    embed = discord.Embed(title='📧 Sua caixa de email real', description=f"**Endereço:** `{account['address']}`", color=discord.Color.green())
    embed.add_field(name='Senha', value=f"`{account['password']}`", inline=False)
    embed.set_footer(text='Você será alertado por DM quando chegarem novos emails.')
    await interaction.response.send_message(embed=embed, ephemeral=True)

@email_group.command(name="list", description="Lista os emails recebidos na sua caixa real")
async def email_list_real(interaction: discord.Interaction):
    account = get_mailtm_account(interaction.user.id)
    if not account:
        await interaction.response.send_message('❌ Você ainda não criou sua caixa. Use /email criar.', ephemeral=True)
        return
    messages, err = await mailtm_list_messages(account)
    if err:
        await interaction.response.send_message(f'❌ {err}', ephemeral=True)
        return
    if not messages:
        await interaction.response.send_message(f'📭 Sua caixa `{account["address"]}` está vazia.', ephemeral=True)
        return
    embed = discord.Embed(title='📥 Inbox real', description=f"Caixa: `{account['address']}`\nMensagens: **{len(messages)}**", color=discord.Color.blurple())
    for i, msg in enumerate(messages[:10], 1):
        embed.add_field(name=f'{i}. {msg.get("subject") or "(sem assunto)"}', value=f"**ID:** `{msg.get('id')}`\n**De:** {msg.get('from', {}).get('address', 'desconhecido')}\n**Data:** {msg.get('createdAt', 'N/A')}", inline=False)
    embed.set_footer(text='Use /email read <id> para abrir e /email delete <id> para excluir.')
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def email_read_real_impl(interaction: discord.Interaction, email_id: str):
    account = get_mailtm_account(interaction.user.id)
    if not account:
        if not interaction.response.is_done():
            await interaction.response.send_message('❌ Você ainda não criou sua caixa. Use /email criar.', ephemeral=True)
        else:
            await interaction.followup.send('❌ Você ainda não criou sua caixa. Use /email criar.', ephemeral=True)
        return
    msg, err = await mailtm_get_message(account, email_id)
    if err or not msg:
        if not interaction.response.is_done():
            await interaction.response.send_message(f'❌ {err or "Email não encontrado."}', ephemeral=True)
        else:
            await interaction.followup.send(f'❌ {err or "Email não encontrado."}', ephemeral=True)
        return
    sender = msg.get('from', {}).get('address', 'desconhecido')
    subject = msg.get('subject') or '(sem assunto)'
    text = msg.get('text') or msg.get('intro') or msg.get('html', [''])[0]
    if isinstance(text, list):
        text = '\n'.join(text)
    embed = discord.Embed(title=f'📨 {subject}', description=f"**De:** {sender}\n**Para:** `{account['address']}`\n**ID:** `{email_id}`", color=discord.Color.blurple())
    embed.add_field(name='Conteúdo', value=(text or '(sem conteúdo)')[:1024], inline=False)
    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)
    remaining = (text or '')[1024:]
    while remaining:
        chunk = remaining[:1900]
        remaining = remaining[1900:]
        await interaction.followup.send(f'```{chunk}```', ephemeral=True)

@email_group.command(name="read", description="Lê um email recebido pelo ID")
@app_commands.describe(email_id="ID do email")
async def email_read_real(interaction: discord.Interaction, email_id: str):
    await email_read_real_impl(interaction, email_id)

@email_group.command(name="delete", description="Exclui um email pelo ID")
@app_commands.describe(email_id="ID do email")
async def email_delete_real(interaction: discord.Interaction, email_id: str):
    account = get_mailtm_account(interaction.user.id)
    if not account:
        await interaction.response.send_message('❌ Você ainda não criou sua caixa. Use /email criar.', ephemeral=True)
        return
    ok, err = await mailtm_delete_message(account, email_id)
    if ok:
        await interaction.response.send_message('✅ Email excluído com sucesso.', ephemeral=True)
    else:
        await interaction.response.send_message(f'❌ Falha ao excluir: {err}', ephemeral=True)

@email_group.command(name="painel", description="Abre os controles da sua caixa de email real")
async def email_panel_real(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f'📧 Caixa do {BOT_NAME}',
        description=(
            'Este painel usa uma caixa temporária real do Mail.tm.\n\n'
            '• Crie seu endereço\n'
            '• Receba emails reais\n'
            '• Seja alertado por DM quando chegar mensagem nova\n'
            '• Os emails ficam disponíveis até você apagar'
        ),
        color=discord.Color.blurple()
    )
    await interaction.response.send_message(embed=embed, view=EmailPanelView(interaction.user.id), ephemeral=True)

@email_group.command(name="endereco", description="Mostra o endereço da sua caixa atual")
async def email_address_real(interaction: discord.Interaction):
    account = get_mailtm_account(interaction.user.id)
    if not account:
        await interaction.response.send_message('❌ Você ainda não criou sua caixa. Use /email criar.', ephemeral=True)
        return
    await interaction.response.send_message(f"📮 Seu endereço atual é: `{account['address']}`", ephemeral=True)

steam_group = app_commands.Group(name='steam', description='Vinculação com a Steam')
bot.tree.add_command(steam_group)

@steam_group.command(name='painel', description='Abre o painel interativo da sua Steam')
async def steam_panel_slash(interaction: discord.Interaction):
    linked = get_steam_link(interaction.user.id)
    pending = get_pending_steam_code(interaction.user.id)
    if linked:
        embed = build_steam_embed_from_info(linked)
        embed.description = (embed.description or '') + '\n\nUse os botões abaixo para gerar um novo código, verificar o perfil ou desvincular a conta.'
    else:
        embed = discord.Embed(
            title=f'🎮 Steam no {BOT_NAME}',
            description=(
                'Para evitar o erro de **Access Denied** do OpenID, este painel usa verificação por código no perfil.\n\n'
                '1. Clique em **Gerar código**\n'
                '2. Cole o código no seu perfil Steam\n'
                '3. Clique em **Vincular perfil** e envie a URL/ID'
            ),
            color=discord.Color.dark_blue()
        )
    if pending:
        embed.add_field(name='Código pendente', value=f'`{pending}`', inline=False)
    await interaction.response.send_message(embed=embed, view=SteamPanelView(interaction.user.id), ephemeral=True)

@steam_group.command(name='status', description='Mostra sua conta Steam vinculada')
async def steam_status_slash(interaction: discord.Interaction):
    linked = get_steam_link(interaction.user.id)
    if not linked:
        await interaction.response.send_message('ℹ️ Você ainda não vinculou uma conta Steam. Use `/steam painel`.', ephemeral=True)
        return
    await interaction.response.send_message(embed=build_steam_embed_from_info(linked), ephemeral=True)

@steam_group.command(name='desvincular', description='Remove o vínculo atual com a Steam')
async def steam_unlink_slash(interaction: discord.Interaction):
    removed = remove_steam_link(interaction.user.id)
    clear_pending_steam_code(interaction.user.id)
    if removed:
        await interaction.response.send_message('✅ Sua conta Steam foi desvinculada.', ephemeral=True)
    else:
        await interaction.response.send_message('ℹ️ Você não possui uma Steam vinculada.', ephemeral=True)

@bot.command(name='steamlogin')
async def steam_login(ctx, code: str = None):
    pending = get_pending_steam_code(ctx.author.id)
    if not code:
        verify_code = create_steam_verification_code(ctx.author.id)
        embed = discord.Embed(
            title='🎮 Vincular Steam',
            description=(
                'O login OpenID da Steam está instável e pode retornar **Access Denied**.\n'
                'Por isso, este comando usa verificação por posse do perfil.\n\n'
                f'**Código:** `{verify_code}`\n\n'
                '1. Coloque esse código no seu resumo do perfil ou nome temporariamente na Steam\n'
                '2. Salve o perfil\n'
                '3. Rode `/steam painel` e clique em **Vincular perfil**, ou use `/steamlogin <url_do_perfil>` em DM'
            ),
            color=discord.Color.dark_blue()
        )
        try:
            await ctx.author.send(embed=embed)
            await ctx.send('📩 Te enviei no privado o código e as instruções para vincular a Steam.')
        except discord.Forbidden:
            await ctx.send(embed=embed)
        return

    if not pending:
        await ctx.send('❌ Nenhuma verificação iniciada. Use `/steamlogin` ou `/steam painel` primeiro.')
        return

    info, error = await verify_steam_profile_code(code, pending)
    if error:
        await ctx.send(error)
        return

    save_steam_link(ctx.author.id, info)
    clear_pending_steam_code(ctx.author.id)
    await ctx.send(embed=build_steam_embed_from_info(info, title='✅ Steam vinculada com sucesso'))

@bot.tree.command(name="count", description="Mostra quantas ocorrências um usuário tem")
async def count_slash(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    await count.callback(make_slash_ctx(interaction), member)

@bot.tree.command(name="ranking", description="Mostra o ranking geral")
async def ranking_slash(interaction: discord.Interaction):
    await ranking.callback(make_slash_ctx(interaction))

@bot.tree.command(name="serverinfo", description="Resume os números do servidor")
async def serverinfo_slash(interaction: discord.Interaction):
    await serverinfo.callback(make_slash_ctx(interaction))

@bot.tree.command(name="uptime", description="Mostra há quanto tempo o navigatebot está online")
async def uptime_slash(interaction: discord.Interaction):
    await uptime.callback(make_slash_ctx(interaction))

@bot.tree.command(name="ping", description="Mostra a latência atual")
async def ping_slash(interaction: discord.Interaction):
    await ping.callback(make_slash_ctx(interaction))

@bot.tree.command(name="ajuda", description="Abre a ajuda com os comandos principais")
async def help_slash(interaction: discord.Interaction):
    await help_public.callback(make_slash_ctx(interaction))

@bot.tree.command(name="menu", description="Abre a central de cripto")
async def menu_slash(interaction: discord.Interaction):
    await menu_principal.callback(make_slash_ctx(interaction))

@bot.tree.command(name="invest", description="Mostra a leitura atual das moedas")
async def invest_slash(interaction: discord.Interaction):
    await invest_simples.callback(make_slash_ctx(interaction))

@bot.tree.command(name="cripto", description="Adiciona uma moeda à lista de acompanhamento")
@app_commands.describe(nome="Nome da criptomoeda")
async def cripto_slash(interaction: discord.Interaction, nome: str):
    await adicionar_cripto.callback(make_slash_ctx(interaction), nome=nome)

@bot.tree.command(name="removercripto", description="Remove uma moeda da lista de acompanhamento")
@app_commands.describe(nome="Nome da criptomoeda")
async def remover_cripto_slash(interaction: discord.Interaction, nome: str):
    await remover_cripto.callback(make_slash_ctx(interaction), nome=nome)

@bot.tree.command(name="intervalo", description="Define o intervalo das atualizações de cripto")
@app_commands.describe(minutos="Intervalo em minutos")
async def intervalo_slash(interaction: discord.Interaction, minutos: int):
    await alterar_intervalo.callback(make_slash_ctx(interaction), minutos)

@bot.tree.command(name="limite", description="Define o valor de referência para investimento")
@app_commands.describe(valor="Novo limite")
async def limite_slash(interaction: discord.Interaction, valor: float):
    await alterar_limite.callback(make_slash_ctx(interaction), valor)

@bot.tree.command(name="upload", description="Envia um arquivo e devolve o link direto")
@app_commands.describe(arquivo="Arquivo para enviar")
async def upload_slash(interaction: discord.Interaction, arquivo: discord.Attachment):
    await upload_publico.callback(make_slash_ctx(interaction, [arquivo]))

@bot.tree.command(name="uploadc", description="Guarda um arquivo na resenha")
@app_commands.check(immune_only)
@app_commands.describe(arquivo="Arquivo para enviar", categoria="Categoria da resenha")
async def uploadc_slash(interaction: discord.Interaction, arquivo: discord.Attachment, categoria: str):
    ctx = make_slash_ctx(interaction, [arquivo])
    if arquivo.size > 200 * 1024 * 1024:
        await ctx.send("❌ Arquivo muito grande. O limite é 200 MB.")
        return
    await ctx.send("⏳ Fazendo upload para o Catbox...")
    try:
        arquivo_bytes = await arquivo.read()
        url = await upload_para_catbox(arquivo_bytes, arquivo.filename)
        if not url:
            await ctx.send("❌ Erro ao fazer upload. Tente novamente mais tarde.")
            return
        salvar_metadados(ctx.author.id, arquivo.filename, url)
        resenha_data = carregar_resenha()
        resenha_data.setdefault(categoria, []).append(url)
        salvar_resenha(resenha_data)
        if eh_video(arquivo.filename):
            tipo = "🎬 Vídeo"
        elif eh_gif(arquivo.filename):
            tipo = "🎞️ GIF"
        elif eh_imagem(arquivo.filename):
            tipo = "🖼️ Imagem"
        else:
            tipo = "📁 Arquivo"
        embed = discord.Embed(
            title="✅ Adicionado à resenha!",
            description=f"**Arquivo:** {arquivo.filename}\n**Tipo:** {tipo}\n**Categoria:** {categoria}\n**Link:** {url}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    except Exception as e:
        pass
        await ctx.send(f"❌ Erro: {e}")

@bot.tree.command(name="meusarquivos", description="Mostra os arquivos que você já enviou")
async def meus_arquivos_slash(interaction: discord.Interaction):
    await meus_arquivos.callback(make_slash_ctx(interaction))

@bot.tree.command(name="gif", description="Procura um GIF pelo termo informado")
@app_commands.describe(termo="Termo de busca")
async def gif_slash(interaction: discord.Interaction, termo: str):
    await gif_command.callback(make_slash_ctx(interaction), termo=termo)

@bot.tree.command(name="img", description="Procura uma imagem pelo termo informado")
@app_commands.describe(termo="Termo de busca")
async def img_slash(interaction: discord.Interaction, termo: str):
    await image_command.callback(make_slash_ctx(interaction), termo=termo)

@bot.tree.command(name="twittervideo", description="Baixa o vídeo de um link do X/Twitter")
@app_commands.describe(url="URL do tweet/post")
async def twittervideo_slash(interaction: discord.Interaction, url: str):
    await twitter_video_command.callback(make_slash_ctx(interaction), url)

@bot.tree.command(name="resenha", description="Mostra o que já foi salvo na resenha")
async def resenha_slash(interaction: discord.Interaction):
    await resenha.callback(make_slash_ctx(interaction))

@bot.tree.command(name="connect", description="Conecta o navigatebot a um canal de voz")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(channel_id="ID do canal de voz")
async def connect_slash(interaction: discord.Interaction, channel_id: int):
    await connect.callback(make_slash_ctx(interaction), channel_id)

@bot.tree.command(name="disconnect", description="Desconecta o navigatebot do canal de voz")
@app_commands.checks.has_permissions(administrator=True)
async def disconnect_slash(interaction: discord.Interaction):
    await disconnect.callback(make_slash_ctx(interaction))

@bot.tree.command(name="setrole", description="Entrega um cargo para um membro")
@app_commands.checks.has_permissions(administrator=True)
async def setrole_slash(interaction: discord.Interaction, role: discord.Role, member: discord.Member):
    await setrole.callback(make_slash_ctx(interaction), role, member)

@bot.tree.command(name="ban", description="Bane um usuário pelo ID")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_slash(interaction: discord.Interaction, user_id: str, motivo: str = "Não especificado"):
    await ban.callback(make_slash_ctx(interaction), int(user_id), motivo=motivo)

@bot.tree.command(name="kick", description="Expulsa um membro do servidor")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_slash(interaction: discord.Interaction, member: discord.Member, motivo: str = "Não especificado"):
    await kick.callback(make_slash_ctx(interaction), member, motivo=motivo)

@bot.tree.command(name="unban", description="Remove o banimento de um usuário pelo ID")
@app_commands.checks.has_permissions(ban_members=True)
async def unban_slash(interaction: discord.Interaction, user_id: str):
    await unban.callback(make_slash_ctx(interaction), int(user_id))

@bot.tree.command(name="restart", description="Reinicia o navigatebot")
@app_commands.checks.has_permissions(administrator=True)
async def restart_slash(interaction: discord.Interaction):
    await restart.callback(make_slash_ctx(interaction))

@bot.tree.command(name="recarregar", description="Recarrega listas e configurações")
@app_commands.checks.has_permissions(administrator=True)
async def recarregar_slash(interaction: discord.Interaction):
    await recarregar.callback(make_slash_ctx(interaction))

@bot.tree.command(name="nuke", description="Recria o canal atual do zero")
@app_commands.checks.has_permissions(administrator=True)
async def nuke_slash(interaction: discord.Interaction):
    await nuke.callback(make_slash_ctx(interaction))

@bot.tree.command(name="tt", description="Mostra os limites semanais")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(target="Usuário, ID ou nome do cargo")
async def tt_slash(interaction: discord.Interaction, target: Optional[str] = None):
    await tt.callback(make_slash_ctx(interaction), target)

@bot.tree.command(name="resetlimit", description="Zera os limites de um usuário")
@app_commands.check(immune_only)
async def resetlimit_slash(interaction: discord.Interaction, user_id: str):
    await resetlimit.callback(make_slash_ctx(interaction), int(user_id))

@bot.tree.command(name="purge", description="Ativa o modo purge por um período")
@app_commands.describe(tempo="Tempo do purge, exemplo: 10m")
async def purge_slash(interaction: discord.Interaction, tempo: str):
    await purge.callback(make_slash_ctx(interaction), tempo)

@bot.tree.command(name="unpurge", description="Desativa o modo purge")
@app_commands.check(owner_only)
async def unpurge_slash(interaction: discord.Interaction):
    await unpurge.callback(make_slash_ctx(interaction))

@bot.tree.command(name="sorteio", description="Cria um sorteio com botão de participação")
@app_commands.checks.has_permissions(administrator=True)
async def sorteio_slash(interaction: discord.Interaction, tempo_inscricao: str, tempo_sorteio: str, descricao: str):
    await sorteio.callback(make_slash_ctx(interaction), tempo_inscricao, tempo_sorteio, descricao=descricao)

@bot.tree.command(name="padd", description="Adiciona um usuário à lista de imunes")
@app_commands.check(owner_only)
async def padd_slash(interaction: discord.Interaction, user_id: str):
    await padd.callback(make_slash_ctx(interaction), int(user_id))

@bot.tree.command(name="removeimune", description="Remove um usuário da lista de imunes")
@app_commands.check(owner_only)
async def remove_imune_slash(interaction: discord.Interaction, user_id: str):
    await remove_imune.callback(make_slash_ctx(interaction), int(user_id))

@bot.tree.command(name="helpadm", description="Abre a ajuda administrativa")
@app_commands.checks.has_permissions(administrator=True)
async def helpadm_slash(interaction: discord.Interaction):
    await help_admin.callback(make_slash_ctx(interaction))

@bot.tree.command(name="comandos", description="Envia a lista completa no seu privado")
async def comandos_slash(interaction: discord.Interaction):
    await enviar_comandos.callback(make_slash_ctx(interaction))

@bot.tree.command(name="steamlogin", description="Inicia ou conclui a vinculação com a Steam")
async def steamlogin_slash(interaction: discord.Interaction, code: Optional[str] = None):
    await steam_login.callback(make_slash_ctx(interaction), code)

@bot.tree.command(name="iplookup", description="Consulta informações básicas de um IP")
async def iplookup_slash(interaction: discord.Interaction, ip: str):
    await ip_lookup_command.callback(make_slash_ctx(interaction), ip)

@bot.tree.command(name="backup", description="Cria um backup dos dados do navigatebot")
@app_commands.check(immune_only)
async def backup_slash(interaction: discord.Interaction):
    await backup_command.callback(make_slash_ctx(interaction))

@bot.tree.command(name="restore", description="Restaura os dados a partir de um arquivo .zip")
@app_commands.check(immune_only)
async def restore_slash(interaction: discord.Interaction, arquivo: discord.Attachment):
    await restore_command.callback(make_slash_ctx(interaction, [arquivo]))

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        msg = "❌ Você não tem permissão para usar este comando."
    elif isinstance(error, app_commands.errors.CheckFailure):
        msg = "❌ Você não pode usar este comando."
    elif isinstance(error, app_commands.errors.CommandInvokeError):
        original = error.original
        msg = f"❌ Ocorreu um erro: {original}"
        pass
    else:
        msg = f"❌ Ocorreu um erro: {error}"
        pass
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)

@app_commands.describe(visibilidade='private ou public', tema='blue, green, purple, gold, red', mostrar_resumo='Mostrar resumo do perfil', mostrar_localizacao='Mostrar localização do perfil')
@steam_group.command(name='configuracoes', description='Ajusta visual e privacidade da sua Steam vinculada')
async def steam_config_slash(interaction: discord.Interaction, visibilidade: str = 'public', tema: str = 'blue', mostrar_resumo: bool = True, mostrar_localizacao: bool = True):
    vis = visibilidade.lower().strip()
    if vis not in ('public', 'private'):
        await interaction.response.send_message('❌ A visibilidade deve ser `public` ou `private`.', ephemeral=True)
        return
    tema = tema.lower().strip()
    if tema not in ('blue', 'green', 'purple', 'gold', 'red'):
        await interaction.response.send_message('❌ Tema inválido. Use: blue, green, purple, gold ou red.', ephemeral=True)
        return
    settings = update_steam_settings(interaction.user.id, profile_visibility=vis, theme=tema, show_summary=mostrar_resumo, show_location=mostrar_localizacao)
    linked = get_steam_link(interaction.user.id)
    if linked:
        embed = build_styled_steam_embed(linked, settings=settings, title='⚙️ Preferências da Steam atualizadas', owner=interaction.user)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(f'✅ Configurações salvas. Visibilidade: `{vis}` • Tema: `{tema}`', ephemeral=True)

@steam_group.command(name='atualizar', description='Atualiza os dados da sua Steam já vinculada')
async def steam_refresh_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)
    info, err = await refresh_linked_steam(interaction.user.id)
    if err:
        await interaction.followup.send(f'❌ {err}', ephemeral=True)
        return
    settings = get_steam_settings(interaction.user.id)
    await interaction.followup.send(embed=build_styled_steam_embed(info, settings=settings, title='🔄 Perfil Steam atualizado agora', owner=interaction.user), ephemeral=True)

@app_commands.describe(usuario='Usuário do Discord para consultar')
@steam_group.command(name='show', description='Mostra a Steam vinculada de um usuário')
async def steam_show_slash(interaction: discord.Interaction, usuario: discord.User):
    linked = get_steam_link(usuario.id)
    if not linked:
        await interaction.response.send_message('ℹ️ Esse usuário não possui uma Steam vinculada.', ephemeral=True)
        return
    settings = get_steam_settings(usuario.id)
    if settings.get('profile_visibility', 'public') == 'private' and interaction.user.id != usuario.id:
        await interaction.response.send_message('🔒 Esse usuário deixou a Steam vinculada como privada.', ephemeral=True)
        return
    await interaction.response.send_message(embed=build_styled_steam_embed(linked, settings=settings, owner=usuario), ephemeral=False)

if __name__ == "__main__":
    pass
    if TOKEN:
        bot.run(TOKEN)
    else:
        pass
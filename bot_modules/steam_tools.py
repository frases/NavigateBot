import json
import re
import secrets
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

import aiohttp
import discord

from .storage import load_json_file, save_json_file

STEAM_LINKS_FILE = 'steam_links.json'
STEAM_SETTINGS_FILE = 'steam_settings.json'
steam_verification_states = {}

def load_steam_links():
    return load_json_file(STEAM_LINKS_FILE, {})

def save_steam_links(data):
    save_json_file(STEAM_LINKS_FILE, data)

def save_steam_link(discord_user_id: int, steam_info: dict):
    links = load_steam_links()
    steam_id = steam_info.get('steamid') or steam_info.get('steam_id')
    links[str(discord_user_id)] = {
        'steamid': steam_id,
        'steam_id': steam_id,
        'personaname': steam_info.get('personaname', 'Desconhecido'),
        'profileurl': steam_info.get('profileurl', ''),
        'avatarfull': steam_info.get('avatarfull', ''),
        'headline': steam_info.get('headline', ''),
        'location': steam_info.get('location', ''),
        'visibilitystate': steam_info.get('visibilitystate', ''),
        'linked_at': steam_info.get('linked_at', datetime.utcnow().isoformat()),
    }
    save_steam_links(links)

def get_steam_link(discord_user_id: int) -> Optional[dict]:
    return load_steam_links().get(str(discord_user_id))

def remove_steam_link(discord_user_id: int) -> bool:
    links = load_steam_links()
    if str(discord_user_id) not in links:
        return False
    del links[str(discord_user_id)]
    save_steam_links(links)
    return True

def build_steam_embed_from_info(steam_info: dict, title: str = '🎮 Painel Steam') -> discord.Embed:
    steam_id = steam_info.get('steamid') or steam_info.get('steam_id') or 'Desconhecido'
    profile = steam_info.get('profileurl') or f'https://steamcommunity.com/profiles/{steam_id}'
    embed = discord.Embed(
        title=title,
        description=(
            f"**Nome:** {steam_info.get('personaname', 'Desconhecido')}\n"
            f"**Steam ID:** {steam_id}\n"
            f"**Perfil:** {profile}"
        ),
        color=discord.Color.dark_blue(),
    )
    avatar = steam_info.get('avatarfull') or steam_info.get('avatarmedium') or steam_info.get('avatar')
    if avatar:
        embed.set_thumbnail(url=avatar)
    linked_at = steam_info.get('linked_at')
    if linked_at:
        embed.add_field(name='Vinculado em', value=linked_at.replace('T', ' '), inline=False)
    headline = steam_info.get('headline')
    if headline:
        embed.add_field(name='Resumo do perfil', value=headline[:1024], inline=False)
    location = steam_info.get('location')
    if location:
        embed.add_field(name='Localização', value=location, inline=False)
    privacy = steam_info.get('visibilitystate')
    if privacy:
        embed.add_field(name='Visibilidade', value=privacy, inline=False)
    return embed

def create_steam_verification_code(user_id: int) -> str:
    code = f'NAVSTEAM-{secrets.token_hex(3).upper()}'
    steam_verification_states[user_id] = {
        'code': code,
        'created_at': time.time(),
    }
    return code

def get_pending_steam_code(user_id: int) -> Optional[str]:
    state = steam_verification_states.get(user_id)
    if not state:
        return None
    return state.get('code')

def clear_pending_steam_code(user_id: int):
    steam_verification_states.pop(user_id, None)

def extract_steam_id_from_payload(payload: str) -> Optional[str]:
    if not payload:
        return None
    patterns = [
        r'https?://steamcommunity\.com/openid/id/(\d+)',
        r'https?://steamcommunity\.com/profiles/(\d+)',
        r'\b(7656119\d{10})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, payload, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

async def fetch_text(url: str) -> Optional[str]:
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=20, allow_redirects=True) as resp:
                if resp.status != 200:
                    return None
                return await resp.text()
    except Exception:
        return None

async def resolve_steam_profile_input(profile_input: str):
    profile_input = (profile_input or '').strip()
    if not profile_input:
        return None, None, None

    steam_id = extract_steam_id_from_payload(profile_input)
    if steam_id:
        profile_url = f'https://steamcommunity.com/profiles/{steam_id}'
        xml_url = profile_url + '?xml=1'
        return steam_id, profile_url, xml_url

    custom_match = re.search(r'https?://steamcommunity\.com/id/([^/?#]+)/?', profile_input, re.IGNORECASE)
    if custom_match:
        vanity = custom_match.group(1)
        profile_url = f'https://steamcommunity.com/id/{vanity}'
        xml_url = profile_url + '?xml=1'
        xml_text = await fetch_text(xml_url)
        if xml_text:
            sid = extract_steam_id_from_payload(xml_text)
            if sid is None:
                m = re.search(r'<steamID64>(\d+)</steamID64>', xml_text)
                if m:
                    sid = m.group(1)
            return sid, profile_url, xml_url
        return None, profile_url, xml_url

    if re.fullmatch(r'[A-Za-z0-9_-]{2,64}', profile_input):
        profile_url = f'https://steamcommunity.com/id/{profile_input}'
        xml_url = profile_url + '?xml=1'
        xml_text = await fetch_text(xml_url)
        if xml_text:
            m = re.search(r'<steamID64>(\d+)</steamID64>', xml_text)
            if m:
                return m.group(1), profile_url, xml_url

    return None, None, None

async def steam_get_user_info_from_xml_url(xml_url: str, fallback_profile_url: Optional[str] = None):
    xml_text = await fetch_text(xml_url)
    if not xml_text:
        return None
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    def get_text(tag: str, default: str = ''):
        node = root.find(tag)
        return node.text.strip() if node is not None and node.text else default

    steamid64 = get_text('steamID64')
    custom_url = get_text('customURL')
    if custom_url and custom_url.startswith('http'):
        profile_url = custom_url
    elif custom_url:
        profile_url = f'https://steamcommunity.com/id/{custom_url}'
    else:
        profile_url = fallback_profile_url or f'https://steamcommunity.com/profiles/{steamid64}'

    return {
        'steamid': steamid64,
        'steam_id': steamid64,
        'personaname': get_text('steamID', 'Perfil Steam'),
        'profileurl': profile_url,
        'avatar': get_text('avatarIcon'),
        'avatarmedium': get_text('avatarMedium'),
        'avatarfull': get_text('avatarFull'),
        'headline': get_text('headline') or get_text('summary'),
        'location': ' / '.join([v for v in [get_text('location'), get_text('stateOrProvince'), get_text('country')] if v]),
        'visibilitystate': get_text('privacyState'),
    }

async def steam_get_user_info(steam_input: str):
    steam_id, profile_url, xml_url = await resolve_steam_profile_input(steam_input)
    if xml_url:
        info = await steam_get_user_info_from_xml_url(xml_url, fallback_profile_url=profile_url)
        if info:
            return info
    if steam_id:
        xml_url = f'https://steamcommunity.com/profiles/{steam_id}?xml=1'
        return await steam_get_user_info_from_xml_url(
            xml_url,
            fallback_profile_url=f'https://steamcommunity.com/profiles/{steam_id}',
        )
    return None

async def verify_steam_profile_code(profile_input: str, code: str):
    steam_id, profile_url, xml_url = await resolve_steam_profile_input(profile_input)
    if not xml_url:
        return None, '❌ Não consegui interpretar a URL/ID do perfil Steam.'

    info = await steam_get_user_info_from_xml_url(xml_url, fallback_profile_url=profile_url)
    if not info:
        return None, '❌ Não consegui abrir esse perfil. Verifique se ele existe e está público.'

    html = await fetch_text(profile_url) if profile_url else None
    code_upper = (code or '').strip().upper()
    haystacks = [
        json.dumps(info, ensure_ascii=False).upper(),
        (html or '').upper(),
    ]
    if not any(code_upper in h for h in haystacks):
        return None, (
            '❌ Não encontrei o código de verificação no seu perfil. '
            'Coloque o código no **Resumo do Perfil** ou no **Nome temporariamente**, salve na Steam e tente de novo.'
        )

    return info, None

def load_steam_settings():
    return load_json_file(STEAM_SETTINGS_FILE, {})

def save_steam_settings(data):
    save_json_file(STEAM_SETTINGS_FILE, data)

def get_steam_settings(discord_user_id: int) -> dict:
    settings = load_steam_settings().get(str(discord_user_id), {})
    return {
        'profile_visibility': settings.get('profile_visibility', 'public'),
        'theme': settings.get('theme', 'blue'),
        'show_summary': bool(settings.get('show_summary', True)),
        'show_location': bool(settings.get('show_location', True)),
    }

def update_steam_settings(discord_user_id: int, **updates) -> dict:
    data = load_steam_settings()
    current = get_steam_settings(discord_user_id)
    current.update({k: v for k, v in updates.items() if v is not None})
    data[str(discord_user_id)] = current
    save_steam_settings(data)
    return current

def theme_color(theme: str):
    return {
        'blue': discord.Color.blurple(),
        'green': discord.Color.green(),
        'purple': discord.Color.purple(),
        'gold': discord.Color.gold(),
        'red': discord.Color.red(),
    }.get((theme or 'blue').lower(), discord.Color.blurple())

def build_styled_steam_embed(
    steam_info: dict,
    settings: Optional[dict] = None,
    title: str = '🎮 Perfil Steam',
    owner: Optional[discord.abc.User] = None,
) -> discord.Embed:
    settings = settings or get_steam_settings(int(owner.id)) if owner else (settings or {})
    settings = settings or {'theme': 'blue', 'show_summary': True, 'show_location': True}
    steam_id = steam_info.get('steamid') or steam_info.get('steam_id') or 'Desconhecido'
    profile = steam_info.get('profileurl') or f'https://steamcommunity.com/profiles/{steam_id}'
    desc = [
        f"### {steam_info.get('personaname', 'Desconhecido')}",
        f"**Steam ID:** `{steam_id}`",
        f"**Perfil:** {profile}",
    ]
    if owner is not None:
        desc.append(f"**Discord:** {owner.mention}")
    embed = discord.Embed(
        title=title,
        description='\n'.join(desc),
        color=theme_color(settings.get('theme', 'blue')),
    )
    avatar = steam_info.get('avatarfull') or steam_info.get('avatarmedium') or steam_info.get('avatar')
    if avatar:
        embed.set_thumbnail(url=avatar)
    linked_at = steam_info.get('linked_at')
    if linked_at:
        embed.add_field(name='Vinculado em', value=linked_at.replace('T', ' '), inline=True)
    embed.add_field(name='Visibilidade do painel', value=settings.get('profile_visibility', 'public'), inline=True)
    privacy = steam_info.get('visibilitystate') or 'desconhecida'
    embed.add_field(name='Privacidade Steam', value=privacy, inline=True)
    if settings.get('show_summary', True) and steam_info.get('headline'):
        embed.add_field(name='Resumo', value=steam_info.get('headline')[:1024], inline=False)
    if settings.get('show_location', True) and steam_info.get('location'):
        embed.add_field(name='Localização', value=steam_info.get('location')[:1024], inline=False)
    embed.set_footer(text=f"Tema: {settings.get('theme', 'blue')} • Use /steam configuracoes para personalizar")
    return embed

async def refresh_linked_steam(discord_user_id: int):
    linked = get_steam_link(discord_user_id)
    if not linked:
        return None, 'Nenhuma conta Steam vinculada.'
    steam_input = linked.get('profileurl') or linked.get('steamid') or linked.get('steam_id')
    info = await steam_get_user_info(steam_input)
    if not info:
        return None, 'Não foi possível atualizar o perfil agora. Verifique se ele ainda está público.'
    info['linked_at'] = linked.get('linked_at', datetime.utcnow().isoformat())
    save_steam_link(discord_user_id, info)
    return get_steam_link(discord_user_id), None

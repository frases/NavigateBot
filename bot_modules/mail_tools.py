import json
import os
import random
import re
import secrets
import time
from datetime import datetime
from typing import Optional

import aiohttp

from .storage import load_json_file, save_json_file

EMAILS_DIR = 'emails'
EMAILS_EXPIRATION_HOURS = 24
MAILTM_ACCOUNTS_FILE = 'mailtm_accounts.json'
MAILTM_API = 'https://api.mail.tm'

os.makedirs(EMAILS_DIR, exist_ok=True)

def email_filename(user_id):
    return os.path.join(EMAILS_DIR, f'{user_id}.json')

def carregar_emails(user_id):
    arquivo = email_filename(user_id)
    if not os.path.exists(arquivo):
        return []
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def salvar_emails(user_id, emails):
    arquivo = email_filename(user_id)
    agora = time.time()
    emails = [e for e in emails if e.get('expira', 0) > agora]
    emails.sort(key=lambda e: e.get('data', ''), reverse=True)
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(emails, f, indent=4, ensure_ascii=False)

def normalizar_email_texto(texto: str, limite: int) -> str:
    texto = (texto or '').strip()
    texto = re.sub(r'\r\n?', '\n', texto)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto[:limite]

def gerar_email_id() -> str:
    return f"{int(time.time() * 1000)}{random.randint(1000, 9999)}"

def enviar_email(remetente_id, destinatario_id, assunto, corpo):
    assunto = normalizar_email_texto(assunto, 120)
    corpo = normalizar_email_texto(corpo, 3500)

    if not assunto:
        return False, 'O assunto não pode ficar vazio.'
    if len(assunto) < 3:
        return False, 'O assunto precisa ter pelo menos 3 caracteres.'
    if not corpo:
        return False, 'O corpo do email não pode ficar vazio.'
    if remetente_id == destinatario_id:
        return False, 'Você não pode enviar email para si mesmo.'

    dest_emails = carregar_emails(destinatario_id) or []
    novo_email = {
        'id': gerar_email_id(),
        'de': remetente_id,
        'assunto': assunto,
        'corpo': corpo,
        'preview': corpo[:120],
        'data': datetime.now().isoformat(timespec='seconds'),
        'lido': False,
        'expira': time.time() + (EMAILS_EXPIRATION_HOURS * 3600),
    }
    dest_emails.append(novo_email)
    salvar_emails(destinatario_id, dest_emails)
    return True, f'Email enviado para {destinatario_id}'

def listar_emails(user_id, apenas_nao_lidos=False):
    emails = carregar_emails(user_id)
    emails.sort(key=lambda e: e.get('data', ''), reverse=True)
    if apenas_nao_lidos:
        emails = [e for e in emails if not e.get('lido', False)]
    return emails

def ler_email(user_id, email_id):
    emails = carregar_emails(user_id)
    for email in emails:
        if email['id'] == email_id:
            email['lido'] = True
            salvar_emails(user_id, emails)
            return email
    return None

def excluir_email(user_id, email_id):
    emails = carregar_emails(user_id)
    novos = [email for email in emails if email['id'] != email_id]
    if len(novos) == len(emails):
        return False
    salvar_emails(user_id, novos)
    return True

def load_mailtm_accounts():
    return load_json_file(MAILTM_ACCOUNTS_FILE, {})

def save_mailtm_accounts(data):
    save_json_file(MAILTM_ACCOUNTS_FILE, data)

def get_mailtm_account(user_id: int) -> Optional[dict]:
    return load_mailtm_accounts().get(str(user_id))

def save_mailtm_account(user_id: int, account: dict):
    data = load_mailtm_accounts()
    existing = data.get(str(user_id), {})
    existing.update(account)
    data[str(user_id)] = existing
    save_mailtm_accounts(data)

def delete_mailtm_account(user_id: int):
    data = load_mailtm_accounts()
    if str(user_id) in data:
        del data[str(user_id)]
        save_mailtm_accounts(data)
        return True
    return False

async def mailtm_get_domains():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{MAILTM_API}/domains', timeout=20) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return [item['domain'] for item in data.get('hydra:member', []) if item.get('isActive', True)]
    except Exception as e:
        pass
        return []

async def mailtm_create_account_for_user(user_id: int):
    domains = await mailtm_get_domains()
    if not domains:
        return None, 'Não foi possível obter domínios do Mail.tm agora.'
    domain = random.choice(domains)
    address = f'discord{user_id}_{secrets.token_hex(4)}@{domain}'
    password = secrets.token_urlsafe(16)
    payload = {'address': address, 'password': password}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{MAILTM_API}/accounts', json=payload, timeout=20) as resp:
                if resp.status not in (200, 201):
                    text = await resp.text()
                    return None, f'Falha ao criar caixa real ({resp.status}): {text[:300]}'
                created = await resp.json()
            async with session.post(f'{MAILTM_API}/token', json=payload, timeout=20) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return None, f'Conta criada, mas o token falhou ({resp.status}): {text[:300]}'
                token_data = await resp.json()
        account = {
            'service': 'mail.tm',
            'account_id': created.get('id'),
            'address': address,
            'password': password,
            'token': token_data.get('token'),
            'created_at': datetime.utcnow().isoformat(),
            'seen_message_ids': [],
            'notified_message_ids': [],
        }
        save_mailtm_account(user_id, account)
        return account, None
    except Exception as e:
        return None, f'Erro ao criar conta Mail.tm: {e}'

async def mailtm_api_request(account: dict, method: str, path: str):
    headers = {'Authorization': f"Bearer {account['token']}"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.request(method, f'{MAILTM_API}{path}', timeout=20) as resp:
            if resp.status >= 400:
                return None, resp.status, await resp.text()
            ctype = resp.headers.get('Content-Type', '')
            if 'application/json' in ctype:
                return await resp.json(), resp.status, None
            return await resp.text(), resp.status, None

async def mailtm_list_messages(account: dict):
    data, status, err = await mailtm_api_request(account, 'GET', '/messages?page=1')
    if status and status < 400 and isinstance(data, dict):
        return data.get('hydra:member', []), None
    return [], err or 'Falha ao listar mensagens.'

async def mailtm_get_message(account: dict, message_id: str):
    data, status, err = await mailtm_api_request(account, 'GET', f'/messages/{message_id}')
    if status and status < 400:
        return data, None
    return None, err or 'Falha ao ler mensagem.'

async def mailtm_delete_message(account: dict, message_id: str):
    _, status, err = await mailtm_api_request(account, 'DELETE', f'/messages/{message_id}')
    return bool(status and status < 400), err

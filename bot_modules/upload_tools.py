import json
import os
from datetime import datetime

import aiohttp

UPLOADS_DIR = 'uploads'
os.makedirs(UPLOADS_DIR, exist_ok=True)

async def upload_para_catbox(arquivo_bytes, nome_arquivo):
    url = 'https://catbox.moe/user/api.php'
    data = aiohttp.FormData()
    data.add_field('reqtype', 'fileupload')
    data.add_field('fileToUpload', arquivo_bytes, filename=nome_arquivo, content_type='application/octet-stream')

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as resp:
                if resp.status == 200:
                    return (await resp.text()).strip()
                pass
                return None
    except Exception as e:
        pass
        return None

def salvar_metadados(user_id, nome_arquivo, url):
    arquivo_user = os.path.join(UPLOADS_DIR, f'{user_id}.json')
    dados = []
    if os.path.exists(arquivo_user):
        with open(arquivo_user, 'r', encoding='utf-8') as f:
            dados = json.load(f)
    dados.append({
        'nome': nome_arquivo,
        'url': url,
        'data': datetime.utcnow().isoformat(),
    })
    with open(arquivo_user, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4)

def carregar_metadados(user_id):
    arquivo_user = os.path.join(UPLOADS_DIR, f'{user_id}.json')
    if not os.path.exists(arquivo_user):
        return []
    with open(arquivo_user, 'r', encoding='utf-8') as f:
        return json.load(f)

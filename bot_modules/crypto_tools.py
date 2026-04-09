import json
import os
import time

import aiohttp

CONFIG_FILE = 'config.json'
CACHE_DURACAO = 60
cache_precos = {}
cache_timestamp = 0

def load_config():
    if not os.path.exists(CONFIG_FILE):
        default = {
            "cryptos": ["bitcoin", "ethereum", "ripple", "tron", "solana", "cardano", "usd-coin", "tether"],
            "intervalo_minutos": 30,
            "limite_investimento": 1000,
            "api_priority": ["binance", "coingecko"],
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4)
        return default
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config()

async def obter_precos_binance(cryptos):
    precos = {}
    mapa = {
        "bitcoin": "BTCUSDT", "ethereum": "ETHUSDT", "ripple": "XRPUSDT",
        "cardano": "ADAUSDT", "solana": "SOLUSDT", "dogecoin": "DOGEUSDT",
        "polkadot": "DOTUSDT", "litecoin": "LTCUSDT", "tron": "TRXUSDT",
        "usd-coin": "USDCUSDT", "tether": "USDTUSDT", "binancecoin": "BNBUSDT",
        "chainlink": "LINKUSDT", "stellar": "XLMUSDT",
    }
    async with aiohttp.ClientSession() as session:
        for crypto in cryptos:
            if crypto in mapa:
                symbol = mapa[crypto]
                url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
                try:
                    async with session.get(url, timeout=5) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            precos[crypto] = {
                                "usd": float(data["lastPrice"]),
                                "usd_24h_change": float(data["priceChangePercent"]),
                            }
                except Exception as e:
                    pass
    return precos

async def obter_precos_coingecko(cryptos):
    ids = ",".join(cryptos)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            pass
    return {}

async def obter_precos_com_fallback(cryptos, priority_apis):
    global cache_precos, cache_timestamp
    if time.time() - cache_timestamp < CACHE_DURACAO and cache_precos:
        return cache_precos

    for api in priority_apis:
        if api == "binance":
            precos = await obter_precos_binance(cryptos)
            if precos:
                cache_precos = precos
                cache_timestamp = time.time()
                return precos
        elif api == "coingecko":
            precos = await obter_precos_coingecko(cryptos)
            if precos:
                cache_precos = precos
                cache_timestamp = time.time()
                return precos
    return cache_precos if cache_precos else {}

async def obter_recomendacoes():
    dados = await obter_precos_com_fallback(config["cryptos"], config.get("api_priority", ["binance", "coingecko"]))
    recomendacoes = {}
    for crypto in config["cryptos"]:
        if crypto not in dados:
            recomendacoes[crypto] = {
                "preco": 0.0,
                "variacao": 0.0,
                "recomendacao": "⚠️ Dados indisponíveis",
            }
            continue

        info = dados[crypto]
        preco = info["usd"]
        variacao = info.get("usd_24h_change", 0)

        if preco < config["limite_investimento"] * 0.1:
            limite_ajustado = "MUITO BAIXO"
        elif preco < config["limite_investimento"] * 0.5:
            limite_ajustado = "BAIXO"
        elif preco < config["limite_investimento"]:
            limite_ajustado = "DENTRO DO LIMITE"
        else:
            limite_ajustado = "ACIMA DO LIMITE"

        if variacao > 8:
            acao = "📈 COMPRAR FORTE"
        elif variacao > 3:
            acao = "📈 COMPRAR MODERADO"
        elif variacao > 0:
            acao = "⚖️ OBSERVAR"
        elif variacao > -5:
            acao = "⚖️ MANTER"
        elif variacao > -10:
            acao = "📉 AGUARDAR QUEDA"
        else:
            acao = "📉 EVITAR"

        recomendacoes[crypto] = {
            "preco": preco,
            "variacao": variacao,
            "recomendacao": f"{acao} | {limite_ajustado}",
        }
    return recomendacoes

async def validar_cripto(nome):
    try:
        async with aiohttp.ClientSession() as session:
            mapa = {
                "bitcoin": "BTCUSDT", "ethereum": "ETHUSDT", "ripple": "XRPUSDT",
                "cardano": "ADAUSDT", "solana": "SOLUSDT", "dogecoin": "DOGEUSDT",
                "polkadot": "DOTUSDT", "litecoin": "LTCUSDT", "tron": "TRXUSDT",
            }
            if nome in mapa:
                url = f"https://api.binance.com/api/v3/ticker/price?symbol={mapa[nome]}"
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        return True
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={nome}&vs_currencies=usd"
            async with session.get(url, timeout=5) as resp:
                return resp.status == 200 and nome in await resp.json()
    except Exception:
        return False

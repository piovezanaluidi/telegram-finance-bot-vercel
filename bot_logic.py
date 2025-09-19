# bot_logic.py
import os, json
from datetime import datetime
import telebot
from upstash_redis import Redis

# ====== Config ======
TOKEN = "8122957124:AAEPoyWZ0cUyOkoV34RhGmhkGrffQY0dQQk"
bot = telebot.TeleBot(TOKEN, threaded=False)  # sem threads em serverless

# ====== Persistência (Upstash Redis) ======
redis = Redis(
    url=os.environ["UPSTASH_REDIS_REST_URL"],
    token=os.environ["UPSTASH_REDIS_REST_TOKEN"]
)

def carregar_dados():
    raw = redis.get("gastos")
    return json.loads(raw) if raw else []

def salvar_dados(dados):
    redis.set("gastos", json.dumps(dados))

def mes_atual():
    return datetime.now().strftime("%Y-%m")

# ====== Categorização (teu código) ======
def categorizar(descricao):
    desc = descricao.lower()
    if "sicoob" in desc: return "Cartão Sicoob"
    if "viacredi" in desc: return "Cartão Viacredi"
    if "magazine" in desc: return "Cartão Magazine"
    if "mercado" in desc: return "Mercado"
    if any(p in desc for p in ["lanche","padaria","ifood","almoço","janta","comida"]): return "Alimentação"
    if "seguro" in desc: return "Seguro"
    if any(p in desc for p in ["telefone","celular","tim","claro","vivo","oi"]): return "Telefonia"
    if any(p in desc for p in ["netflix","spotify","prime","youtube","hbo"]): return "Assinaturas"
    if any(p in desc for p in ["futebol","academia","pilates"]): return "Lazer/Fixo"
    if "compras" in desc or any(p in desc for p in ["roupa","tenis","sapato","shopping","magalu","eletrônico","celular","notebook"]): return "Compras"
    if any(p in desc for p in ["aluguel","luz","água","internet","wifi","net","fibra","gvt","claro net","oi fibra"]): return "Moradia"
    if any(p in desc for p in ["uber","gasolina","ônibus","carro"]): return "Transporte"
    if any(p in desc for p in ["salario","pagamento","recebi"]): return "Salário"
    return "Outros"

# ====== Handlers (iguais aos teus) ======
from telebot.types import Message

@bot.message_handler(func=lambda m: m.text and m.text.startswith("-"))
def registrar_gasto(message: Message):
    try:
        partes = message.text[1:].strip().split(" ", 1)
        valor = float(partes[0].replace(",", "."))
        descricao = partes[1] if len(partes) > 1 else "Sem descrição"
        categoria = categorizar(descricao)
        data = datetime.now().strftime("%Y-%m-%d %H:%M")
        dados = carregar_dados()
        dados.append({"tipo":"gasto","valor":valor,"descricao":descricao,"categoria":categoria,"data":data})
        salvar_dados(dados)
        bot.reply_to(message, f"💸 Gasto: R$ {valor:.2f} | {descricao} | {categoria}")
    except Exception:
        bot.reply_to(message, "⚠️ Formato inválido! Use: -35 pizza")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("+"))
def registrar_entrada(message: Message):
    try:
        partes = message.text[1:].strip().split(" ", 1)
        valor = float(partes[0].replace(",", "."))
        descricao = partes[1] if len(partes) > 1 else "Salário"
        data = datetime.now().strftime("%Y-%m-%d %H:%M")
        dados = carregar_dados()
        dados.append({"tipo":"entrada","valor":valor,"descricao":descricao,"categoria":"Salário","data":data})
        salvar_dados(dados)
        bot.reply_to(message, f"💰 Entrada: R$ {valor:.2f} | {descricao}")
    except Exception:
        bot.reply_to(message, "⚠️ Formato inválido! Use: +3800 salario")

@bot.message_handler(func=lambda m: m.text and m.text.upper() == "RESUMO")
def resumo(message: Message):
    dados = carregar_dados()
    mes = mes_atual()
    entradas = sum(d["valor"] for d in dados if d["tipo"]=="entrada" and d["data"].startswith(mes))
    gastos = sum(d["valor"] for d in dados if d["tipo"]=="gasto" and d["data"].startswith(mes))
    saldo = entradas - gastos
    bot.reply_to(message, f"📊 RESUMO ({mes}):\n💰 Entradas: R$ {entradas:.2f}\n💸 Gastos: R$ {gastos:.2f}\n📌 Saldo: R$ {saldo:.2f}")

@bot.message_handler(func=lambda m: m.text and m.text.upper() == "GASTOS")
def gastos(message: Message):
    dados = carregar_dados()
    mes = mes_atual()
    categorias, total = {}, 0
    for item in dados:
        if item["tipo"] == "gasto" and item["data"].startswith(mes):
            categorias[item["categoria"]] = categorias.get(item["categoria"], 0) + item["valor"]
            total += item["valor"]
    if not categorias:
        bot.reply_to(message, "Nenhum gasto registrado este mês.")
        return
    linhas = [f"{cat}: R$ {val:.2f}" for cat, val in categorias.items()]
    bot.reply_to(message, f"📊 GASTOS POR CATEGORIA ({mes}):\n\n" + "\n".join(linhas) + f"\n\n💸 Total Geral: R$ {total:.2f}")

@bot.message_handler(func=lambda m: m.text and m.text.upper() == "HISTORICO")
def historico(message: Message):
    dados = carregar_dados()
    if not dados:
        bot.reply_to(message, "Nenhum lançamento registrado.")
        return
    resposta = ["📋 HISTÓRICO (últimos 10):", ""]
    total = 0
    for idx, item in list(enumerate(dados))[-10:]:
        tipo = "Entrada" if item["tipo"] == "entrada" else "Gasto"
        resposta.append(f"[{idx+1}] {tipo} | R$ {item['valor']:.2f} | {item['descricao']} | {item['categoria']} | {item['data']}")
        if item["tipo"] == "gasto":
            total += item["valor"]
    resposta.append(f"\n💸 Total gastos nesses lançamentos: R$ {total:.2f}")
    bot.reply_to(message, "\n".join(resposta))

@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith("REMOVER"))
def remover(message: Message):
    try:
        partes = message.text.split()
        idx = int(partes[1]) - 1
        dados = carregar_dados()
        if idx < 0 or idx >= len(dados):
            bot.reply_to(message, "⚠️ Número inválido.")
            return
        removido = dados.pop(idx)
        salvar_dados(dados)
        bot.reply_to(message, f"❌ Removido: R$ {removido['valor']:.2f} | {removido['descricao']} | {removido['categoria']}")
    except Exception:
        bot.reply_to(message, "⚠️ Use assim: REMOVER 2")

@bot.message_handler(func=lambda m: m.text and m.text.upper() == "RESETAR")
def resetar(message: Message):
    salvar_dados([])
    bot.reply_to(message, "✅ Todos os registros foram apagados.")

@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith("CATEGORIA"))
def listar_categoria(message: Message):
    try:
        partes = message.text.split(" ", 1)
        if len(partes) < 2:
            bot.reply_to(message, "⚠️ Use assim: CATEGORIA Mercado")
            return
        nome = partes[1].strip()
        dados = carregar_dados()
        mes = mes_atual()
        filtro = [(i, d) for i, d in enumerate(dados) if d["tipo"]=="gasto" and d["data"].startswith(mes) and d["categoria"].lower()==nome.lower()]
        if not filtro:
            bot.reply_to(message, f"Nenhum lançamento na categoria {nome} este mês.")
            return
        linhas, total = [], 0
        for idx, item in filtro:
            linhas.append(f"[{idx+1}] - {item['data']} | R$ {item['valor']:.2f} | {item['descricao']}")
            total += item["valor"]
        linhas.append(f"\n💸 Total da categoria {nome}: R$ {total:.2f}")
        bot.reply_to(message, "📂 Lançamentos da categoria " + nome + f" ({mes}):\n\n" + "\n".join(linhas))
    except Exception:
        bot.reply_to(message, "⚠️ Erro ao listar categoria. Use: CATEGORIA Mercado")

@bot.message_handler(func=lambda m: m.text and m.text.upper() == "ENTRADAS")
def listar_entradas(message: Message):
    dados = carregar_dados()
    mes = mes_atual()
    filtro = [(i, d) for i, d in enumerate(dados) if d["tipo"]=="entrada" and d["data"].startswith(mes)]
    if not filtro:
        bot.reply_to(message, "Nenhuma entrada registrada este mês.")
        return
    linhas, total = [], 0
    for idx, item in filtro:
        linhas.append(f"[{idx+1}] - {item['data']} | R$ {item['valor']:.2f} | {item['descricao']}")
        total += item["valor"]
    linhas.append(f"\n💰 Total de entradas: R$ {total:.2f}")
    bot.reply_to(message, f"💰 Entradas registradas ({mes}):\n\n" + "\n".join(linhas))

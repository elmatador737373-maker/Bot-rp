import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import random
import datetime
import os
from flask import Flask
from threading import Thread

# -------------------- TOKEN --------------------
# Se usi Replit Secrets, leggere così:
TOKEN = os.environ['TOKEN']

# -------------------- BOT --------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# -------------------- DATABASE --------------------
conn = sqlite3.connect("rp.db")
c = conn.cursor()

# UTENTI
c.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    money INTEGER DEFAULT 1000
)""")

# INVENTARIO
c.execute("""CREATE TABLE IF NOT EXISTS inventory (
    user_id INTEGER,
    item TEXT,
    quantity INTEGER
)""")

# ITEM DISPONIBILI
c.execute("""CREATE TABLE IF NOT EXISTS items (
    name TEXT PRIMARY KEY,
    description TEXT
)""")

# DOCUMENTI
c.execute("""CREATE TABLE IF NOT EXISTS documents (
    user_id INTEGER,
    name TEXT,
    age TEXT,
    job TEXT
)""")

# TURNI
c.execute("""CREATE TABLE IF NOT EXISTS shifts (
    user_id INTEGER,
    start_time TEXT
)""")

# STIPENDI IN ATTESA APPROVAZIONE
c.execute("""CREATE TABLE IF NOT EXISTS pending_salary (
    user_id INTEGER,
    hours REAL,
    hourly_rate INTEGER
)""")

# FAZIONI
c.execute("""CREATE TABLE IF NOT EXISTS faction_accounts (
    faction TEXT PRIMARY KEY,
    balance INTEGER DEFAULT 0
)""")

# RUOLO SELEZIONATO UTENTE
c.execute("""CREATE TABLE IF NOT EXISTS active_roles (
    user_id INTEGER PRIMARY KEY,
    role_id INTEGER
)""")

conn.commit()

# -------------------- FUNZIONI BASE --------------------
def get_money(user_id):
    c.execute("SELECT money FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result:
        return result[0]
    else:
        c.execute("INSERT INTO users (user_id, money) VALUES (?, ?)", (user_id, 1000))
        conn.commit()
        return 1000

def add_money(user_id, amount):
    money = get_money(user_id)
    c.execute("UPDATE users SET money = ? WHERE user_id = ?", (money + amount, user_id))
    conn.commit()

def add_item(user_id, item, qty):
    c.execute("SELECT quantity FROM inventory WHERE user_id=? AND item=?", (user_id,item))
    result = c.fetchone()
    if result:
        c.execute("UPDATE inventory SET quantity=? WHERE user_id=? AND item=?",
                  (result[0]+qty, user_id, item))
    else:
        c.execute("INSERT INTO inventory VALUES (?,?,?)", (user_id,item,qty))
    conn.commit()

def get_faction_balance(faction):
    c.execute("SELECT balance FROM faction_accounts WHERE faction=?", (faction,))
    result = c.fetchone()
    if result:
        return result[0]
    else:
        c.execute("INSERT INTO faction_accounts(faction, balance) VALUES(?,?)", (faction, 0))
        conn.commit()
        return 0

def add_faction_balance(faction, amount):
    bal = get_faction_balance(faction)
    c.execute("UPDATE faction_accounts SET balance=? WHERE faction=?", (bal+amount, faction))
    conn.commit()

# -------------------- KEEP ALIVE FLASK --------------------
app = Flask('')

@app.route('/')
def home():
    return "Bot RP online"

def run():
    app.run(host='0.0.0.0', port=8080)

t = Thread(target=run)
t.start()

# -------------------- EVENT READY --------------------
@bot.event
async def on_ready():
    await tree.sync()
    print(f"{bot.user} online")

# -------------------- COMANDI ECONOMIA --------------------
@tree.command(name="saldo", description="Mostra il tuo saldo in banca")
async def saldo(interaction: discord.Interaction):
    money = get_money(interaction.user.id)
    embed = discord.Embed(title="💰 Saldo Bancario",
                          description=f"Saldo: **${money}**",
                          color=0x00ff00)
    await interaction.response.send_message(embed=embed)

@tree.command(name="paga", description="Paga un altro utente")
async def paga(interaction: discord.Interaction, utente: discord.Member, importo: int):
    if importo <= 0:
        return await interaction.response.send_message("Importo non valido", ephemeral=True)
    if get_money(interaction.user.id) < importo:
        return await interaction.response.send_message("Fondi insufficienti", ephemeral=True)
    add_money(interaction.user.id, -importo)
    add_money(utente.id, importo)
    embed = discord.Embed(title="💸 Transazione",
                          description=f"{interaction.user.mention} ha pagato ${importo} a {utente.mention}",
                          color=0x0099ff)
    await interaction.response.send_message(embed=embed)

@tree.command(name="setmoney", description="Imposta il saldo di un utente (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def setmoney(interaction: discord.Interaction, utente: discord.Member, importo: int):
    c.execute("UPDATE users SET money=? WHERE user_id=?", (importo, utente.id))
    conn.commit()
    await interaction.response.send_message("💼 Saldo aggiornato.")

# -------------------- INVENTARIO --------------------
@tree.command(name="inventario", description="Mostra il tuo inventario")
async def inventario(interaction: discord.Interaction):
    c.execute("SELECT item, quantity FROM inventory WHERE user_id=?", (interaction.user.id,))
    items = c.fetchall()
    desc = ""
    for item in items:
        desc += f"{item[0]} x{item[1]}\n"
    if desc == "":
        desc = "Inventario vuoto."
    embed = discord.Embed(title="🎒 Inventario", description=desc)
    await interaction.response.send_message(embed=embed)

@tree.command(name="additem", description="Aggiungi un item esistente a un utente (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def additem(interaction: discord.Interaction, utente: discord.Member, item: str, qty: int):
    c.execute("SELECT name FROM items WHERE name=?", (item,))
    if not c.fetchone():
        return await interaction.response.send_message("❌ Questo item non esiste.", ephemeral=True)
    add_item(utente.id, item, qty)
    await interaction.response.send_message(f"✅ {qty} {item} aggiunti a {utente.display_name}.")

# -------------------- NEGOZIO --------------------
@tree.command(name="apri_negozio", description="Mostra il negozio con tutti gli item disponibili")
async def apri_negozio(interaction: discord.Interaction):
    c.execute("SELECT name, description FROM items")
    items = c.fetchall()
    if not items:
        return await interaction.response.send_message("Il negozio è vuoto.", ephemeral=True)
    desc = ""
    for i in items:
        desc += f"**{i[0]}**: {i[1]}\n"
    embed = discord.Embed(title="🛒 Negozio RP", description=desc, color=0x00ff00)
    await interaction.response.send_message(embed=embed)

# -------------------- DOCUMENTI --------------------
@tree.command(name="crea_documento", description="Crea il tuo documento RP")
async def crea_documento(interaction: discord.Interaction, nome: str, eta: str, lavoro: str):
    c.execute("DELETE FROM documents WHERE user_id=?", (interaction.user.id,))
    c.execute("INSERT INTO documents VALUES (?,?,?,?)",
              (interaction.user.id, nome, eta, lavoro))
    conn.commit()
    await interaction.response.send_message("📄 Documento creato.")

@tree.command(name="mostra_documento", description="Mostra il documento di un utente")
async def mostra_documento(interaction: discord.Interaction, utente: discord.Member):
    c.execute("SELECT name, age, job FROM documents WHERE user_id=?", (utente.id,))
    doc = c.fetchone()
    if not doc:
        return await interaction.response.send_message("Nessun documento.")
    embed = discord.Embed(title="🪪 Documento",
                          description=f"Nome: {doc[0]}\nEtà: {doc[1]}\nLavoro: {doc[2]}",
                          color=0xcccccc)
    await interaction.response.send_message(embed=embed)

@tree.command(name="elimina_documento", description="Elimina il documento di un utente (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def elimina_documento(interaction: discord.Interaction, utente: discord.Member):
    c.execute("DELETE FROM documents WHERE user_id=?", (utente.id,))
    conn.commit()
    await interaction.response.send_message("Documento eliminato.")

# -------------------- /ME --------------------
@tree.command(name="me", description="Mostra un'azione RP")
async def me(interaction: discord.Interaction, azione: str):
    embed = discord.Embed(description=f"*{interaction.user.display_name} {azione}*",
                          color=0x999999)
    await interaction.response.send_message(embed=embed)

# -------------------- SPAZZATURA --------------------
@tree.command(name="cerca_spazzatura", description="Cerca materiali nella spazzatura")
async def cerca_spazzatura(interaction: discord.Interaction):
    materiali = ["Rame", "Vetro", "Plastica", "Ferro", "Componenti elettronici"]
    chance = random.randint(1,100)
    if chance <= 40:
        await interaction.response.send_message("🗑 Non hai trovato nulla.")
    elif chance <= 70:
        item = random.choice(materiali[:3])
        add_item(interaction.user.id, item, 1)
        await interaction.response.send_message(f"🗑 Hai trovato: {item}")
    elif chance <= 90:
        item = random.choice(materiali)
        add_item(interaction.user.id, item, 2)
        await interaction.response.send_message(f"🗑 Hai trovato materiale raro: {item} x2")
    else:
        add_item(interaction.user.id, "Oggetto speciale", 1)
        await interaction.response.send_message("🗑 Hai trovato un oggetto speciale!")

# -------------------- TURNI PERSONALIZZATI --------------------
@tree.command(name="seleziona_ruolo", description="Seleziona il tuo ruolo attivo per il turno")
async def seleziona_ruolo(interaction: discord.Interaction, ruolo: discord.Role):
    if ruolo not in interaction.user.roles:
        return await interaction.response.send_message("❌ Non hai questo ruolo.", ephemeral=True)
    c.execute("INSERT OR REPLACE INTO active_roles(user_id, role_id) VALUES (?,?)",
              (interaction.user.id, ruolo.id))
    conn.commit()
    await interaction.response.send_message(f"✅ Ruolo attivo per il turno: {ruolo.name}")

@tree.command(name="inizio_turno", description="Inizia il tuo turno lavorativo")
async def inizio_turno(interaction: discord.Interaction):
    c.execute("SELECT role_id FROM active_roles WHERE user_id=?", (interaction.user.id,))
    res = c.fetchone()
    if not res:
        return await interaction.response.send_message("❌ Devi prima selezionare un ruolo attivo con /seleziona_ruolo", ephemeral=True)
    role_id = res[0]
    if role_id not in [r.id for r in interaction.user.roles]:
        return await interaction.response.send_message("❌ Non hai il ruolo attivo.", ephemeral=True)
    c.execute("INSERT INTO shifts VALUES (?,?)", (interaction.user.id, str(datetime.datetime.now())))
    conn.commit()
    await interaction.response.send_message("🟢 Turno iniziato per il ruolo attivo.")

@tree.command(name="fine_turno", description="Termina il tuo turno lavorativo")
async def fine_turno(interaction: discord.Interaction, stipendio_orario: int):
    c.execute("SELECT role_id FROM active_roles WHERE user_id=?", (interaction.user.id,))
    res = c.fetchone()
    if not res:
        return await interaction.response.send_message("❌ Devi prima selezionare un ruolo attivo.", ephemeral=True)
    role_id = res[0]
    if role_id not in [r.id for r in interaction.user.roles]:
        return await interaction.response.send_message("❌ Non hai il ruolo attivo.", ephemeral=True)

    c.execute("SELECT start_time FROM shifts WHERE user_id=?", (interaction.user.id,))
    result = c.fetchone()
    if not result:
        return await interaction.response.send_message("⚠️ Non sei in turno.")
    
    start = datetime.datetime.fromisoformat(result[0])
    end = datetime.datetime.now()
    ore_lavorate = (end - start).total_seconds() / 3600

    c.execute("DELETE FROM shifts WHERE user_id=?", (interaction.user.id,))
    c.execute("INSERT INTO pending_salary VALUES (?,?,?)", (interaction.user.id, ore_lavorate, stipendio_orario))
    conn.commit()
    await interaction.response.send_message(f"🔴 Turno finito. Ore lavorate: {round(ore_lavorate,2)}\nStipendio di ${stipendio_orario}/h in attesa approvazione admin.")

@tree.command(name="approva_stipendio", description="Approva uno stipendio in attesa (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def approva_stipendio(interaction: discord.Interaction, utente: discord.Member):
    c.execute("SELECT hours, hourly_rate FROM pending_salary WHERE user_id=?", (utente.id,))
    res = c.fetchone()
    if not res:
        return await interaction.response.send_message("Nessun stipendio in attesa.")
    hours, rate = res
    totale = int(hours*rate)
    add_money(utente.id, totale)
    c.execute("DELETE FROM pending_salary WHERE user_id=?", (utente.id,))
    conn.commit()
    await interaction.response.send_message(f"Stipendio di ${totale} approvato per {utente.mention}.")

# -------------------- TELEFONO --------------------
class Telefono(discord.ui.View):
    @discord.ui.button(label="Saldo", style=discord.ButtonStyle.green)
    async def saldo_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"Saldo: ${get_money(interaction.user.id)}", ephemeral=True)

    @discord.ui.button(label="Inventario", style=discord.ButtonStyle.blurple)
    async def inv_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        c.execute("SELECT item, quantity FROM inventory WHERE user_id=?", (interaction.user.id,))
        items = c.fetchall()
        text = ""
        for i in items:
            text += f"{i[0]} x{i[1]}\n"
        if text == "":
            text = "Vuoto"
        await interaction.response.send_message(text, ephemeral=True)

@tree.command(name="telefono", description="Apri il tuo telefono RP")
async def telefono(interaction: discord.Interaction):
    embed = discord.Embed(title="📱 Smartphone RP",
                          description="Sistema operativo Los Santos OS",
                          color=0x111111)
    await interaction.response.send_message(embed=embed, view=Telefono())

# -------------------- RUN BOT --------------------
bot.run(TOKEN)

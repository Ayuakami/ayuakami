import discord
from discord.ext import commands
import asyncio
import datetime
import os
from aiohttp import web

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 🔧 IDs anpassen
GUILD_ID = 123456789012345678         # Deine Server-ID
VOICE_CHANNEL_ID = 234567890123456789 # Voice-Channel-ID
TEXT_CHANNEL_ID = 345678901234567890  # Text-Channel-ID

# Anmeldeliste
angemeldete = set()
MAX_ANMELDUNGEN = 10

def anmeldung_offen():
    """Nur zwischen xx:30 und xx:45 ist Anmeldung erlaubt."""
    now = datetime.datetime.now()
    return 30 <= now.minute < 45

class AnmeldungView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Anmelden", style=discord.ButtonStyle.green, custom_id="anmelden")
    async def anmelden(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not anmeldung_offen():
            await interaction.response.send_message(
                "⏳ Die Anmeldung ist aktuell geschlossen. Erlaubt nur von xx:30 bis xx:45.", ephemeral=True)
            return

        user_id = interaction.user.id
        if len(angemeldete) >= MAX_ANMELDUNGEN and user_id not in angemeldete:
            await interaction.response.send_message("❌ Es sind bereits 10 Personen angemeldet.", ephemeral=True)
            return

        if user_id in angemeldete:
            await interaction.response.send_message("✅ Du bist bereits angemeldet.", ephemeral=True)
            return

        angemeldete.add(user_id)
        guild = bot.get_guild(GUILD_ID)
        member = guild.get_member(user_id)
        voice_channel = guild.get_channel(VOICE_CHANNEL_ID)

        if member and voice_channel:
            try:
                await member.move_to(voice_channel)
            except Exception:
                pass

        await interaction.response.send_message("✅ Du wurdest angemeldet und verschoben.", ephemeral=True)

    @discord.ui.button(label="Abmelden", style=discord.ButtonStyle.red, custom_id="abmelden")
    async def abmelden(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in angemeldete:
            angemeldete.remove(user_id)
            await interaction.response.send_message("✅ Du wurdest abgemeldet.", ephemeral=True)
        else:
            await interaction.response.send_message("ℹ️ Du warst nicht angemeldet.", ephemeral=True)

    @discord.ui.button(label="Anzeigen der Angemeldeten", style=discord.ButtonStyle.grey, custom_id="anzeigen")
    async def anzeigen(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = bot.get_guild(GUILD_ID)
        if not angemeldete:
            await interaction.response.send_message("👥 Es sind derzeit keine Personen angemeldet.", ephemeral=True)
            return

        names = []
        for user_id in angemeldete:
            member = guild.get_member(user_id)
            names.append(member.display_name if member else f"<User {user_id}>")

        await interaction.response.send_message("👥 Angemeldete Personen:\n" + "\n".join(names), ephemeral=True)

async def send_40er_message():
    channel = bot.get_channel(TEXT_CHANNEL_ID)
    if channel:
        view = AnmeldungView()
        await channel.send("🟢 **40er Anmeldung geöffnet (xx:30 – xx:45)**", view=view)

async def timed_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.datetime.now()
        minute = now.minute

        if minute < 20:
            target_minute = 20
        elif minute < 30:
            target_minute = 30
        else:
            target_minute = 80  # nächste Stunde +20min
        next_run = now.replace(minute=target_minute % 60, second=0, microsecond=0)
        if target_minute >= 60:
            next_run += datetime.timedelta(hours=1)
        wait_seconds = (next_run - now).total_seconds()

        await asyncio.sleep(wait_seconds)

        current_minute = datetime.datetime.now().minute

        # xx:20 Uhr → Leute aus Voice-Channel entfernen
        if current_minute == 20:
            guild = bot.get_guild(GUILD_ID)
            for user_id in list(angemeldete):
                member = guild.get_member(user_id)
                if member and member.voice and member.voice.channel and member.voice.channel.id == VOICE_CHANNEL_ID:
                    try:
                        await member.move_to(None)
                    except Exception:
                        pass
            print("🔁 Alle User wurden um xx:20 aus dem Voice-Channel entfernt.")

        # xx:30 Uhr → Neue Anmeldung posten + Liste leeren
        elif current_minute == 30:
            angemeldete.clear()
            await send_40er_message()
            print("📨 Neue Anmeldung um xx:30 gepostet.")

@bot.command()
async def test(ctx):
    if ctx.channel.id != TEXT_CHANNEL_ID:
        await ctx.send("⚠️ Bitte nutze diesen Befehl im vorgesehenen Channel.")
        return
    await send_40er_message()
    await ctx.send("✅ Testnachricht gesendet.")

# Webserver für UptimeRobot:
async def handle(request):
    return web.Response(text="Bot läuft!")

app = web.Application()
app.add_routes([web.get('/', handle)])

async def start_webserver():
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

@bot.event
async def on_ready():
    print(f"✅ Bot ist online als {bot.user}")
    bot.loop.create_task(timed_task())
    bot.loop.create_task(start_webserver())

bot.run(os.getenv("BOT_TOKEN"))

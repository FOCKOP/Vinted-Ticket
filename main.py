import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime

# ─────────────────────────────────────────
#  CONFIGURATION — modifie ces valeurs
# ─────────────────────────────────────────
TOKEN = os.getenv("TOKEN")

# IDs à remplacer par les vrais IDs de ton serveur
GUILD_ID         = 1480209260360106045          # ID de ton serveur Discord
ADMIN_ROLE_ID    = 1484660893886185692          # Rôle admin / staff
ACHETEUR_ROLE_ID = 1484864396927963267          # Rôle donné après paiement
COMMANDES_CATEGORY_ID = 1484864877205127238     # Catégorie où créer les salons de commande
LOG_CHANNEL_ID        = 1484866153741553724     # Salon où tu reçois les récaps commandes (staff only)
ACHETEUR_CHANNEL_ID   = 1484864355672784959     # Salon "ma-commande" visible uniquement par les acheteurs

# ─────────────────────────────────────────
#  GRILLE DE PRIX (rang_départ → rang_cible)
#  Format : "DEPART-CIBLE": prix_en_euros
# ─────────────────────────────────────────
PRIX = {
    # League of Legends
    "Fer-Bronze":         16,
    "Fer-Argent":         30,
    "Fer-Or":             56,
    "Fer-Platine":        90,
    "Fer-Emeraude":      140,
    "Fer-Diamant":       200,
    "Bronze-Argent":      24,
    "Bronze-Or":          44,
    "Bronze-Platine":     76,
    "Bronze-Emeraude":   120,
    "Bronze-Diamant":    180,
    "Argent-Or":          30,
    "Argent-Platine":     56,
    "Argent-Emeraude":   100,
    "Argent-Diamant":    160,
    "Or-Platine":         36,
    "Or-Emeraude":        70,
    "Or-Diamant":        130,
    "Platine-Emeraude":   44,
    "Platine-Diamant":    90,
    "Emeraude-Diamant":   56,
    "Diamant-Maitre":    110,
    "Diamant-GrandMaitre": 180,
    "Diamant-Challenger":  300,
    "Maitre-GrandMaitre":  90,
    "Maitre-Challenger":   200,
    "GrandMaitre-Challenger": 130,
    # ── Valorant ───────────────────────────────────────
    "Fer-Bronze_VL":      20,
    "Fer-Argent_VL":      40,
    "Fer-Or_VL":          70,
    "Fer-Platine_VL":    110,
    "Fer-Diamant_VL":    170,
    "Fer-Ascendant_VL":  240,
    "Fer-Immortel_VL":   340,
    "Bronze-Argent_VL":   28,
    "Bronze-Or_VL":       50,
    "Bronze-Platine_VL":  84,
    "Bronze-Diamant_VL": 140,
    "Bronze-Ascendant_VL": 200,
    "Bronze-Immortel_VL": 290,
    "Argent-Or_VL":       36,
    "Argent-Platine_VL":  64,
    "Argent-Diamant_VL": 116,
    "Argent-Ascendant_VL": 176,
    "Argent-Immortel_VL": 260,
    "Or-Platine_VL":      40,
    "Or-Diamant_VL":      84,
    "Or-Ascendant_VL":   140,
    "Or-Immortel_VL":    220,
    "Platine-Diamant_VL": 56,
    "Platine-Ascendant_VL": 104,
    "Platine-Immortel_VL":  180,
    "Diamant-Ascendant_VL": 70,
    "Diamant-Immortel_VL":  136,
    "Ascendant-Immortel_VL": 84,
    # ── Warzone ────────────────────────────────────────
    "Bronze-Argent_WZ":   24,
    "Bronze-Or_WZ":       44,
    "Bronze-Platine_WZ":  76,
    "Bronze-Diamant_WZ": 116,
    "Bronze-Crimson_WZ": 170,
    "Bronze-Iridescent_WZ": 260,
    "Argent-Or_WZ":       30,
    "Argent-Platine_WZ":  56,
    "Argent-Diamant_WZ":  90,
    "Argent-Crimson_WZ": 144,
    "Argent-Iridescent_WZ": 220,
    "Or-Platine_WZ":      36,
    "Or-Diamant_WZ":      64,
    "Or-Crimson_WZ":     120,
    "Or-Iridescent_WZ":  190,
    "Platine-Diamant_WZ": 44,
    "Platine-Crimson_WZ": 96,
    "Platine-Iridescent_WZ": 160,
    "Diamant-Crimson_WZ": 70,
    "Diamant-Iridescent_WZ": 124,
    "Crimson-Iridescent_WZ": 84,
     # ── Fortnite ───────────────────────────────────────
    "Bronze-Argent_FN":   20,
    "Bronze-Or_FN":       36,
    "Bronze-Platine_FN":  60,
    "Bronze-Diamant_FN": 100,
    "Bronze-Elite_FN":   160,
    "Bronze-Champion_FN": 240,
    "Bronze-Unreal_FN":  360,
    "Argent-Or_FN":       24,
    "Argent-Platine_FN":  44,
    "Argent-Diamant_FN":  76,
    "Argent-Elite_FN":   136,
    "Argent-Champion_FN": 210,
    "Argent-Unreal_FN":  320,
    "Or-Platine_FN":      30,
    "Or-Diamant_FN":      56,
    "Or-Elite_FN":       110,
    "Or-Champion_FN":    180,
    "Or-Unreal_FN":      290,
    "Platine-Diamant_FN": 36,
    "Platine-Elite_FN":   84,
    "Platine-Champion_FN": 150,
    "Platine-Unreal_FN": 250,
    "Diamant-Elite_FN":   60,
    "Diamant-Champion_FN": 110,
    "Diamant-Unreal_FN": 200,
    "Elite-Champion_FN":  76,
    "Elite-Unreal_FN":   150,
    "Champion-Unreal_FN": 100,
    # ── Counter-strike 2 ───────────────────────────────
    "Argent1-Argent2_CS":  15,
    "Argent1-ArgentElite_CS": 25,
    "Argent1-Or1_CS":      40,
    "Argent1-MGNova_CS":   65,
    "Argent1-MG_CS":       90,
    "Argent1-DMG_CS":     130,
    "Argent1-LEM_CS":     170,
    "Argent1-SMFC_CS":    220,
    "Argent1-Global_CS":  280,
    "Argent2-ArgentElite_CS": 18,
    "Argent2-Or1_CS":      32,
    "Argent2-MGNova_CS":   55,
    "Argent2-MG_CS":       80,
    "Argent2-DMG_CS":     120,
    "Argent2-Global_CS":  260,
    "ArgentElite-Or1_CS":  22,
    "ArgentElite-MGNova_CS": 45,
    "ArgentElite-DMG_CS": 110,
    "ArgentElite-Global_CS": 240,
    "Or1-MGNova_CS":       35,
    "Or1-DMG_CS":          90,
    "Or1-Global_CS":      220,
    "MGNova-MG_CS":        20,
    "MGNova-DMG_CS":       65,
    "MGNova-Global_CS":   180,
    "MG-MGElite_CS":       18,
    "MG-DMG_CS":           50,
    "MG-Global_CS":       150,
    "MGElite-DMG_CS":      35,
    "MGElite-Global_CS":  130,
    "DMG-LEM_CS":          30,
    "DMG-Global_CS":      100,
    "LEM-SMFC_CS":         25,
    "LEM-Global_CS":       75,
    "SMFC-Global_CS":      50,
        # ── Clash royale ──────────────────
    "1-2_CR":    8,
    "1-3_CR":   14,
    "1-4_CR":   20,
    "1-5_CR":   28,
    "1-6_CR":   36,
    "1-7_CR":   46,
    "1-8_CR":   58,
    "1-9_CR":   70,
    "1-10_CR":  85,
    "1-11_CR": 100,
    "1-12_CR": 118,
    "1-13_CR": 138,
    "1-14_CR": 160,
    "1-15_CR": 185,
    "1-16_CR": 210,
    "2-3_CR":    8,
    "2-4_CR":   14,
    "2-5_CR":   22,
    "2-6_CR":   30,
    "2-7_CR":   40,
    "2-8_CR":   52,
    "2-9_CR":   64,
    "2-10_CR":  78,
    "2-11_CR":  94,
    "2-12_CR": 112,
    "2-13_CR": 132,
    "2-14_CR": 154,
    "2-15_CR": 178,
    "2-16_CR": 204,
    "3-4_CR":    8,
    "3-5_CR":   14,
    "3-6_CR":   22,
    "3-7_CR":   32,
    "3-8_CR":   44,
    "3-9_CR":   56,
    "3-10_CR":  70,
    "3-11_CR":  86,
    "3-12_CR": 104,
    "3-13_CR": 124,
    "3-14_CR": 146,
    "3-15_CR": 170,
    "3-16_CR": 196,
    "4-5_CR":    8,
    "4-6_CR":   14,
    "4-7_CR":   24,
    "4-8_CR":   36,
    "4-9_CR":   48,
    "4-10_CR":  62,
    "4-11_CR":  78,
    "4-12_CR":  96,
    "4-13_CR": 116,
    "4-14_CR": 138,
    "4-15_CR": 162,
    "4-16_CR": 188,
    "5-6_CR":    8,
    "5-7_CR":   16,
    "5-8_CR":   28,
    "5-9_CR":   40,
    "5-10_CR":  54,
    "5-11_CR":  70,
    "5-12_CR":  88,
    "5-13_CR": 108,
    "5-14_CR": 130,
    "5-15_CR": 154,
    "5-16_CR": 180,
    "6-7_CR":   10,
    "6-8_CR":   20,
    "6-9_CR":   32,
    "6-10_CR":  46,
    "6-11_CR":  62,
    "6-12_CR":  80,
    "6-13_CR": 100,
    "6-14_CR": 122,
    "6-15_CR": 146,
    "6-16_CR": 172,
    "7-8_CR":   12,
    "7-9_CR":   24,
    "7-10_CR":  38,
    "7-11_CR":  54,
    "7-12_CR":  72,
    "7-13_CR":  92,
    "7-14_CR": 114,
    "7-15_CR": 138,
    "7-16_CR": 164,
    "8-9_CR":   14,
    "8-10_CR":  28,
    "8-11_CR":  44,
    "8-12_CR":  62,
    "8-13_CR":  82,
    "8-14_CR": 104,
    "8-15_CR": 128,
    "8-16_CR": 154,
    "9-10_CR":  16,
    "9-11_CR":  32,
    "9-12_CR":  50,
    "9-13_CR":  70,
    "9-14_CR":  92,
    "9-15_CR": 116,
    "9-16_CR": 142,
    "10-11_CR": 18,
    "10-12_CR": 36,
    "10-13_CR": 56,
    "10-14_CR": 78,
    "10-15_CR": 102,
    "10-16_CR": 128,
    "11-12_CR": 20,
    "11-13_CR": 40,
    "11-14_CR": 62,
    "11-15_CR": 86,
    "11-16_CR": 114,
    "12-13_CR": 22,
    "12-14_CR": 44,
    "12-15_CR": 68,
    "12-16_CR": 94,
    "13-14_CR": 24,
    "13-15_CR": 48,
    "13-16_CR": 74,
    "14-15_CR": 26,
    "14-16_CR": 52,
    "15-16_CR": 30,
}

    # Ajoute autant de paliers que tu veux


RANGS_ORDRE = ["Fer", "Bronze", "Argent", "Or", "Platine", "Diamant", "Emeraude", "Maître", "Grand Maître", "Challenger"]

# ─────────────────────────────────────────
#  SETUP BOT
# ─────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Stockage des commandes en cours (en mémoire, remplace par une DB pour la prod)
commandes_en_cours = {}


# ─────────────────────────────────────────
#  UTILITAIRES
# ─────────────────────────────────────────
def calculer_prix(rang_depart: str, rang_cible: str) -> int | None:
    cle = f"{rang_depart}-{rang_cible}"
    return PRIX.get(cle, None)

def estimer_temps(rang_depart: str, rang_cible: str) -> str:
    if rang_depart not in RANGS_ORDRE or rang_cible not in RANGS_ORDRE:
        return "Inconnu"
    diff = RANGS_ORDRE.index(rang_cible) - RANGS_ORDRE.index(rang_depart)
    if diff <= 1:
        return "24-48h"
    elif diff <= 2:
        return "2-4 jours"
    elif diff <= 3:
        return "4-7 jours"
    else:
        return "1-2 semaines"

def sauvegarder_commandes():
    with open("commandes.json", "w") as f:
        json.dump(commandes_en_cours, f, indent=2, default=str)


# ─────────────────────────────────────────
#  RANGS PAR JEU
# ─────────────────────────────────────────
RANGS_PAR_JEU = {
    "League of Legends": ["Fer", "Bronze", "Argent", "Or", "Platine", "Emeraude", "Diamant", "Maitre", "GrandMaitre", "Challenger"],
    "Valorant":          ["Fer", "Bronze", "Argent", "Or", "Platine", "Diamant", "Ascendant", "Immortel"],
    "Warzone":           ["Bronze", "Argent", "Or", "Platine", "Diamant", "Crimson", "Iridescent"],
    "Fortnite":          ["Bronze", "Argent", "Or", "Platine", "Diamant", "Elite", "Champion", "Unreal"],
    "Counter-Strike 2":  ["Argent1", "Argent2", "ArgentElite", "Or1", "MGNova", "MG", "MGElite", "DMG", "LEM", "SMFC", "Global"],
    "Clash Royale":      ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16"],
}

SUFFIXES = {
    "League of Legends": "",
    "Valorant":          "_VL",
    "Warzone":           "_WZ",
    "Fortnite":          "_FN",
    "Counter-Strike 2":  "_CS",
    "Clash Royale":      "_CR",
}

# ─────────────────────────────────────────
#  VIEWS (boutons interactifs)
# ─────────────────────────────────────────

class BoutonCommencer(discord.ui.View):
    """Bouton dans le salon #shop pour démarrer une commande."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🛒 Commander un boost", style=discord.ButtonStyle.primary, custom_id="btn_commander")
    async def commander(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "**Étape 1/3** — Choisis ton jeu :",
            view=SelectJeu(),
            ephemeral=True
        )


class SelectJeu(discord.ui.View):
    """Menu déroulant pour choisir le jeu."""

    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.select(
        placeholder="🎮 Choisis ton jeu...",
        options=[discord.SelectOption(label=jeu, emoji="🎮") for jeu in RANGS_PAR_JEU.keys()]
    )
    async def select_jeu(self, interaction: discord.Interaction, select: discord.ui.Select):
        jeu = select.values[0]
        await interaction.response.edit_message(
            content=f"**Étape 2/3** — Choisis ton **rang actuel** pour {jeu} :",
            view=SelectRangDepart(jeu)
        )


class SelectRangDepart(discord.ui.View):
    """Menu déroulant pour choisir le rang de départ."""

    def __init__(self, jeu):
        super().__init__(timeout=300)
        self.jeu = jeu
        rangs = RANGS_PAR_JEU[jeu]
        options = [discord.SelectOption(label=r) for r in rangs]
        self.select_rang.options = options

    @discord.ui.select(placeholder="📊 Ton rang actuel...")
    async def select_rang(self, interaction: discord.Interaction, select: discord.ui.Select):
        rang_dep = select.values[0]
        await interaction.response.edit_message(
            content=f"**Étape 3/3** — Choisis ton **rang cible** pour {self.jeu} :",
            view=SelectRangCible(self.jeu, rang_dep)
        )


class SelectRangCible(discord.ui.View):
    """Menu déroulant pour choisir le rang cible."""

    def __init__(self, jeu, rang_dep):
        super().__init__(timeout=300)
        self.jeu = jeu
        self.rang_dep = rang_dep
        rangs = RANGS_PAR_JEU[jeu]
        # Filtrer les rangs inférieurs ou égaux au rang de départ
        idx = rangs.index(rang_dep) if rang_dep in rangs else 0
        options = [discord.SelectOption(label=r) for r in rangs[idx+1:]]
        if not options:
            options = [discord.SelectOption(label="Aucun rang supérieur")]
        self.select_rang.options = options

    @discord.ui.select(placeholder="🎯 Ton rang cible...")
    async def select_rang(self, interaction: discord.Interaction, select: discord.ui.Select):
        rang_cib = select.values[0]
        suffixe = SUFFIXES[self.jeu]
        cle = f"{self.rang_dep}-{rang_cib}{suffixe}"
        prix = PRIX.get(cle)
        temps = estimer_temps(self.rang_dep, rang_cib)

        if prix is None:
            await interaction.response.edit_message(
                content=f"❌ Combinaison **{self.rang_dep} → {rang_cib}** non disponible. Contacte un admin.",
                view=None
            )
            return


        embed = discord.Embed(title="💰 Estimation de ta commande", color=discord.Color.gold())
        embed.add_field(name="🎮 Jeu",          value=self.jeu,        inline=True)
        embed.add_field(name="📊 Rang actuel",  value=self.rang_dep,   inline=True)
        embed.add_field(name="🎯 Rang cible",   value=rang_cib,        inline=True)
        embed.add_field(name="💵 Prix estimé",  value=f"**{prix}€**",  inline=True)
        embed.add_field(name="⏱ Délai estimé", value=temps,           inline=True)
        embed.set_footer(text="⚠️ Prix final confirmé après validation du paiement.")

        view = BoutonConfirmerCommande(self.jeu, self.rang_dep, rang_cib, "", prix, temps)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class BoutonConfirmerCommande(discord.ui.View):
    """Bouton pour valider la commande après avoir vu le prix."""

    def __init__(self, jeu, rang_dep, rang_cib, pseudo, prix, temps):
        super().__init__(timeout=300)
        self.jeu = jeu
        self.rang_dep = rang_dep
        self.rang_cib = rang_cib
        self.pseudo = pseudo
        self.prix = prix
        self.temps = temps

    @discord.ui.button(label="✅ Confirmer et payer", style=discord.ButtonStyle.success)
    async def confirmer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"💳 **Instructions de paiement :**\n\n"
            f"Envoie **{self.prix}€** via PayPal / Lydia / Virement à :\n"
            f"> `https://www.paypal.com/ncp/payment/UMQWU3A8V4V76`\n\n"
`\n\n"
            f"Une fois le paiement effectué, clique sur le bouton ci-dessous pour le confirmer.",
            view=BoutonPaiementEffectue(self.jeu, self.rang_dep, self.rang_cib, self.pseudo, self.prix, self.temps),
            ephemeral=True
        )

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.danger)
    async def annuler(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Commande annulée.", ephemeral=True)


# Stockage des paiements en attente
paiements_en_attente = {}

class BoutonPaiementEffectue(discord.ui.View):
    def __init__(self, jeu, rang_dep, rang_cib, pseudo, prix, temps):
        super().__init__(timeout=600)
        self.jeu = jeu
        self.rang_dep = rang_dep
        self.rang_cib = rang_cib
        self.pseudo = pseudo
        self.prix = prix
        self.temps = temps

    @discord.ui.button(label="💳 J'ai payé !", style=discord.ButtonStyle.primary)
    async def paiement_ok(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        guild = interaction.guild

        # Message d'attente pour le client
        await interaction.response.edit_message(
            content=(
                "⏳ **Paiement en cours de vérification...**\n\n"
                "Un admin va confirmer ton paiement sous peu.\n"
                "Tu recevras un message dès que ce sera validé !\n\n"
                "⚠️ Ne ferme pas Discord."
            ),
            view=None
        )

        # Stocker le paiement en attente
        import random, string
        paiement_id = "PAY-" + "".join(random.choices(string.digits, k=6))
        paiements_en_attente[paiement_id] = {
            "user_id":  user.id,
            "jeu":      self.jeu,
            "rang_dep": self.rang_dep,
            "rang_cib": self.rang_cib,
            "pseudo":   self.pseudo,
            "prix":     self.prix,
            "temps":    self.temps
        }

        # Notif dans le salon admin
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="💳 Paiement à vérifier !",
                color=discord.Color.yellow()
            )
            embed.add_field(name="👤 Client",       value=f"{user.mention} (`{user.name}`)", inline=False)
            embed.add_field(name="🎮 Jeu",          value=self.jeu,      inline=True)
            embed.add_field(name="📊 Rang actuel",  value=self.rang_dep, inline=True)
            embed.add_field(name="🎯 Rang cible",   value=self.rang_cib, inline=True)
            embed.add_field(name="💵 Montant",      value=f"**{self.prix}€**", inline=True)
            embed.set_footer(text="Vérifie sur PayPal/Lydia que le paiement est bien reçu !")

            await log_channel.send(
                embed=embed,
                view=BoutonConfirmerPaiement(paiement_id, user.id)
            )


class BoutonConfirmerPaiement(discord.ui.View):
    def __init__(self, paiement_id, user_id):
        super().__init__(timeout=None)
        self.paiement_id = paiement_id
        self.user_id = user_id

    @discord.ui.button(label="✅ Confirmer le paiement", style=discord.ButtonStyle.success)
    async def confirmer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.paiement_id not in paiements_en_attente:
            await interaction.response.send_message("❌ Ce paiement a déjà été traité.", ephemeral=True)
            return

        data = paiements_en_attente.pop(self.paiement_id)
        guild = interaction.guild
        user = guild.get_member(data["user_id"])

        # Désactiver les boutons
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        await interaction.response.send_message(
            f"✅ Paiement de {user.mention} confirmé !", ephemeral=True
        )

        # Envoyer un DM au client pour entrer ses identifiants
        try:
            view_identifiants = BoutonEntrerIdentifiants(data)
            await user.send(
                "✅ **Ton paiement a été confirmé !**\n\n"
                "Clique sur le bouton ci-dessous pour entrer tes identifiants de connexion.",
                view=view_identifiants
            )
        except:
            pass

        # Créer la commande directement
        

    @discord.ui.button(label="❌ Refuser le paiement", style=discord.ButtonStyle.danger)
    async def refuser(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.paiement_id not in paiements_en_attente:
            await interaction.response.send_message("❌ Ce paiement a déjà été traité.", ephemeral=True)
            return

        data = paiements_en_attente.pop(self.paiement_id)
        guild = interaction.guild
        user = guild.get_member(data["user_id"])

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        await interaction.response.send_message(
            f"❌ Paiement de {user.mention} refusé.", ephemeral=True
        )

        try:
            await user.send(
                "❌ **Ton paiement n'a pas été validé.**\n\n"
                "Contacte un admin si tu penses qu'il y a une erreur."
            )
        except:
            pass

async def creer_commande(guild, user, data):
    """Crée la commande après confirmation du paiement."""
    num_commande = len(commandes_en_cours) + 1

    # Créer salon privé
    category = guild.get_channel(COMMANDES_CATEGORY_ID)
    nom_salon = f"commande-{num_commande:03d}-{user.name}"
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.get_role(ADMIN_ROLE_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    salon_commande = await guild.create_text_channel(
        name=nom_salon, category=category, overwrites=overwrites
    )

    # Message dans le salon de suivi
    embed_suivi = discord.Embed(
        title=f"📦 Commande #{num_commande:03d}",
        description=f"Bienvenue {user.mention} ! Voici le suivi de ta commande.",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    embed_suivi.add_field(name="🎮 Jeu",         value=data["jeu"],      inline=True)
    embed_suivi.add_field(name="📊 Rang actuel", value=data["rang_dep"], inline=True)
    embed_suivi.add_field(name="🎯 Rang cible",  value=data["rang_cib"], inline=True)
    embed_suivi.add_field(name="💵 Prix payé",   value=f"{data['prix']}€", inline=True)
    embed_suivi.add_field(name="🔄 Statut",      value="⏳ En attente d'un boosteur", inline=False)
    await salon_commande.send(embed=embed_suivi)

    # Message dans #ma-commande
    acheteur_channel = guild.get_channel(ACHETEUR_CHANNEL_ID)
    if acheteur_channel:
        acheteur_role = guild.get_role(ACHETEUR_ROLE_ID)
        if acheteur_role:
            await user.add_roles(acheteur_role)

        embed_client = discord.Embed(
            title=f"📦 Ta commande #{num_commande:03d} est enregistrée !",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        embed_client.add_field(name="🎮 Jeu",         value=data["jeu"],        inline=True)
        embed_client.add_field(name="📊 Rang actuel", value=data["rang_dep"],   inline=True)
        embed_client.add_field(name="🎯 Rang cible",  value=data["rang_cib"],   inline=True)
        embed_client.add_field(name="💵 Prix payé",   value=f"{data['prix']}€", inline=True)
        embed_client.add_field(name="🔄 Statut actuel", value="```⏳ En attente d'un boosteur```", inline=False)
        embed_client.add_field(name="📋 Suivi détaillé", value=salon_commande.mention, inline=False)

        msg = await acheteur_channel.send(content=f"{user.mention}", embed=embed_client)
        commandes_en_cours[str(num_commande)] = {
            "user_id":        user.id,
            "salon_id":       salon_commande.id,
            "msg_acheteur_id": msg.id,
            "jeu":            data["jeu"],
            "rang_dep":       data["rang_dep"],
            "rang_cib":       data["rang_cib"],
            "prix":           data["prix"],
            "statut":         "en_attente",
            "date":           str(datetime.utcnow())
        }
        sauvegarder_commandes()
class BoutonEntrerIdentifiants(discord.ui.View):
    def __init__(self, data):
        super().__init__(timeout=600)
        self.data = data

    @discord.ui.button(label="🔐 Entrer mes identifiants", style=discord.ButtonStyle.primary)
    async def entrer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ModalIdentifiants(
                self.data["jeu"],
                self.data["rang_dep"],
                self.data["rang_cib"],
                self.data["pseudo"],
                self.data["prix"],
                self.data["temps"]
            )
        )        
class ModalIdentifiants(discord.ui.Modal, title="🔐 Identifiants de connexion"):
    """Modal pour recueillir le compte du client après paiement."""

    identifiant = discord.ui.TextInput(
        label="Nom d'utilisateur / Email",
        placeholder="Ex: MonCompte123 ou email@exemple.com",
        required=True
    )
    mot_de_passe = discord.ui.TextInput(
        label="Mot de passe",
        placeholder="Ton mot de passe",
        required=True
    )

    def __init__(self, jeu, rang_dep, rang_cib, pseudo, prix, temps):
        super().__init__()
        self.jeu = jeu
        self.rang_dep = rang_dep
        self.rang_cib = rang_cib
        self.pseudo = pseudo
        self.prix = prix
        self.temps = temps

    async def on_submit(self, interaction: discord.Interaction):
        guild = bot.get_guild(GUILD_ID)
        user  = guild.get_member(interaction.user.id)

        # ── 1. Donner le rôle acheteur ──────────────────────────────────────
        acheteur_role = guild.get_role(ACHETEUR_ROLE_ID)
        if acheteur_role:
            await user.add_roles(acheteur_role)

        # ── 2. Créer le salon privé de suivi ────────────────────────────────
        category = guild.get_channel(COMMANDES_CATEGORY_ID)
        num_commande = len(commandes_en_cours) + 1
        nom_salon = f"commande-{num_commande:03d}-{user.name}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user:               discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.get_role(ADMIN_ROLE_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        salon_commande = await guild.create_text_channel(
            name=nom_salon,
            category=category,
            overwrites=overwrites,
            topic=f"Commande #{num_commande:03d} — {user.display_name}"
        )

        # ── 3. Message de suivi dans le salon de commande ───────────────────
        embed_suivi = discord.Embed(
            title=f"📦 Commande #{num_commande:03d}",
            description=f"Bienvenue {user.mention} ! Voici le suivi de ta commande.",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed_suivi.add_field(name="🎮 Jeu",          value=self.jeu,      inline=True)
        embed_suivi.add_field(name="📊 Rang actuel",  value=self.rang_dep, inline=True)
        embed_suivi.add_field(name="🎯 Rang cible",   value=self.rang_cib, inline=True)
        embed_suivi.add_field(name="💵 Prix payé",    value=f"{self.prix}€", inline=True)
        embed_suivi.add_field(name="⏱ Délai estimé", value=self.temps,    inline=True)
        embed_suivi.add_field(name="🔄 Statut",       value="⏳ En attente d'un boosteur", inline=False)
        embed_suivi.set_footer(text="⚠️ Ne joue pas sur ton compte pendant le boosting !")

        await salon_commande.send(embed=embed_suivi)
        await salon_commande.send(
            "📌 **Un staff va t'assigner un boosteur très prochainement.** Tu seras notifié ici dès qu'il prend en charge ta commande."
        )

        # ── 4. Poster / mettre à jour le salon #ma-commande (acheteurs) ───────
        acheteur_channel = guild.get_channel(ACHETEUR_CHANNEL_ID)
        if acheteur_channel:
            embed_client = discord.Embed(
                title=f"📦 Ta commande #{num_commande:03d} est enregistrée !",
                description=(
                    f"Bonjour {user.mention} 👋\n\n"
                    "Voici le récapitulatif complet de ta commande. "
                    "Tu peux suivre son avancement ici en temps réel."
                ),
                color=discord.Color.blurple(),
                timestamp=datetime.utcnow()
            )
            embed_client.add_field(name="🎮 Jeu",           value=self.jeu,               inline=True)
            embed_client.add_field(name="📊 Rang actuel",   value=self.rang_dep,           inline=True)
            embed_client.add_field(name="🎯 Rang cible",    value=self.rang_cib,           inline=True)
            embed_client.add_field(name="🕹️ Pseudo",        value=self.pseudo,             inline=True)
            embed_client.add_field(name="💵 Prix payé",     value=f"**{self.prix}€**",     inline=True)
            embed_client.add_field(name="⏱ Délai estimé",  value=self.temps,              inline=True)
            embed_client.add_field(
                name="🔄 Statut actuel",
                value="```⏳ En attente d'un boosteur```",
                inline=False
            )
            embed_client.add_field(
                name="📋 Suivi détaillé",
                value=salon_commande.mention,
                inline=False
            )
            embed_client.add_field(
                name="⚠️ Important",
                value=(
                    "• **Ne joue pas** sur ton compte pendant le boosting\n"
                    "• Tu seras **notifié ici et dans ton salon de suivi** à chaque étape\n"
                    "• En cas de problème, contacte un membre du staff"
                ),
                inline=False
            )
            embed_client.set_footer(text="Service de boosting — Commande sécurisée ✅")

            msg = await acheteur_channel.send(
                content=f"{user.mention}",
                embed=embed_client
            )
            # Stocker l'ID du message pour pouvoir le modifier plus tard
            commandes_en_cours[str(num_commande)] = commandes_en_cours.get(str(num_commande), {})
            commandes_en_cours[str(num_commande)]["msg_acheteur_id"] = msg.id

        # ── 5. Récap PRIVÉ pour les admins (avec identifiants) ──────────────
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed_admin = discord.Embed(
                title=f"🔔 Nouvelle commande #{num_commande:03d}",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed_admin.add_field(name="👤 Client",         value=f"{user.mention} (`{user.id}`)", inline=False)
            embed_admin.add_field(name="🎮 Jeu",            value=self.jeu,           inline=True)
            embed_admin.add_field(name="📊 Rang actuel",    value=self.rang_dep,      inline=True)
            embed_admin.add_field(name="🎯 Rang cible",     value=self.rang_cib,      inline=True)
            embed_admin.add_field(name="🕹️ Pseudo",         value=self.pseudo,        inline=True)
            embed_admin.add_field(name="💵 Prix",           value=f"{self.prix}€",    inline=True)
            embed_admin.add_field(name="⏱ Délai",          value=self.temps,         inline=True)
            embed_admin.add_field(name="🔑 Identifiant",   value=f"||`{self.identifiant.value}`||", inline=True)
            embed_admin.add_field(name="🔒 Mot de passe",  value=f"||`{self.mot_de_passe.value}`||", inline=True)
            embed_admin.add_field(name="📂 Salon",         value=salon_commande.mention, inline=False)
            embed_admin.set_footer(text="Informations sensibles — usage interne uniquement")

            view_admin = BoutonsAdmin(salon_commande.id, user.id, num_commande)
            await log_channel.send(embed=embed_admin, view=view_admin)

        # ── 6. Sauvegarder la commande ──────────────────────────────────────
        commandes_en_cours[str(num_commande)] = {
            "user_id":     user.id,
            "salon_id":    salon_commande.id,
            "jeu":         self.jeu,
            "rang_dep":    self.rang_dep,
            "rang_cib":    self.rang_cib,
            "pseudo":      self.pseudo,
            "prix":        self.prix,
            "statut":      "en_attente",
            "date":        str(datetime.utcnow())
        }
        sauvegarder_commandes()

        # ── 7. Confirmer au client ───────────────────────────────────────────
        await interaction.response.send_message(
            f"✅ **Commande enregistrée !**\n\n"
            f"Rends-toi dans {salon_commande.mention} pour suivre l'avancement.\n"
            f"⚠️ **Ne joue pas sur ton compte** pendant le boosting.",
            ephemeral=True
        )


class BoutonsAdmin(discord.ui.View):
    """Boutons dans le salon admin pour gérer la commande."""

    def __init__(self, salon_id, user_id, num_commande):
        super().__init__(timeout=None)
        self.salon_id = salon_id
        self.user_id = user_id
        self.num_commande = num_commande

    @discord.ui.button(label="✅ Marquer comme terminée", style=discord.ButtonStyle.success)
    async def terminer(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        salon = guild.get_channel(self.salon_id)
        user  = guild.get_member(self.user_id)

        if salon:
            embed_fin = discord.Embed(
                title="🎉 Boosting terminé !",
                description=(
                    f"Félicitations {user.mention if user else ''} !\n\n"
                    "Ton boosting est **terminé**. Tu peux récupérer ton compte.\n"
                    "N'oublie pas de **changer ton mot de passe** dès maintenant."
                ),
                color=discord.Color.green()
            )
            await salon.send(embed=embed_fin)

        # Mettre à jour le statut
        key = str(self.num_commande)
        if key in commandes_en_cours:
            commandes_en_cours[key]["statut"] = "terminee"
            sauvegarder_commandes()

            # Mettre à jour le message dans #ma-commande
            acheteur_channel = guild.get_channel(ACHETEUR_CHANNEL_ID)
            msg_id = commandes_en_cours[key].get("msg_acheteur_id")
            if acheteur_channel and msg_id:
                try:
                    msg = await acheteur_channel.fetch_message(msg_id)
                    embed = msg.embeds[0]
                    new_fields = []
                    for field in embed.fields:
                        if field.name == "🔄 Statut actuel":
                            new_fields.append(discord.EmbedField(
                                name="🔄 Statut actuel",
                                value="```✅ Boosting terminé — Tu peux récupérer ton compte !```",
                                inline=False
                            ))
                        else:
                            new_fields.append(field)
                    embed.clear_fields()
                    for f in new_fields:
                        embed.add_field(name=f.name, value=f.value, inline=f.inline)
                    embed.color = discord.Color.green()
                    embed.title = f"✅ Commande #{self.num_commande:03d} terminée !"
                    await msg.edit(embed=embed)
                except Exception:
                    pass

        await interaction.response.send_message(
            f"✅ Commande #{self.num_commande:03d} marquée comme terminée.", ephemeral=True
        )

        # Désactiver les boutons
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="🔄 En cours de boost", style=discord.ButtonStyle.primary)
    async def en_cours(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        salon = guild.get_channel(self.salon_id)
        user  = guild.get_member(self.user_id)

        if salon:
            await salon.send(
                f"🔄 {user.mention if user else ''} **Un boosteur a pris en charge ta commande !** "
                "Le boosting est en cours, ne joue pas sur ton compte. 🚫"
            )

        key = str(self.num_commande)
        if key in commandes_en_cours:
            commandes_en_cours[key]["statut"] = "en_cours"
            sauvegarder_commandes()

            # Mettre à jour le message dans #ma-commande
            acheteur_channel = guild.get_channel(ACHETEUR_CHANNEL_ID)
            msg_id = commandes_en_cours[key].get("msg_acheteur_id")
            if acheteur_channel and msg_id:
                try:
                    msg = await acheteur_channel.fetch_message(msg_id)
                    embed = msg.embeds[0]
                    # Remplacer le champ statut
                    new_fields = []
                    for field in embed.fields:
                        if field.name == "🔄 Statut actuel":
                            new_fields.append(discord.EmbedField(
                                name="🔄 Statut actuel",
                                value="```🚀 Boosting en cours — Ne joue pas sur ton compte !```",
                                inline=False
                            ))
                        else:
                            new_fields.append(field)
                    embed.clear_fields()
                    for f in new_fields:
                        embed.add_field(name=f.name, value=f.value, inline=f.inline)
                    embed.color = discord.Color.orange()
                    await msg.edit(embed=embed)
                except Exception:
                    pass

        await interaction.response.send_message("🔄 Statut mis à jour : en cours.", ephemeral=True)

    @discord.ui.button(label="❌ Annuler / Rembourser", style=discord.ButtonStyle.danger)
    async def annuler(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        salon = guild.get_channel(self.salon_id)
        user  = guild.get_member(self.user_id)

        if salon:
            await salon.send(
                f"❌ {user.mention if user else ''} Ta commande a été **annulée**. "
                "Un remboursement de 50% sera effectué sous 24-48h."
            )

        key = str(self.num_commande)
        if key in commandes_en_cours:
            commandes_en_cours[key]["statut"] = "annulee"
            sauvegarder_commandes()

        await interaction.response.send_message("❌ Commande annulée.", ephemeral=True)


# ─────────────────────────────────────────
#  COMMANDES SLASH
# ─────────────────────────────────────────

@tree.command(name="setup_shop", description="[ADMIN] Crée le message de shop avec le bouton de commande")
@app_commands.checks.has_role(ADMIN_ROLE_ID)
async def setup_shop(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🚀 Bienvenue dans notre service de Boosting",
        description=(
            "Nous te proposons un service de boosting rapide et fiable.\n\n"
            "**Comment ça marche ?**\n"
            "1️⃣ Clique sur **Commander un boost** ci-dessous\n"
            "2️⃣ Renseigne ton jeu, rang actuel et rang désiré\n"
            "3️⃣ Notre système calcule le prix automatiquement\n"
            "4️⃣ Procède au paiement\n"
            "5️⃣ Fournis tes identifiants en toute sécurité\n"
            "6️⃣ Suis l'avancement en temps réel !\n\n"
            "⚠️ **Important :** Ne joue pas sur ton compte pendant le boosting."
        ),
        color=discord.Color.gold()
    )
    embed.set_footer(text="Service professionnel — Boosteurs vérifiés")
    await interaction.channel.send(embed=embed, view=BoutonCommencer())
    await interaction.response.send_message("✅ Shop créé !", ephemeral=True)


@tree.command(name="commandes", description="[ADMIN] Voir toutes les commandes en cours")
@app_commands.checks.has_role(ADMIN_ROLE_ID)
async def voir_commandes(interaction: discord.Interaction):
    if not commandes_en_cours:
        await interaction.response.send_message("Aucune commande en cours.", ephemeral=True)
        return

    embed = discord.Embed(title="📋 Commandes en cours", color=discord.Color.blue())
    for num, data in commandes_en_cours.items():
        embed.add_field(
            name=f"#{num:>3} — {data['jeu']}",
            value=(
                f"**{data['rang_dep']} → {data['rang_cib']}** | {data['prix']}€\n"
                f"Statut : `{data['statut']}`"
            ),
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────
#  EVENTS
# ─────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ Bot connecté : {bot.user}")
    bot.add_view(BoutonCommencer())
    guild = discord.Object(id=GUILD_ID)
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)
    print("✅ Commandes slash synchronisées.")


# ─────────────────────────────────────────
#  LANCEMENT
# ─────────────────────────────────────────
bot.run(TOKEN)

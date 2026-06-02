import discord
from discord import app_commands
from discord.ext import commands
import os
import io
import smtplib
import random
import string
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────
TOKEN        = os.getenv("TOKEN")
SMTP_HOST    = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT    = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER    = os.getenv("SMTP_USER")    # ton adresse email expéditeur
SMTP_PASS    = os.getenv("SMTP_PASS")    # mot de passe app Gmail (ou autre)
GUILD_ID     = int(os.getenv("GUILD_ID", "0"))

# ─────────────────────────────────────────
#  BOT SETUP
# ─────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Sessions actives : user_id -> dict avec les données collectées
sessions: dict[int, dict] = {}


# ─────────────────────────────────────────
#  UTILITAIRES
# ─────────────────────────────────────────
def gen_numero() -> str:
    return "".join(random.choices(string.digits, k=8))


def envoyer_email(destinataire: str, sujet: str, corps: str, pdf_bytes: bytes, nom_fichier: str) -> bool:
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = destinataire
        msg["Subject"] = sujet
        msg.attach(MIMEText(corps, "plain", "utf-8"))

        part = MIMEBase("application", "octet-stream")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{nom_fichier}"')
        msg.attach(part)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, destinataire, msg.as_string())
        return True
    except Exception as e:
        print(f"[SMTP ERROR] {e}")
        return False


# ─────────────────────────────────────────
#  GÉNÉRATION PDF — TICKET DE CAISSE
# ─────────────────────────────────────────
def generer_ticket(data: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=(8 * cm, 25 * cm),
        rightMargin=0.5 * cm,
        leftMargin=0.5 * cm,
        topMargin=0.5 * cm,
        bottomMargin=0.5 * cm,
    )

    styles = getSampleStyleSheet()
    bold_center = ParagraphStyle("bc", parent=styles["Normal"], alignment=TA_CENTER, fontName="Helvetica-Bold")
    center = ParagraphStyle("c", parent=styles["Normal"], alignment=TA_CENTER, fontSize=8)
    small = ParagraphStyle("s", parent=styles["Normal"], fontSize=7)

    elems = []

    # En-tête
    elems.append(Paragraph(data["marque"].upper(), bold_center))
    elems.append(Spacer(1, 3))
    elems.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    elems.append(Spacer(1, 3))

    now = datetime.now()
    elems.append(Paragraph(f"Date : {now.strftime('%d/%m/%Y  %H:%M')}", small))
    elems.append(Paragraph(f"Ticket n° {data['numero']}", small))
    elems.append(Paragraph(f"Client : {data['prenom']} {data['nom'].upper()}", small))
    elems.append(Spacer(1, 5))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elems.append(Spacer(1, 5))

    # Articles
    table_data = [["Article", "Qté", "P.U.", "Total"]]
    total_ttc = 0.0
    for art in data["articles"]:
        ligne_total = art["quantite"] * art["prix_unitaire"]
        total_ttc += ligne_total
        table_data.append([
            art["nom"],
            str(art["quantite"]),
            f"{art['prix_unitaire']:.2f}€",
            f"{ligne_total:.2f}€",
        ])

    t = Table(table_data, colWidths=[3 * cm, 1 * cm, 1.5 * cm, 1.5 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.lightgrey]),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.grey),
        ("ALIGN",       (1, 1), (-1, -1), "RIGHT"),
    ]))
    elems.append(t)

    elems.append(Spacer(1, 5))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))

    tva_rate = data.get("tva", 20.0)
    ht = total_ttc / (1 + tva_rate / 100)
    tva_montant = total_ttc - ht

    resume = Table([
        ["Sous-total HT", f"{ht:.2f}€"],
        [f"TVA ({tva_rate:.0f}%)", f"{tva_montant:.2f}€"],
        ["TOTAL TTC", f"{total_ttc:.2f}€"],
    ], colWidths=[4.5 * cm, 2.5 * cm])
    resume.setStyle(TableStyle([
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ALIGN",       (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME",    (0, 2), (-1, 2),  "Helvetica-Bold"),
        ("LINEABOVE",   (0, 2), (-1, 2),  0.5, colors.black),
    ]))
    elems.append(resume)

    elems.append(Spacer(1, 8))
    mode = data.get("paiement", "Carte bancaire")
    elems.append(Paragraph(f"Mode de paiement : {mode}", small))
    elems.append(Spacer(1, 10))
    elems.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    elems.append(Spacer(1, 5))
    elems.append(Paragraph("Merci de votre achat !", bold_center))
    elems.append(Paragraph(data["marque"], center))

    doc.build(elems)
    return buf.getvalue()


# ─────────────────────────────────────────
#  GÉNÉRATION PDF — FACTURE
# ─────────────────────────────────────────
def generer_facture(data: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm,
                             topMargin=2 * cm, bottomMargin=2 * cm)

    styles = getSampleStyleSheet()
    titre_style = ParagraphStyle("titre", parent=styles["Title"], fontSize=22, textColor=colors.HexColor("#2C3E50"))
    h2 = ParagraphStyle("h2", parent=styles["Normal"], fontSize=11, fontName="Helvetica-Bold",
                         textColor=colors.HexColor("#2C3E50"))
    normal = styles["Normal"]
    right = ParagraphStyle("right", parent=normal, alignment=TA_RIGHT)

    elems = []

    # En-tête
    header_data = [
        [Paragraph(data["marque"].upper(), titre_style), ""],
        [Paragraph(data.get("adresse_emetteur", ""), normal),
         Paragraph(f"<b>FACTURE N°</b> {data['numero']}", right)],
        ["", Paragraph(f"Date : {datetime.now().strftime('%d/%m/%Y')}", right)],
        ["", Paragraph(f"Échéance : {data.get('echeance', '30 jours')}", right)],
    ]
    header_table = Table(header_data, colWidths=[9 * cm, 9 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("SPAN",   (0, 0), (1, 0)),
    ]))
    elems.append(header_table)
    elems.append(Spacer(1, 20))

    # Infos client
    elems.append(Paragraph("Facturé à :", h2))
    elems.append(Spacer(1, 4))
    client_data = [
        [f"{data['prenom']} {data['nom'].upper()}"],
        [data.get("adresse_client", "")],
        [data.get("email_client", "")],
        [data.get("siret_client", "")],
    ]
    client_table = Table([[Paragraph(row[0], normal)] for row in client_data if row[0]],
                          colWidths=[10 * cm])
    client_table.setStyle(TableStyle([
        ("BOX",        (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0),  colors.HexColor("#ECF0F1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elems.append(client_table)
    elems.append(Spacer(1, 20))

    # Tableau articles
    elems.append(Paragraph("Détail des prestations", h2))
    elems.append(Spacer(1, 6))

    table_data = [["Description", "Quantité", "Prix unitaire HT", "TVA", "Total TTC"]]
    total_ttc = 0.0
    for art in data["articles"]:
        tva_r = art.get("tva", data.get("tva", 20.0))
        prix_ttc = art["prix_unitaire"] * (1 + tva_r / 100)
        ligne_total = art["quantite"] * prix_ttc
        total_ttc += ligne_total
        table_data.append([
            art["nom"],
            str(art["quantite"]),
            f"{art['prix_unitaire']:.2f} €",
            f"{tva_r:.0f}%",
            f"{ligne_total:.2f} €",
        ])

    col_widths = [7 * cm, 2 * cm, 3.5 * cm, 2 * cm, 3.5 * cm]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  colors.HexColor("#2C3E50")),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F3F4")]),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.grey),
        ("ALIGN",       (1, 1), (-1, -1), "RIGHT"),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elems.append(t)
    elems.append(Spacer(1, 15))

    # Totaux
    tva_rate = data.get("tva", 20.0)
    ht = total_ttc / (1 + tva_rate / 100)
    tva_montant = total_ttc - ht

    totaux = Table([
        ["Sous-total HT",   f"{ht:.2f} €"],
        [f"TVA ({tva_rate:.0f}%)", f"{tva_montant:.2f} €"],
        ["TOTAL TTC",       f"{total_ttc:.2f} €"],
    ], colWidths=[12 * cm, 6 * cm])
    totaux.setStyle(TableStyle([
        ("FONTSIZE",    (0, 0), (-1, -1), 10),
        ("ALIGN",       (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME",    (0, 2), (-1, 2),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 2), (-1, 2),  12),
        ("BACKGROUND",  (0, 2), (-1, 2),  colors.HexColor("#2C3E50")),
        ("TEXTCOLOR",   (0, 2), (-1, 2),  colors.white),
        ("TOPPADDING",  (0, 2), (-1, 2),  8),
        ("BOTTOMPADDING", (0, 2), (-1, 2), 8),
        ("LINEABOVE",   (0, 2), (-1, 2),  1, colors.black),
    ]))
    elems.append(totaux)

    # Mentions légales
    elems.append(Spacer(1, 30))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elems.append(Spacer(1, 6))
    mentions = data.get("mentions", "Paiement à réception. Tout retard entraîne des pénalités de 3× le taux légal.")
    elems.append(Paragraph(mentions, ParagraphStyle("tiny", parent=normal, fontSize=7, textColor=colors.grey)))

    doc.build(elems)
    return buf.getvalue()


# ─────────────────────────────────────────
#  MODALS
# ─────────────────────────────────────────

class ModalArticle(discord.ui.Modal, title="Ajouter un article"):
    nom_article = discord.ui.TextInput(label="Nom de l'article", placeholder="Ex: Chemise bleue")
    quantite    = discord.ui.TextInput(label="Quantité", placeholder="1", default="1", max_length=4)
    prix_ht     = discord.ui.TextInput(label="Prix unitaire HT (€)", placeholder="Ex: 29.99")

    def __init__(self, type_doc: str):
        super().__init__()
        self.type_doc = type_doc

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        try:
            qte = int(self.quantite.value)
            prix = float(self.prix_ht.value.replace(",", "."))
        except ValueError:
            await interaction.response.send_message(
                "❌ Quantité ou prix invalide.", ephemeral=True
            )
            return

        sessions[uid]["articles"].append({
            "nom": self.nom_article.value,
            "quantite": qte,
            "prix_unitaire": prix,
        })

        articles = sessions[uid]["articles"]
        total = sum(a["quantite"] * a["prix_unitaire"] for a in articles)
        tva = sessions[uid].get("tva", 20.0)
        total_ttc = total * (1 + tva / 100) if self.type_doc == "facture" else total

        lignes = "\n".join(
            f"• {a['nom']} × {a['quantite']} = {a['quantite'] * a['prix_unitaire']:.2f}€"
            for a in articles
        )
        await interaction.response.send_message(
            f"✅ Article ajouté !\n\n**Articles :**\n{lignes}\n\n"
            f"**Total {'TTC' if self.type_doc == 'ticket' else 'HT'} :** {total:.2f}€"
            + (f"\n**Total TTC :** {total_ttc:.2f}€" if self.type_doc == "facture" else ""),
            view=ViewArticles(self.type_doc),
            ephemeral=True,
        )


class ModalInfosTicket(discord.ui.Modal, title="Informations — Ticket de caisse"):
    marque  = discord.ui.TextInput(label="Nom de la boutique / marque", placeholder="Ex: Ma Boutique")
    prenom  = discord.ui.TextInput(label="Prénom du client")
    nom     = discord.ui.TextInput(label="Nom du client")
    email   = discord.ui.TextInput(label="Email (pour recevoir le ticket)", placeholder="client@email.com")
    paiement = discord.ui.TextInput(label="Mode de paiement", placeholder="Carte bancaire / Espèces / …", default="Carte bancaire")

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        sessions[uid] = {
            "type": "ticket",
            "marque": self.marque.value,
            "prenom": self.prenom.value,
            "nom": self.nom.value,
            "email": self.email.value,
            "paiement": self.paiement.value,
            "tva": 20.0,
            "articles": [],
            "numero": gen_numero(),
        }
        await interaction.response.send_message(
            f"✅ Infos enregistrées pour **{self.prenom.value} {self.nom.value}** "
            f"— boutique **{self.marque.value}**.\n\nAjoute maintenant tes articles :",
            view=ViewArticles("ticket"),
            ephemeral=True,
        )


class ModalInfosFacture(discord.ui.Modal, title="Informations — Facture"):
    marque          = discord.ui.TextInput(label="Nom de votre entreprise / marque")
    adresse_emetteur = discord.ui.TextInput(label="Votre adresse (optionnel)", required=False, placeholder="1 rue de la Paix, 75001 Paris")
    prenom          = discord.ui.TextInput(label="Prénom du client")
    nom             = discord.ui.TextInput(label="Nom du client")
    email           = discord.ui.TextInput(label="Email client (pour recevoir la facture)", placeholder="client@email.com")

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        sessions[uid] = {
            "type": "facture",
            "marque": self.marque.value,
            "adresse_emetteur": self.adresse_emetteur.value or "",
            "prenom": self.prenom.value,
            "nom": self.nom.value,
            "email": self.email.value,
            "tva": 20.0,
            "articles": [],
            "numero": f"FAC-{gen_numero()}",
            "echeance": "30 jours",
            "adresse_client": "",
            "siret_client": "",
            "mentions": "Paiement à réception. Tout retard entraîne des pénalités de 3× le taux légal.",
        }
        await interaction.response.send_message(
            f"✅ Facture créée pour **{self.prenom.value} {self.nom.value}** "
            f"— entreprise **{self.marque.value}**.\n\nAjoute maintenant tes articles / prestations :",
            view=ViewArticles("facture"),
            ephemeral=True,
        )


# ─────────────────────────────────────────
#  VIEW ARTICLES (boutons après chaque article)
# ─────────────────────────────────────────

class ViewArticles(discord.ui.View):
    def __init__(self, type_doc: str):
        super().__init__(timeout=600)
        self.type_doc = type_doc

    @discord.ui.button(label="➕ Ajouter un article", style=discord.ButtonStyle.primary)
    async def ajouter(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalArticle(self.type_doc))

    @discord.ui.button(label="✅ Générer & Envoyer par mail", style=discord.ButtonStyle.success)
    async def generer(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        data = sessions.get(uid)

        if not data or not data["articles"]:
            await interaction.response.send_message(
                "❌ Aucun article ajouté.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if data["type"] == "ticket":
                pdf_bytes = generer_ticket(data)
                nom_fichier = f"ticket_{data['numero']}.pdf"
                sujet = f"Votre ticket de caisse — {data['marque']}"
                corps = (
                    f"Bonjour {data['prenom']} {data['nom']},\n\n"
                    f"Veuillez trouver ci-joint votre ticket de caisse pour votre achat chez {data['marque']}.\n\n"
                    f"Merci de votre confiance !\n\n{data['marque']}"
                )
            else:
                pdf_bytes = generer_facture(data)
                nom_fichier = f"facture_{data['numero']}.pdf"
                sujet = f"Votre facture {data['numero']} — {data['marque']}"
                corps = (
                    f"Bonjour {data['prenom']} {data['nom']},\n\n"
                    f"Veuillez trouver ci-joint votre facture n° {data['numero']}.\n\n"
                    f"Cordialement,\n{data['marque']}"
                )

            # Envoyer l'email
            email_ok = envoyer_email(data["email"], sujet, corps, pdf_bytes, nom_fichier)

            # Envoyer le PDF aussi dans Discord (en DM)
            discord_file = discord.File(io.BytesIO(pdf_bytes), filename=nom_fichier)
            try:
                await interaction.user.send(
                    f"📄 Voici votre {'ticket de caisse' if data['type'] == 'ticket' else 'facture'} :",
                    file=discord_file,
                )
                dm_ok = True
            except Exception:
                dm_ok = False

            total = sum(a["quantite"] * a["prix_unitaire"] for a in data["articles"])
            tva = data.get("tva", 20.0)
            total_ttc = total * (1 + tva / 100) if data["type"] == "facture" else total

            msg = (
                f"✅ **{'Ticket de caisse' if data['type'] == 'ticket' else 'Facture'} généré{'e' if data['type'] == 'facture' else ''} !**\n\n"
                f"📋 **N°** : `{data['numero']}`\n"
                f"👤 **Client** : {data['prenom']} {data['nom']}\n"
                f"🏪 **{'Boutique' if data['type'] == 'ticket' else 'Entreprise'}** : {data['marque']}\n"
                f"💰 **Total** : `{total_ttc:.2f}€`\n\n"
            )
            msg += f"{'✅' if email_ok else '❌'} Email envoyé à `{data['email']}`\n"
            msg += f"{'✅' if dm_ok else '⚠️'} PDF envoyé en DM Discord\n"

            if not email_ok:
                msg += "\n⚠️ L'envoi d'email a échoué — vérifiez la configuration SMTP."

            del sessions[uid]
            await interaction.followup.send(msg, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Erreur lors de la génération : `{e}`", ephemeral=True)

    @discord.ui.button(label="🗑️ Annuler", style=discord.ButtonStyle.danger)
    async def annuler(self, interaction: discord.Interaction, button: discord.ui.Button):
        sessions.pop(interaction.user.id, None)
        await interaction.response.send_message("❌ Opération annulée.", ephemeral=True)


# ─────────────────────────────────────────
#  VUE PRINCIPALE — choix ticket ou facture
# ─────────────────────────────────────────

class ViewChoix(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🧾 Ticket de caisse", style=discord.ButtonStyle.primary, custom_id="btn_ticket")
    async def ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalInfosTicket())

    @discord.ui.button(label="📄 Facture", style=discord.ButtonStyle.secondary, custom_id="btn_facture")
    async def facture(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalInfosFacture())


# ─────────────────────────────────────────
#  COMMANDES SLASH
# ─────────────────────────────────────────

@tree.command(name="documents", description="Crée un ticket de caisse ou une facture et l'envoie par email")
async def documents(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📄 Générateur de documents",
        description=(
            "Choisis le type de document à créer :\n\n"
            "🧾 **Ticket de caisse** — reçu simple (petit format)\n"
            "📄 **Facture** — document professionnel A4\n\n"
            "Le document sera généré en PDF et envoyé par email au client,"
            " ainsi qu'en DM Discord."
        ),
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed, view=ViewChoix(), ephemeral=True)


@tree.command(name="setup_documents", description="[ADMIN] Poste le panneau de génération de documents dans ce salon")
@app_commands.default_permissions(administrator=True)
async def setup_documents(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📄 Générateur de documents",
        description=(
            "Clique sur un bouton pour créer un document :\n\n"
            "🧾 **Ticket de caisse** — reçu de vente (format thermique)\n"
            "📄 **Facture** — document comptable A4\n\n"
            "Le PDF sera envoyé par **email** et en **DM Discord**."
        ),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="Powered by votre bot Discord")
    await interaction.channel.send(embed=embed, view=ViewChoix())
    await interaction.response.send_message("✅ Panneau posté !", ephemeral=True)


# ─────────────────────────────────────────
#  EVENTS
# ─────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ Bot connecté : {bot.user}")
    bot.add_view(ViewChoix())
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
        print("✅ Commandes slash synchronisées (guild).")
    else:
        await tree.sync()
        print("✅ Commandes slash synchronisées (global).")


# ─────────────────────────────────────────
#  LANCEMENT
# ─────────────────────────────────────────
bot.run(TOKEN)

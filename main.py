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
from reportlab.graphics.barcode import code128

def _load_env(path=".env"):
    if not os.path.exists(path):
        path = ".env.example"
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

_load_env()

TOKEN        = os.getenv("TOKEN")
SMTP_HOST    = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT    = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER    = os.getenv("SMTP_USER", "")
SMTP_PASS    = os.getenv("SMTP_PASS", "")
GUILD_ID     = int(os.getenv("GUILD_ID", "0"))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

sessions: dict[int, dict] = {}


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


TICKET_STYLES = {
    "luxe": {
        "label":       "💎 Luxe (LV, Chanel, Dior…)",
        "header_font": "Times-Bold",
        "header_sz":   22,
        "spacing":     True,
    },
    "standard": {
        "label":       "🛍️ Standard (Zara, Nike, Sephora…)",
        "header_font": "Helvetica-Bold",
        "header_sz":   18,
        "spacing":     False,
    },
    "restaurant": {
        "label":       "🍔 Restaurant / Supermarché",
        "header_font": "Courier-Bold",
        "header_sz":   14,
        "spacing":     False,
    },
}


def _spaced(text: str) -> str:
    return "  ".join(text.upper())

def generer_ticket(data: dict) -> bytes:
    style_key = data.get("style", "standard")
    s = TICKET_STYLES.get(style_key, TICKET_STYLES["standard"])

    W_PAGE = 8 * cm
    n_art = len(data["articles"])
    extra_addr = len(data["adresse"].split(",")) * 0.4 if data.get("adresse") else 0.0
    page_h = (14.5 + 1.2 * n_art + extra_addr) * cm

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=(W_PAGE, page_h),
        rightMargin=0.5 * cm,
        leftMargin=0.5 * cm,
        topMargin=0.6 * cm,
        bottomMargin=0.6 * cm,
    )
    W = W_PAGE - 1.0 * cm
    now = datetime.now()
    tva_rate = data.get("tva", 20.0)
    BODY = "Courier"
    BODY_B = "Courier-Bold"
    SZ = 7

    def p(text, font=BODY, size=SZ, align=TA_LEFT):
        st = ParagraphStyle("_", fontName=font, fontSize=size, alignment=align, leading=size + 2)
        return Paragraph(text, st)

    def sep(char="-"):
        return p(char * 42, align=TA_CENTER)

    elems = []

    nom = _spaced(data["marque"]) if s["spacing"] else data["marque"].upper()
    elems.append(p(nom, font=s["header_font"], size=s["header_sz"], align=TA_CENTER))
    elems.append(Spacer(1, 3))
    if data.get("adresse"):
        for ligne in data["adresse"].split(","):
            elems.append(p(ligne.strip(), align=TA_CENTER))
    elems.append(Spacer(1, 4))
    elems.append(sep("-"))
    elems.append(Spacer(1, 4))

    store_num  = "".join(random.choices(string.digits, k=5))
    reg_num    = "".join(random.choices(string.digits, k=2))
    cashier    = "".join(random.choices(string.ascii_uppercase, k=5))
    client_id  = "".join(random.choices(string.digits, k=13))
    trans_num  = data["numero"]

    info = Table([
        [p(f"Trans # : {trans_num}", BODY_B), p(f"Date : {now.strftime('%d/%m/%Y')}", align=TA_RIGHT)],
        [p(f"Store  : {store_num}"),           p(f"Heure : {now.strftime('%H:%M:%S')}", align=TA_RIGHT)],
        [p(f"Caissier : {cashier}"),            p(f"Register : {reg_num}", align=TA_RIGHT)],
    ], colWidths=[W * 0.55, W * 0.45])
    info.setStyle(TableStyle([
        ("FONTSIZE", (0,0),(-1,-1), SZ),
        ("TOPPADDING", (0,0),(-1,-1), 1),
        ("BOTTOMPADDING", (0,0),(-1,-1), 1),
    ]))
    elems.append(info)
    elems.append(p(f"Customer : {data['prenom']} {data['nom'].upper()}"))
    elems.append(p(f"Customer ID : {client_id}"))
    elems.append(Spacer(1, 4))
    elems.append(sep("-"))
    elems.append(Spacer(1, 3))

    elems.append(p("ARTICLE          QTE  PRIX    MONTANT", BODY_B))
    elems.append(sep("-"))

    total_ttc = 0.0
    for art in data["articles"]:
        code_art = "".join(random.choices(string.digits, k=9))
        ligne_total = art["quantite"] * art["prix_unitaire"]
        total_ttc += ligne_total
        qte = str(art["quantite"]).rjust(3)
        pu  = f"{art['prix_unitaire']:.2f}".rjust(7)
        tot = f"{ligne_total:.2f}".rjust(9)
        elems.append(p(f"{code_art}"))
        elems.append(p(art["nom"], BODY_B))
        elems.append(p(f"  {qte}  {pu}  {tot}"))
    elems.append(Spacer(1, 4))
    elems.append(sep("-"))

    ht  = total_ttc / (1 + tva_rate / 100)
    tva = total_ttc - ht
    mode = data.get("paiement", "Carte bancaire")
    monnaie = "EUR"

    totaux = [
        ("SOUS-TOTAL HT", f"{monnaie}  {ht:.2f}"),
        (f"TVA {tva_rate:.0f}%",       f"{monnaie}  {tva:.2f}"),
        ("",              ""),
        ("TOTAL (EUR)",   f"{monnaie}  {total_ttc:.2f}"),
    ]
    for label, val in totaux:
        if not label:
            elems.append(Spacer(1, 3))
            continue
        row = Table([[p(label, BODY_B if "TOTAL" in label else BODY),
                      p(val, BODY_B if "TOTAL" in label else BODY, align=TA_RIGHT)]],
                    colWidths=[W*0.55, W*0.45])
        row.setStyle(TableStyle([
            ("TOPPADDING",    (0,0),(-1,-1), 1),
            ("BOTTOMPADDING", (0,0),(-1,-1), 1),
            ("LINEABOVE", (0,0),(-1,0), 0.5 if "TOTAL (EUR)" in label else 0, colors.black),
        ]))
        elems.append(row)

    elems.append(Spacer(1, 4))
    elems.append(sep("-"))

    pmt = Table([
        [p(mode.upper(), BODY_B), p(f"EUR  {total_ttc:.2f}", BODY_B, align=TA_RIGHT)],
        [p("MONNAIE RENDUE"),     p("EUR   0.00", align=TA_RIGHT)],
    ], colWidths=[W*0.55, W*0.45])
    pmt.setStyle(TableStyle([
        ("FONTSIZE", (0,0),(-1,-1), SZ),
        ("TOPPADDING",    (0,0),(-1,-1), 1),
        ("BOTTOMPADDING", (0,0),(-1,-1), 1),
    ]))
    elems.append(pmt)
    elems.append(Spacer(1, 4))
    elems.append(sep("-"))

    nb = len(data["articles"])
    elems.append(Spacer(1, 3))
    elems.append(p(f"NOMBRE D'ARTICLES VENDUS = {nb}"))
    elems.append(Spacer(1, 6))

    if data.get("siret"):
        elems.append(p(f"SIRET : {data['siret']}", align=TA_CENTER))

    elems.append(Spacer(1, 4))
    elems.append(p("J'accepte de payer le montant ci-dessus", align=TA_CENTER))
    elems.append(p("conformement a mon accord porteur de carte.", align=TA_CENTER))
    elems.append(Spacer(1, 10))

    barcode_val = "".join(random.choices(string.digits + string.ascii_uppercase, k=12))
    try:
        bc_ref = code128.Code128(barcode_val, barHeight=1.5*cm, barWidth=1.0, humanReadable=False)
        scale = W / bc_ref.width
        bc = code128.Code128(barcode_val, barHeight=1.5*cm, barWidth=scale, humanReadable=True)
        bc.hAlign = "CENTER"
        elems.append(Spacer(1, 4))
        elems.append(bc)
    except Exception:
        elems.append(p(barcode_val, align=TA_CENTER))

    doc.build(elems)
    return buf.getvalue()


def generer_facture(data: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                             topMargin=2*cm, bottomMargin=2*cm)

    C = colors.HexColor("#1B2A4A")
    C2 = colors.HexColor("#F0F4FA")

    styles = getSampleStyleSheet()
    N = styles["Normal"]

    def fp(name, font="Helvetica", size=9, align=TA_LEFT, color=colors.black, leading=None):
        return ParagraphStyle(name, fontName=font, fontSize=size, alignment=align,
                               textColor=color, leading=leading or size + 3)

    elems = []
    now = datetime.now()
    W = 17 * cm

    brand_cell = Table(
        [[Paragraph(data["marque"].upper(), fp("b1","Helvetica-Bold",20,TA_LEFT,colors.white)),
          Paragraph(f"<b>FACTURE</b><br/>N° {data['numero']}", fp("b2","Helvetica-Bold",12,TA_RIGHT,colors.white))]],
        colWidths=[W*0.6, W*0.4]
    )
    brand_cell.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), C),
        ("TOPPADDING",    (0,0),(-1,-1), 14),
        ("BOTTOMPADDING", (0,0),(-1,-1), 14),
        ("LEFTPADDING",   (0,0),(0,-1), 12),
        ("RIGHTPADDING",  (1,0),(1,-1), 12),
        ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
    ]))
    elems.append(brand_cell)
    elems.append(Spacer(1, 12))

    adr_emetteur = data.get("adresse_emetteur", "")
    siret = data.get("siret", "")
    tva_intra = data.get("tva_intra", "")
    date_str = now.strftime("%d/%m/%Y")
    echeance = data.get("echeance", "30 jours")

    emetteur_lines = [data["marque"]]
    if adr_emetteur:
        emetteur_lines.append(adr_emetteur)
    if siret:
        emetteur_lines.append(f"SIRET : {siret}")
    if tva_intra:
        emetteur_lines.append(f"N° TVA : {tva_intra}")

    client_lines = [f"{data['prenom']} {data['nom'].upper()}"]
    if data.get("adresse_client"):
        client_lines.append(data["adresse_client"])
    client_lines.append(data.get("email", ""))

    def info_block(titre, lignes, couleur_titre=C):
        rows = [[Paragraph(titre, fp("t", "Helvetica-Bold", 8, color=couleur_titre))]]
        for l in lignes:
            if l:
                rows.append([Paragraph(l, fp("l", size=8))])
        tbl = Table(rows, colWidths=[W*0.45])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(0,0), C2),
            ("TOPPADDING",    (0,0),(-1,-1), 3),
            ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ("LEFTPADDING",   (0,0),(-1,-1), 6),
            ("BOX", (0,0),(-1,-1), 0.5, colors.HexColor("#CCCCCC")),
        ]))
        return tbl

    meta_rows = [
        ["Date d'émission :", date_str],
        ["Échéance :", echeance],
    ]
    meta_tbl = Table(meta_rows, colWidths=[W*0.18, W*0.2])
    meta_tbl.setStyle(TableStyle([
        ("FONTNAME", (0,0),(0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0),(-1,-1), 8),
        ("TEXTCOLOR",(0,0),(0,-1), colors.HexColor("#555555")),
        ("TOPPADDING",    (0,0),(-1,-1), 2),
        ("BOTTOMPADDING", (0,0),(-1,-1), 2),
    ]))

    header2 = Table(
        [[info_block("ÉMETTEUR", emetteur_lines),
          "",
          info_block("FACTURÉ À", client_lines)]],
        colWidths=[W*0.45, W*0.1, W*0.45]
    )
    header2.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")]))
    elems.append(header2)
    elems.append(Spacer(1, 6))
    elems.append(meta_tbl)
    elems.append(Spacer(1, 16))

    art_header = ["Description", "Qté", "P.U. HT", "TVA", "Total TTC"]
    rows = [art_header]
    total_ht_global = 0.0
    total_tva_global = 0.0
    total_ttc_global = 0.0

    for art in data["articles"]:
        tva_r = art.get("tva", data.get("tva", 20.0))
        pu_ht = art["prix_unitaire"]
        qte = art["quantite"]
        ligne_ht = qte * pu_ht
        ligne_tva = ligne_ht * tva_r / 100
        ligne_ttc = ligne_ht + ligne_tva
        total_ht_global  += ligne_ht
        total_tva_global += ligne_tva
        total_ttc_global += ligne_ttc
        rows.append([
            art["nom"], str(qte),
            f"{pu_ht:.2f} €", f"{tva_r:.0f}%",
            f"{ligne_ttc:.2f} €",
        ])

    col_w = [W*0.38, W*0.08, W*0.18, W*0.1, W*0.18]
    art_tbl = Table(rows, colWidths=col_w, repeatRows=1)
    art_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,0),  C),
        ("TEXTCOLOR",    (0,0),(-1,0),  colors.white),
        ("FONTNAME",     (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0,0),(-1,-1), 9),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, C2]),
        ("ALIGN",        (1,0),(-1,-1), "RIGHT"),
        ("TOPPADDING",   (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING",  (0,0),(0,-1),  6),
        ("LINEBELOW",    (0,-1),(-1,-1), 0.5, colors.HexColor("#CCCCCC")),
        ("LINEBELOW",    (0,0),(-1,0),   0, colors.white),
    ]))
    elems.append(art_tbl)
    elems.append(Spacer(1, 12))

    totaux_data = [
        ["Sous-total HT",      f"{total_ht_global:.2f} €"],
        [f"TVA ({data.get('tva',20):.0f}%)", f"{total_tva_global:.2f} €"],
    ]
    totaux_tbl = Table(totaux_data, colWidths=[W*0.78, W*0.22])
    totaux_tbl.setStyle(TableStyle([
        ("FONTNAME",  (0,0),(-1,-1), "Helvetica"),
        ("FONTSIZE",  (0,0),(-1,-1), 9),
        ("ALIGN",     (1,0),(1,-1),  "RIGHT"),
        ("TEXTCOLOR", (0,0),(-1,-1), colors.HexColor("#555555")),
        ("TOPPADDING",    (0,0),(-1,-1), 2),
        ("BOTTOMPADDING", (0,0),(-1,-1), 2),
    ]))
    elems.append(totaux_tbl)

    total_ligne = Table([["TOTAL TTC", f"{total_ttc_global:.2f} €"]], colWidths=[W*0.78, W*0.22])
    total_ligne.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), C),
        ("TEXTCOLOR",     (0,0),(-1,-1), colors.white),
        ("FONTNAME",      (0,0),(-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 12),
        ("ALIGN",         (1,0),(1,-1),  "RIGHT"),
        ("TOPPADDING",    (0,0),(-1,-1), 8),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ("LEFTPADDING",   (0,0),(0,-1),  8),
        ("RIGHTPADDING",  (1,0),(1,-1),  8),
    ]))
    elems.append(total_ligne)
    elems.append(Spacer(1, 20))

    mode = data.get("paiement", "Virement bancaire")
    elems.append(Paragraph("Modalités de paiement", fp("pm_h","Helvetica-Bold",9,color=C)))
    elems.append(Spacer(1, 3))
    elems.append(Paragraph(f"Mode : {mode}  —  Échéance : {echeance}", fp("pm_d", size=8, color=colors.HexColor("#444444"))))
    elems.append(Spacer(1, 20))

    elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC")))
    elems.append(Spacer(1, 6))
    mentions = (
        "Paiement a reception. Tout retard de paiement entraine des penalites de 3 fois le taux d'interet legal "
        "ainsi qu'une indemnite forfaitaire pour frais de recouvrement de 40 EUR (Art. L441-10 C. com.). "
        "TVA acquittee sur les encaissements."
    )
    if siret:
        mentions = f"SIRET : {siret}  —  " + mentions
    elems.append(Paragraph(mentions, fp("men", size=7, color=colors.HexColor("#888888"))))

    doc.build(elems)
    return buf.getvalue()


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
            await interaction.response.send_message("❌ Quantité ou prix invalide.", ephemeral=True)
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
    marque   = discord.ui.TextInput(label="Nom de la boutique / marque", placeholder="Ex: ZARA, Louis Vuitton…")
    adresse  = discord.ui.TextInput(label="Adresse de la boutique (optionnel)", required=False, placeholder="22 Av. des Champs-Elysées, 75008 Paris")
    client   = discord.ui.TextInput(label="Prénom NOM du client", placeholder="Jean DUPONT")
    email    = discord.ui.TextInput(label="Email client", placeholder="client@email.com")
    paiement = discord.ui.TextInput(label="Mode de paiement", placeholder="Carte Visa / Espèces / PayPal…", default="Carte bancaire")

    def __init__(self, style: str = "standard"):
        super().__init__()
        self.style = style

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        parts = self.client.value.strip().split(" ", 1)
        prenom = parts[0]
        nom = parts[1] if len(parts) > 1 else ""
        sessions[uid] = {
            "type": "ticket",
            "style": self.style,
            "marque": self.marque.value,
            "adresse": self.adresse.value or "",
            "prenom": prenom,
            "nom": nom,
            "email": self.email.value,
            "paiement": self.paiement.value,
            "tva": 20.0,
            "articles": [],
            "numero": gen_numero(),
        }
        style_label = TICKET_STYLES[self.style]["label"]
        await interaction.response.send_message(
            f"✅ **{self.marque.value}** — style *{style_label}*\n"
            f"Client : **{self.client.value}**\n\nAjoute maintenant les articles :",
            view=ViewArticles("ticket"),
            ephemeral=True,
        )


class ModalInfosFacture(discord.ui.Modal, title="Informations — Facture"):
    marque   = discord.ui.TextInput(label="Votre entreprise / marque")
    siret    = discord.ui.TextInput(label="SIRET + N° TVA (optionnel)", required=False, placeholder="Ex: 123 456 789 00012 — FR12 123456789")
    client   = discord.ui.TextInput(label="Prénom NOM du client", placeholder="Jean DUPONT")
    email    = discord.ui.TextInput(label="Email client", placeholder="client@email.com")
    adresse  = discord.ui.TextInput(label="Votre adresse (optionnel)", required=False, placeholder="1 rue de la Paix, 75001 Paris")

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        parts = self.client.value.strip().split(" ", 1)
        prenom = parts[0]
        nom = parts[1] if len(parts) > 1 else ""

        siret_raw = self.siret.value or ""
        siret_val = ""
        tva_intra = ""
        if "—" in siret_raw:
            sp = siret_raw.split("—", 1)
            siret_val = sp[0].strip()
            tva_intra = sp[1].strip()
        elif siret_raw:
            siret_val = siret_raw.strip()

        sessions[uid] = {
            "type": "facture",
            "marque": self.marque.value,
            "adresse_emetteur": self.adresse.value or "",
            "siret": siret_val,
            "tva_intra": tva_intra,
            "prenom": prenom,
            "nom": nom,
            "email": self.email.value,
            "paiement": "Virement bancaire",
            "tva": 20.0,
            "articles": [],
            "numero": f"FAC-{gen_numero()}",
            "echeance": "30 jours",
            "adresse_client": "",
        }
        await interaction.response.send_message(
            f"✅ Facture pour **{self.client.value}** — entreprise **{self.marque.value}**\n\n"
            f"Ajoute maintenant les articles / prestations :",
            view=ViewArticles("facture"),
            ephemeral=True,
        )


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
            await interaction.response.send_message("❌ Aucun article ajouté.", ephemeral=True)
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

            email_ok = envoyer_email(data["email"], sujet, corps, pdf_bytes, nom_fichier)

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


class ViewStyleTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="💎 Luxe", style=discord.ButtonStyle.secondary)
    async def luxe(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalInfosTicket("luxe"))

    @discord.ui.button(label="🛍️ Standard", style=discord.ButtonStyle.primary)
    async def standard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalInfosTicket("standard"))

    @discord.ui.button(label="🍔 Restaurant / Supermarché", style=discord.ButtonStyle.secondary)
    async def restaurant(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalInfosTicket("restaurant"))


class ViewChoix(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🧾 Ticket de caisse", style=discord.ButtonStyle.primary, custom_id="btn_ticket")
    async def ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "**Quel style de ticket ?**\n\n"
            "💎 **Luxe** — LV, Chanel, Dior, Hermès…\n"
            "🛍️ **Standard** — Zara, Nike, Sephora, H&M…\n"
            "🍔 **Restaurant / Supermarché** — McDonald's, Carrefour, Lidl…",
            view=ViewStyleTicket(),
            ephemeral=True,
        )

    @discord.ui.button(label="📄 Facture", style=discord.ButtonStyle.secondary, custom_id="btn_facture")
    async def facture(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalInfosFacture())


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


bot.run(TOKEN)

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

# ─────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────
TOKEN        = os.getenv("TOKEN")
SMTP_HOST    = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT    = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER    = os.getenv("SMTP_USER", "")
SMTP_PASS    = os.getenv("SMTP_PASS", "")
GUILD_ID     = int(os.getenv("GUILD_ID", "0"))

# ─────────────────────────────────────────
#  BOT SETUP
# ─────────────────────────────────────────
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

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
#  STYLES DE TICKETS (header uniquement)
# ─────────────────────────────────────────
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


# ─────────────────────────────────────────
#  GÉNÉRATION PDF — TICKET DE CAISSE
# ─────────────────────────────────────────
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

    # ── NOM DE MARQUE ───────────────────────
    nom = _spaced(data["marque"]) if s["spacing"] else data["marque"].upper()
    elems.append(p(nom, font=s["header_font"], size=s["header_sz"], align=TA_CENTER))
    elems.append(Spacer(1, 3))
    if data.get("adresse"):
        for ligne in data["adresse"].split(","):
            elems.append(p(ligne.strip(), align=TA_CENTER))
    elems.append(Spacer(1, 4))
    elems.append(sep("-"))
    elems.append(Spacer(1, 4))

    # ── INFOS TRANSACTION ─────────────────────
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

    # ── EN-TÊTE ARTICLES ────────────────────
    elems.append(p("ARTICLE          QTE  PRIX    MONTANT", BODY_B))
    elems.append(sep("-"))

    # ── ARTICLES ──────────────────────────
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

    # ── TOTAUX ────────────────────────────
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

    # ── PAIEMENT ──────────────────────────
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

    # ── INFOS FINALES ─────────────────────
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

    # ── CODE-BARRES pleine largeur ────────────
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


# ─────────────────────────────────────────
#  GÉNÉRATION PDF — FACTURE
# ─────────────────────────────────────────
def generer_facture(data: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                             topMargin=1.5*cm, bottomMargin=1.5*cm)

    C    = colors.HexColor("#1B2A4A")   # bleu marine principal
    C2   = colors.HexColor("#F0F4FA")   # fond léger
    CGREY = colors.HexColor("#6B7280")
    CBORDER = colors.HexColor("#D1D5DB")

    def fp(name, font="Helvetica", size=9, align=TA_LEFT, color=colors.black, leading=None):
        return ParagraphStyle(name, fontName=font, fontSize=size, alignment=align,
                               textColor=color, leading=leading or size + 3)

    elems = []
    now = datetime.now()
    W = 17 * cm

    adr_emetteur = data.get("adresse_emetteur", "")
    siret        = data.get("siret", "")
    tva_intra    = data.get("tva_intra", "")
    echeance     = data.get("echeance", "30 jours")
    mode         = data.get("paiement", "Virement bancaire")
    date_str     = now.strftime("%d/%m/%Y")
    numero       = data["numero"]

    # ── BANDE ENTÊTE ────────────────────────────────────
    left_content = [
        Paragraph(data["marque"].upper(),
                  fp("h1", "Helvetica-Bold", 22, TA_LEFT, colors.white)),
    ]
    if adr_emetteur:
        left_content.append(Spacer(1, 3))
        left_content.append(Paragraph(adr_emetteur,
                  fp("ha", "Helvetica", 8, TA_LEFT, colors.HexColor("#BFD0E8"))))
    if siret:
        left_content.append(Paragraph(f"SIRET : {siret}",
                  fp("hs", "Helvetica", 7, TA_LEFT, colors.HexColor("#BFD0E8"))))
    if tva_intra:
        left_content.append(Paragraph(f"N° TVA : {tva_intra}",
                  fp("ht", "Helvetica", 7, TA_LEFT, colors.HexColor("#BFD0E8"))))

    right_content = [
        Paragraph("FACTURE", fp("fac", "Helvetica-Bold", 28, TA_RIGHT, colors.white)),
        Spacer(1, 4),
        Paragraph(f"N° {numero}",
                  fp("fn", "Helvetica-Bold", 10, TA_RIGHT, colors.HexColor("#BFD0E8"))),
        Paragraph(f"Date : {date_str}",
                  fp("fd", "Helvetica", 8, TA_RIGHT, colors.HexColor("#BFD0E8"))),
        Paragraph(f"Échéance : {echeance}",
                  fp("fe", "Helvetica", 8, TA_RIGHT, colors.HexColor("#BFD0E8"))),
    ]

    from reportlab.platypus import KeepInFrame
    header_tbl = Table(
        [[left_content, right_content]],
        colWidths=[W * 0.55, W * 0.45]
    )
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), C),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0),(-1,-1), 16),
        ("BOTTOMPADDING", (0,0),(-1,-1), 16),
        ("LEFTPADDING",   (0,0),(0,-1),  14),
        ("RIGHTPADDING",  (1,0),(1,-1),  14),
    ]))
    elems.append(header_tbl)
    elems.append(Spacer(1, 14))

    # ── ÉMETTEUR / DESTINATAIRE ─────────────────────────
    def info_block(titre, lignes):
        inner = [Paragraph(titre, fp("it", "Helvetica-Bold", 7, color=C))]
        for l in lignes:
            if l:
                inner.append(Paragraph(l, fp("il", size=8, leading=11)))
        tbl = Table([[inner]], colWidths=[W * 0.44])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,0), C2),
            ("TOPPADDING",    (0,0),(-1,-1), 4),
            ("BOTTOMPADDING", (0,0),(-1,-1), 4),
            ("LEFTPADDING",   (0,0),(-1,-1), 7),
            ("RIGHTPADDING",  (0,0),(-1,-1), 7),
            ("BOX",           (0,0),(-1,-1), 0.5, CBORDER),
        ]))
        return tbl

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
    if data.get("email"):
        client_lines.append(data["email"])

    addr_row = Table(
        [[info_block("DE", emetteur_lines), "", info_block("FACTURÉ À", client_lines)]],
        colWidths=[W * 0.44, W * 0.12, W * 0.44]
    )
    addr_row.setStyle(TableStyle([("VALIGN", (0,0),(-1,-1), "TOP")]))
    elems.append(addr_row)
    elems.append(Spacer(1, 18))

    # ── TABLEAU ARTICLES ──────────────────────────────
    art_header = ["Description", "Qté", "P.U. HT", "TVA", "Total HT", "Total TTC"]
    rows = [art_header]
    total_ht_global  = 0.0
    total_tva_global = 0.0
    total_ttc_global = 0.0
    tva_details: dict[float, float] = {}

    for art in data["articles"]:
        tva_r    = art.get("tva", data.get("tva", 20.0))
        pu_ht    = art["prix_unitaire"]
        qte      = art["quantite"]
        ligne_ht = qte * pu_ht
        ligne_tva = ligne_ht * tva_r / 100
        ligne_ttc = ligne_ht + ligne_tva
        total_ht_global  += ligne_ht
        total_tva_global += ligne_tva
        total_ttc_global += ligne_ttc
        tva_details[tva_r] = tva_details.get(tva_r, 0.0) + ligne_tva
        rows.append([
            art["nom"], str(qte),
            f"{pu_ht:.2f} €", f"{tva_r:.0f}%",
            f"{ligne_ht:.2f} €", f"{ligne_ttc:.2f} €",
        ])

    col_w = [W*0.34, W*0.07, W*0.15, W*0.08, W*0.16, W*0.16]
    art_tbl = Table(rows, colWidths=col_w, repeatRows=1)
    art_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  C),
        ("TEXTCOLOR",     (0,0),(-1,0),  colors.white),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 8),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, C2]),
        ("ALIGN",         (1,0),(-1,-1), "RIGHT"),
        ("ALIGN",         (0,0),(0,-1),  "LEFT"),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(0,-1),  7),
        ("RIGHTPADDING",  (-1,0),(-1,-1), 7),
        ("LINEBELOW",     (0,-1),(-1,-1), 0.5, CBORDER),
        ("LINEBELOW",     (0,0),(-1,0),   0,   colors.white),
    ]))
    elems.append(art_tbl)
    elems.append(Spacer(1, 10))

    # ── TOTAUX ────────────────────────────────────
    totaux_rows = [["Sous-total HT", f"{total_ht_global:.2f} €"]]
    for taux, montant in sorted(tva_details.items()):
        totaux_rows.append([f"TVA {taux:.0f}%", f"{montant:.2f} €"])
    totaux_tbl = Table(totaux_rows, colWidths=[W*0.8, W*0.2])
    totaux_tbl.setStyle(TableStyle([
        ("FONTNAME",      (0,0),(-1,-1), "Helvetica"),
        ("FONTSIZE",      (0,0),(-1,-1), 8),
        ("ALIGN",         (1,0),(1,-1),  "RIGHT"),
        ("TEXTCOLOR",     (0,0),(-1,-1), CGREY),
        ("TOPPADDING",    (0,0),(-1,-1), 2),
        ("BOTTOMPADDING", (0,0),(-1,-1), 2),
        ("RIGHTPADDING",  (1,0),(1,-1),  7),
    ]))
    elems.append(totaux_tbl)
    elems.append(Spacer(1, 2))

    total_ligne = Table([["TOTAL TTC", f"{total_ttc_global:.2f} €"]], colWidths=[W*0.8, W*0.2])
    total_ligne.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), C),
        ("TEXTCOLOR",     (0,0),(-1,-1), colors.white),
        ("FONTNAME",      (0,0),(-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 11),
        ("ALIGN",         (1,0),(1,-1),  "RIGHT"),
        ("TOPPADDING",    (0,0),(-1,-1), 7),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
        ("LEFTPADDING",   (0,0),(0,-1),  10),
        ("RIGHTPADDING",  (1,0),(1,-1),  7),
    ]))
    elems.append(total_ligne)
    elems.append(Spacer(1, 18))

    # ── PAIEMENT + SIGNATURE ─────────────────────────
    pmt_lines = [
        Paragraph("MODALITÉS DE PAIEMENT", fp("pm_h","Helvetica-Bold", 8, color=C)),
        Spacer(1, 4),
        Paragraph(f"Mode : <b>{mode}</b>", fp("pm1", size=8, color=colors.HexColor("#374151"))),
        Paragraph(f"Échéance : <b>{echeance}</b>  —  Date limite : <b>{now.strftime('%d/%m/%Y')}</b>",
                  fp("pm2", size=8, color=colors.HexColor("#374151"))),
    ]
    if mode.lower() in ("virement", "virement bancaire"):
        pmt_lines += [
            Spacer(1, 4),
            Paragraph("Virement à effectuer à l'ordre de :", fp("pm3", size=7, color=CGREY)),
            Paragraph(data["marque"], fp("pm4","Helvetica-Bold", 8)),
        ]

    sig_lines = [
        Paragraph("BON POUR ACCORD", fp("sig_h","Helvetica-Bold", 8, TA_CENTER, C)),
        Spacer(1, 28),
        HRFlowable(width="100%", thickness=0.5, color=CBORDER),
        Spacer(1, 3),
        Paragraph("Signature et cachet", fp("sig_f", size=7, align=TA_CENTER, color=CGREY)),
    ]

    bottom_row = Table(
        [[pmt_lines, "", sig_lines]],
        colWidths=[W * 0.52, W * 0.04, W * 0.44]
    )
    bottom_row.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("BOX",           (0,0),(0,-1),  0.5, CBORDER),
        ("BOX",           (2,0),(2,-1),  0.5, CBORDER),
        ("TOPPADDING",    (0,0),(-1,-1), 8),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ("LEFTPADDING",   (0,0),(0,-1),  8),
        ("LEFTPADDING",   (2,0),(2,-1),  8),
        ("RIGHTPADDING",  (0,0),(0,-1),  8),
        ("RIGHTPADDING",  (2,0),(2,-1),  8),
    ]))
    elems.append(bottom_row)
    elems.append(Spacer(1, 14))

    # ── PIED DE PAGE ──────────────────────────────
    elems.append(HRFlowable(width="100%", thickness=0.5, color=CBORDER))
    elems.append(Spacer(1, 5))

    mentions = (
        "Paiement à réception. Tout retard de paiement entraîne des pénalités de 3× le taux d'intérêt légal "
        "ainsi qu'une indemnité forfaitaire de 40 € (Art. L441-10 C. com.). TVA acquittée sur encaissements."
    )
    if siret:
        mentions = f"SIRET : {siret}  —  " + mentions

    # Barcode de référence en bas
    ref_val = numero.replace("-", "")[:12].ljust(12, "0")
    try:
        bc_ref = code128.Code128(ref_val, barHeight=0.8*cm, barWidth=0.8, humanReadable=False)
        scale  = (W * 0.3) / bc_ref.width
        bc     = code128.Code128(ref_val, barHeight=0.8*cm, barWidth=scale, humanReadable=True)
        bc.hAlign = "RIGHT"
        footer_tbl = Table(
            [[Paragraph(mentions, fp("men", size=6.5, color=CGREY)), bc]],
            colWidths=[W * 0.65, W * 0.35]
        )
        footer_tbl.setStyle(TableStyle([
            ("VALIGN",  (0,0),(-1,-1), "MIDDLE"),
            ("ALIGN",   (1,0),(1,-1),  "RIGHT"),
        ]))
        elems.append(footer_tbl)
    except Exception:
        elems.append(Paragraph(mentions, fp("men", size=6.5, color=CGREY)))

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


# ─────────────────────────────────────────
#  VIEW ARTICLES
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


# ─────────────────────────────────────────
#  SÉLECTION DU STYLE DE TICKET
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
#  VUE PRINCIPALE
# ─────────────────────────────────────────

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

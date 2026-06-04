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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import urllib.request

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
#  POLICES PERSONNALISÉES
# ─────────────────────────────────────────
_FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_FONT_URLS = {
    "Cinzel-Bold":      "https://raw.githubusercontent.com/google/fonts/main/ofl/cinzel/Cinzel[wght].ttf",
    "Montserrat-Bold":  "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat[wght].ttf",
    "Oswald-Bold":      "https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/Oswald[wght].ttf",
}

def _ensure_fonts():
    os.makedirs(_FONTS_DIR, exist_ok=True)
    for name, url in _FONT_URLS.items():
        path = os.path.join(_FONTS_DIR, f"{name}.ttf")
        if not os.path.exists(path):
            try:
                urllib.request.urlretrieve(url, path)
                print(f"[FONT] Downloaded {name}")
            except Exception as e:
                print(f"[FONT] Could not download {name}: {e}")
                continue
        try:
            pdfmetrics.registerFont(TTFont(name, path))
        except Exception as e:
            print(f"[FONT] Could not register {name}: {e}")

_ensure_fonts()

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
        "label":            "💎 Luxe (LV, Chanel, Dior…)",
        "header_font":      "Cinzel-Bold",
        "header_fallback":  "Times-Bold",
        "header_sz":        22,
        "spacing":          True,
    },
    "standard": {
        "label":            "🛍️ Standard (Zara, Nike, Sephora…)",
        "header_font":      "Montserrat-Bold",
        "header_fallback":  "Helvetica-Bold",
        "header_sz":        18,
        "spacing":          False,
    },
    "restaurant": {
        "label":            "🍔 Restaurant / Supermarché",
        "header_font":      "Oswald-Bold",
        "header_fallback":  "Courier-Bold",
        "header_sz":        16,
        "spacing":          False,
    },
}


# ─────────────────────────────────────────
#  GÉNÉRATION PDF — TICKET DE CAISSE
# ─────────────────────────────────────────
def _spaced(text: str) -> str:
    words = text.upper().split()
    return "   ".join(" ".join(w) for w in words)

def _header_sz(nom: str, max_sz: int, w_pt: float) -> int:
    parts = nom.split()
    longest = max(len(p) for p in parts) if parts else len(nom)
    for sz in range(max_sz, 8, -1):
        if longest * sz * 0.56 <= w_pt:
            return sz
    return 8

def _font(preferred: str, fallback: str) -> str:
    try:
        pdfmetrics.getFont(preferred)
        return preferred
    except Exception:
        return fallback

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
    hfont = _font(s["header_font"], s.get("header_fallback", "Helvetica-Bold"))
    hsz = _header_sz(nom, s["header_sz"], W) if s["spacing"] else s["header_sz"]
    elems.append(p(nom, font=hfont, size=hsz, align=TA_CENTER))
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

    # ── EN-TÊTE ARTICLES ──────────────────────
    elems.append(p("ARTICLE          QTE  PRIX    MONTANT", BODY_B))
    elems.append(sep("-"))

    # ── ARTICLES ───────────────────────────────
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

    # ── TOTAUX ──────────────────────────────────
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

    # ── PAIEMENT ────────────────────────────────
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

    # ── INFOS FINALES ─────────────────────────
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

    # ── CODE-BARRES pleine largeur ──────────────
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
    n_art  = len(data["articles"])
    W_PAGE = A4[0]
    page_h = max((22 + 1.5 * n_art) * cm, A4[1])

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=(W_PAGE, page_h),
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=1.5*cm,
    )
    W = W_PAGE - 4.0 * cm

    style_key = data.get("style", "standard")
    s = TICKET_STYLES.get(style_key, TICKET_STYLES["standard"])

    BK    = colors.black
    GR    = colors.HexColor("#444444")
    LG    = colors.HexColor("#888888")
    LGRAY = colors.HexColor("#F0F0F0")
    MGRAY = colors.HexColor("#C8C8C8")
    DOT   = (2, 3)

    _c = [0]
    def st(font="Helvetica", size=8.5, align=TA_LEFT, color=colors.black, leading=None):
        _c[0] += 1
        return ParagraphStyle(f"s{_c[0]}", fontName=font, fontSize=size,
                               alignment=align, textColor=color,
                               leading=leading or size * 1.35)

    now       = datetime.now()
    numero    = data["numero"]
    date_str  = now.strftime("%d/%m/%Y")
    echeance  = data.get("echeance", "30 jours")
    mode      = data.get("paiement", "Virement bancaire")
    siret     = data.get("siret", "")
    tva_intra = data.get("tva_intra", "")
    adr_em    = data.get("adresse_emetteur", "")
    iban      = data.get("iban", "")
    bic       = data.get("bic", "")
    logo_url  = data.get("logo_url", "")
    cl_name   = f"{data['prenom']} {data['nom'].upper()}"
    hfont     = _font(s["header_font"], s.get("header_fallback", "Helvetica-Bold"))
    elems     = []

    # ── calcul articles (commun aux deux layouts) ─────────────────
    total_ht = total_tva = total_ttc = 0.0
    tva_details: dict[float, float] = {}
    art_data = []
    for art in data["articles"]:
        tr   = art.get("tva", data.get("tva", 20.0))
        pu   = art["prix_unitaire"]
        qte  = art["quantite"]
        lht  = qte * pu
        ltva = lht * tr / 100
        lttc = lht + ltva
        total_ht  += lht
        total_tva += ltva
        total_ttc += lttc
        tva_details[tr] = tva_details.get(tr, 0.0) + ltva
        art_data.append((art["nom"], qte, pu, tr, lht, lttc))

    # ═══════════════════════════════════════════════════════════════
    if style_key == "luxe":
    # ═══ LAYOUT LUXE — calqué sur les vraies factures de prestige ══

        # ── tenter de charger le logo ─────────────────────────────
        logo_flowable = None
        if logo_url:
            try:
                from reportlab.platypus import Image as RLImage
                tmp_path = "/tmp/_invoice_logo.img"
                urllib.request.urlretrieve(logo_url, tmp_path)
                logo_flowable = RLImage(tmp_path, width=2.2*cm, height=2.2*cm,
                                        kind="proportional")
            except Exception:
                logo_flowable = None

        # ── 1. EN-TÊTE : logo/monogramme gauche, client droite ────
        initials = "".join(w[0] for w in data["marque"].upper().split() if w)[:3]
        em_left = []
        if logo_flowable:
            em_left.append(logo_flowable)
            em_left.append(Spacer(1, 4))
        else:
            em_left.append(Paragraph(initials, st(hfont, 38)))
            em_left.append(Spacer(1, 3))
        em_left.append(Paragraph(data["marque"].upper(), st("Helvetica-Bold", 9.5)))
        if adr_em:
            for line in adr_em.split(","):
                em_left.append(Paragraph(line.strip(), st(size=8.5)))
        if siret:
            em_left.append(Paragraph(f"<b>Siret</b> : {siret}", st(size=8.5)))
        if tva_intra:
            em_left.append(Paragraph(f"<b>N° TVA</b> : {tva_intra}", st(size=8.5)))

        cl_right = [Paragraph(cl_name, st("Helvetica-Bold", 9.5, TA_RIGHT))]
        if data.get("adresse_client"):
            for line in data["adresse_client"].split(","):
                cl_right.append(Paragraph(line.strip(), st(size=8.5, align=TA_RIGHT)))
        if data.get("email"):
            cl_right.append(Paragraph(data["email"], st(size=8, align=TA_RIGHT, color=LG)))

        lw_h, rw_h = W*0.55, W*0.42
        em_tbl = Table([[e] for e in em_left], colWidths=[lw_h])
        em_tbl.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),1.5),("BOTTOMPADDING",(0,0),(-1,-1),1.5),
                                     ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))
        cl_tbl = Table([[e] for e in cl_right], colWidths=[rw_h])
        cl_tbl.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),1.5),("BOTTOMPADDING",(0,0),(-1,-1),1.5),
                                     ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))
        hdr_tbl = Table([[em_tbl, "", cl_tbl]], colWidths=[lw_h, W*0.03, rw_h])
        hdr_tbl.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                                      ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
                                      ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))
        elems.append(hdr_tbl)
        elems.append(Spacer(1, 14))
        elems.append(HRFlowable(width="100%", thickness=0.5, color=BK))
        elems.append(Spacer(1, 12))

        # ── 2. TABLE DE RÉFÉRENCE (Date, N°) ─────────────────────
        ref_rows = [
            [Paragraph("N° de facture",    st("Helvetica-Bold", 8.5)), Paragraph(numero,   st(size=8.5))],
            [Paragraph("Date de facture",  st("Helvetica-Bold", 8.5)), Paragraph(date_str, st(size=8.5))],
            [Paragraph("Date d'échéance",  st("Helvetica-Bold", 8.5)), Paragraph(echeance, st(size=8.5))],
        ]
        ref_tbl = Table(ref_rows, colWidths=[W*0.28, W*0.22])
        ref_tbl.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(0,-1), LGRAY),
            ("BOX",(0,0),(-1,-1),0.5,BK),
            ("LINEBELOW",(0,0),(-1,-2),0.25,MGRAY),
            ("LINEBEFORE",(1,0),(1,-1),0.25,MGRAY),
            ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
            ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),
        ]))
        elems.append(ref_tbl)
        elems.append(Spacer(1, 18))

        # ── 3. TABLEAU ARTICLES 4 colonnes (style LV) ────────────
        art_rows_lux = [["Description", "Quantité", "Prix unitaire HT", "Prix total HT"]]
        for (nom, qte, pu, tr, lht, lttc) in art_data:
            art_rows_lux.append([nom, str(qte), f"{pu:.2f} €", f"{lht:.2f} €"])
        cw_lux = [W*0.46, W*0.12, W*0.22, W*0.20]
        art_tbl_lux = Table(art_rows_lux, colWidths=cw_lux, repeatRows=1)
        art_tbl_lux.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0), LGRAY),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTNAME",(0,1),(-1,-1),"Helvetica"),
            ("FONTSIZE",(0,0),(-1,-1),8.5),
            ("ALIGN",(0,0),(0,-1),"LEFT"),
            ("ALIGN",(1,0),(-1,-1),"RIGHT"),
            ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
            ("LEFTPADDING",(0,0),(0,-1),8),("RIGHTPADDING",(-1,0),(-1,-1),8),
            ("BOX",(0,0),(-1,-1),0.5,BK),
            ("LINEBELOW",(0,0),(-1,0),0.5,MGRAY),
            ("LINEBELOW",(0,1),(-1,-1),0.25,colors.HexColor("#E8E8E8")),
            ("LINEBEFORE",(1,0),(-1,-1),0.25,MGRAY),
        ]))
        elems.append(art_tbl_lux)
        elems.append(Spacer(1, 16))

        # ── 4. TOTAUX droite ──────────────────────────────────────
        tw_l = W * 0.44; lc_l = tw_l * 0.56; vc_l = tw_l * 0.44
        tot_rows_lux = [[Paragraph("Total HT", st(size=8.5)),
                         Paragraph(f"{total_ht:.2f} €", st(size=8.5, align=TA_RIGHT))]]
        for taux, mnt in sorted(tva_details.items()):
            tot_rows_lux.append([Paragraph(f"TVA ({taux:.2f} %)", st(size=8.5)),
                                  Paragraph(f"{mnt:.2f} €", st(size=8.5, align=TA_RIGHT))])
        tot_rows_lux.append([Paragraph("Total TTC", st("Helvetica-Bold", 9)),
                              Paragraph(f"{total_ttc:.2f} €", st("Helvetica-Bold", 9, TA_RIGHT))])
        tot_tbl_lux = Table(tot_rows_lux, colWidths=[lc_l, vc_l])
        tot_tbl_lux.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-2), LGRAY),
            ("BACKGROUND",(0,-1),(-1,-1), colors.HexColor("#E0E0E0")),
            ("BOX",(0,0),(-1,-1),0.5,BK),
            ("LINEBELOW",(0,0),(-1,-2),0.25,MGRAY),
            ("LINEABOVE",(0,-1),(-1,-1),0.5,BK),
            ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
            ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),
        ]))
        wrap_lux = Table([["", tot_tbl_lux]], colWidths=[W - tw_l, tw_l])
        wrap_lux.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
                                       ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
                                       ("VALIGN",(0,0),(-1,-1),"TOP")]))
        elems.append(wrap_lux)
        elems.append(Spacer(1, 16))

        # ── 5. Paiement (virement) ────────────────────────────────
        if iban or bic or mode:
            pay_lines = [Paragraph(f"Mode de règlement : {mode}", st(size=8.5))]
            if iban:
                pay_lines.append(Paragraph(f"IBAN : {iban}", st(size=8.5)))
            if bic:
                pay_lines.append(Paragraph(f"BIC : {bic}", st(size=8.5)))
            for pl in pay_lines:
                elems.append(pl)
            elems.append(Spacer(1, 12))

        # ── 6. Mentions légales ───────────────────────────────────
        elems.append(HRFlowable(width="100%", thickness=0.3, color=LG))
        elems.append(Spacer(1, 5))
        mentions = (
            "En cas de retard, une pénalité au taux annuel de 5 % sera appliquée, "
            "à laquelle s'ajoutera une indemnité forfaitaire pour frais de recouvrement de 40 €"
        )
        if siret:
            mentions = f"SIRET : {siret}" + (f"  |  N° TVA : {tva_intra}" if tva_intra else "") + "  —  " + mentions
        elems.append(Paragraph(mentions, st(size=7, align=TA_CENTER, color=LG)))

    else:
    # ═══ LAYOUT STANDARD / RESTAURANT — pointillés ════════════════

        def dot_box(inner, cw):
            t = Table([[inner]], colWidths=[cw])
            t.setStyle(TableStyle([
                ("BOX",(0,0),(-1,-1),0.6,BK,0,DOT),
                ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),12),
                ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
            ]))
            return t

        def inner_rows(rows, cw):
            t = Table(rows, colWidths=[cw])
            t.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),1.5),("BOTTOMPADDING",(0,0),(-1,-1),1.5),
                                    ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))
            return t

        # ── 1. EN-TÊTE : nom de marque + FACTURE ─────────────────
        lw, rw = W * 0.60, W * 0.40
        nom_marque = _spaced(data["marque"]) if s["spacing"] else data["marque"].upper()
        hsz = _header_sz(nom_marque, s["header_sz"], lw) if s["spacing"] else s["header_sz"]
        hdr = Table([[Paragraph(nom_marque, st(hfont, hsz)),
                      Paragraph("FACTURE", st("Helvetica-Bold", 28, TA_RIGHT))]],
                    colWidths=[lw, rw])
        hdr.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"BOTTOM"),
                                  ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),4),
                                  ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))
        elems.append(hdr)
        elems.append(Spacer(1, 2))
        elems.append(Paragraph(f"N° {numero}", st(size=8.5, align=TA_RIGHT, color=LG)))
        elems.append(HRFlowable(width="100%", thickness=1, color=BK))
        elems.append(Spacer(1, 12))

        # ── 2. ÉMETTEUR  |  FACTURÉ À ────────────────────────────
        bw, gap_w, dw = W * 0.46, W * 0.08, W * 0.46
        de_rows = [[Paragraph("ÉMETTEUR", st("Helvetica-Bold", 7, color=LG))],
                   [Spacer(1, 4)],
                   [Paragraph(data["marque"], st("Helvetica-Bold", 9.5))]]
        if adr_em:
            for line in adr_em.split(","):
                de_rows.append([Paragraph(line.strip(), st(size=8.5, color=GR))])
        if siret:
            de_rows.append([Paragraph(f"SIRET : {siret}", st(size=8, color=LG))])
        if tva_intra:
            de_rows.append([Paragraph(f"N° TVA : {tva_intra}", st(size=8, color=LG))])
        fa_rows = [[Paragraph("FACTURÉ À", st("Helvetica-Bold", 7, color=LG))],
                   [Spacer(1, 4)],
                   [Paragraph(cl_name, st("Helvetica-Bold", 10))]]
        if data.get("adresse_client"):
            fa_rows.append([Paragraph(data["adresse_client"], st(size=8.5, color=GR))])
        if data.get("email"):
            fa_rows.append([Paragraph(data["email"], st(size=8.5, color=GR))])
        addr_tbl = Table([[dot_box(inner_rows(de_rows, bw-20), bw), "",
                           dot_box(inner_rows(fa_rows, dw-20), dw)]], colWidths=[bw, gap_w, dw])
        addr_tbl.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                                       ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
                                       ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))
        elems.append(addr_tbl)
        elems.append(Spacer(1, 10))

        # ── 3. BARRE DE RÉFÉRENCE ─────────────────────────────────
        ref_cw = [W*0.22, W*0.22, W*0.22, W*0.34]
        ref_tbl = Table([
            [Paragraph(t, st("Helvetica-Bold", 7, color=LG)) for t in
             ["N° DE FACTURE","DATE D'ÉMISSION","DATE D'ÉCHÉANCE","MODE DE RÈGLEMENT"]],
            [Paragraph(v, st("Helvetica-Bold", 9)) for v in [numero, date_str, echeance, mode]],
        ], colWidths=ref_cw)
        ref_tbl.setStyle(TableStyle([
            ("BOX",(0,0),(-1,-1),0.6,BK,0,DOT),
            ("LINEBEFORE",(1,0),(3,-1),0.5,BK,0,DOT),
            ("LINEBELOW",(0,0),(-1,0),0.4,BK,0,DOT),
            ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
            ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),
        ]))
        elems.append(ref_tbl)
        elems.append(Spacer(1, 14))

        # ── 4. TABLEAU ARTICLES 6 colonnes ───────────────────────
        art_rows = [["DÉSIGNATION","QTÉ","P.U. HT","TVA","TOTAL HT","TOTAL TTC"]]
        for (nom, qte, pu, tr, lht, lttc) in art_data:
            art_rows.append([nom, str(qte), f"{pu:.2f} €", f"{tr:.0f}%",
                             f"{lht:.2f} €", f"{lttc:.2f} €"])
        cw = [W*0.34, W*0.07, W*0.14, W*0.09, W*0.18, W*0.18]
        art_tbl = Table(art_rows, colWidths=cw, repeatRows=1)
        art_tbl.setStyle(TableStyle([
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTNAME",(0,1),(-1,-1),"Helvetica"),
            ("FONTSIZE",(0,0),(-1,-1),8.5),
            ("ALIGN",(0,0),(0,-1),"LEFT"),("ALIGN",(1,0),(-1,-1),"RIGHT"),
            ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
            ("LEFTPADDING",(0,0),(0,-1),8),("RIGHTPADDING",(-1,0),(-1,-1),8),
            ("BOX",(0,0),(-1,-1),0.6,BK,0,DOT),
            ("INNERGRID",(0,0),(-1,-1),0.4,BK,0,DOT),
            ("LINEBELOW",(0,0),(-1,0),1.0,BK),
        ]))
        elems.append(art_tbl)
        elems.append(Spacer(1, 12))

        # ── 5. TOTAUX ─────────────────────────────────────────────
        tw = W * 0.40; lc = tw * 0.58; vc = tw * 0.42
        tot_data = [[Paragraph("Sous-total HT", st(size=8.5, color=GR)),
                     Paragraph(f"{total_ht:.2f} €", st(size=8.5, align=TA_RIGHT, color=GR))]]
        for taux, mnt in sorted(tva_details.items()):
            tot_data.append([Paragraph(f"TVA {taux:.0f}%", st(size=8.5, color=GR)),
                              Paragraph(f"{mnt:.2f} €", st(size=8.5, align=TA_RIGHT, color=GR))])
        tot_data.append([Paragraph("TOTAL TTC", st("Helvetica-Bold", 10)),
                         Paragraph(f"{total_ttc:.2f} €", st("Helvetica-Bold", 10, TA_RIGHT))])
        tot_tbl = Table(tot_data, colWidths=[lc, vc])
        tot_tbl.setStyle(TableStyle([
            ("BOX",(0,0),(-1,-1),0.6,BK,0,DOT),
            ("LINEBELOW",(0,0),(-1,-2),0.4,BK,0,DOT),
            ("LINEABOVE",(0,-1),(-1,-1),1.0,BK),
            ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
            ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),
        ]))
        wrap = Table([["", tot_tbl]], colWidths=[W-tw, tw])
        wrap.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
                                   ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
                                   ("VALIGN",(0,0),(-1,-1),"TOP")]))
        elems.append(wrap)
        elems.append(Spacer(1, 20))

        # ── 6. PIED DE PAGE ───────────────────────────────────────
        elems.append(HRFlowable(width="100%", thickness=0.5, color=BK, dash=DOT))
        elems.append(Spacer(1, 8))
        pw, nw = W * 0.58, W * 0.42
        pay_rows = [[Paragraph("INFORMATIONS DE PAIEMENT", st("Helvetica-Bold", 7, color=LG))],
                    [Spacer(1, 3)],
                    [Paragraph(mode, st("Helvetica-Bold", 9))]]
        if mode.lower() in ("virement", "virement bancaire"):
            pay_rows.append([Paragraph(f"À l'ordre de : {data['marque']}", st(size=8.5, color=GR))])
        if iban:
            pay_rows.append([Paragraph(f"IBAN : {iban}", st(size=8.5, color=GR))])
        if bic:
            pay_rows.append([Paragraph(f"BIC / SWIFT : {bic}", st(size=8.5, color=GR))])
        pay_left_tbl = Table(pay_rows, colWidths=[pw])
        pay_left_tbl.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
                                           ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))
        net_box = Table([
            [Paragraph("NET À RÉGLER", st("Helvetica-Bold", 7, TA_CENTER, color=LG))],
            [Paragraph(f"{total_ttc:.2f} €", st("Helvetica-Bold", 18, TA_CENTER))],
        ], colWidths=[nw])
        net_box.setStyle(TableStyle([
            ("BOX",(0,0),(-1,-1),0.6,BK,0,DOT),("LINEABOVE",(0,0),(-1,0),1.5,BK),
            ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10),
            ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ]))
        footer_tbl = Table([[pay_left_tbl, net_box]], colWidths=[pw, nw])
        footer_tbl.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                                         ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
                                         ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))
        elems.append(footer_tbl)
        elems.append(Spacer(1, 10))
        mentions = ("En cas de retard de paiement, des pénalités au taux de 3 fois le taux légal seront "
                    "applicables, ainsi qu'une indemnité forfaitaire de recouvrement de 40 € (Art. L441-10 C. com.).")
        if siret:
            mentions = f"SIRET : {siret}" + (f"  |  N° TVA : {tva_intra}" if tva_intra else "") + "  —  " + mentions
        elems.append(HRFlowable(width="100%", thickness=0.4, color=LG, dash=DOT))
        elems.append(Spacer(1, 5))
        elems.append(Paragraph(mentions, st(size=6.5, color=LG)))

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


class ModalInfosFacture1(discord.ui.Modal, title="Facture — Étape 1/2 · Émetteur & Client"):
    marque   = discord.ui.TextInput(label="Votre entreprise / marque", placeholder="Ex: ACME SAS")
    adresse  = discord.ui.TextInput(label="Votre adresse", required=False, placeholder="1 rue de la Paix, 75001 Paris")
    siret    = discord.ui.TextInput(label="SIRET — N° TVA intracommunautaire", required=False, placeholder="123 456 789 00012 — FR12 123456789")
    client   = discord.ui.TextInput(label="Prénom NOM du client", placeholder="Jean DUPONT")
    email    = discord.ui.TextInput(label="Email du client", placeholder="client@email.com")

    def __init__(self, style: str = "standard"):
        super().__init__()
        self.style = style

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        sessions[uid] = {
            "_step1": True,
            "style": self.style,
            "marque": self.marque.value,
            "adresse_emetteur": self.adresse.value or "",
            "siret_raw": self.siret.value or "",
            "client_full": self.client.value.strip(),
            "email": self.email.value,
        }
        await interaction.response.send_modal(ModalInfosFacture2())


class ModalInfosFacture2(discord.ui.Modal, title="Facture — Étape 2/2 · Paiement & Coordonnées"):
    adresse_client = discord.ui.TextInput(label="Adresse du client", required=False, placeholder="10 avenue Victor Hugo, 69001 Lyon")
    paiement       = discord.ui.TextInput(label="Mode de règlement", placeholder="Virement bancaire / Chèque / CB", default="Virement bancaire")
    echeance       = discord.ui.TextInput(label="Délai de paiement", placeholder="30 jours / À réception / 15 jours", default="30 jours")
    iban           = discord.ui.TextInput(label="IBAN — BIC (optionnel)", required=False, placeholder="FR76 3000 6000 0112 3456 7890 189 — BNPAFRPPXXX")
    logo_url       = discord.ui.TextInput(label="URL du logo (optionnel, style Luxe)", required=False, placeholder="https://…/logo.png")

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        step1 = sessions.get(uid, {})

        parts = step1.get("client_full", "").split(" ", 1)
        prenom = parts[0]
        nom = parts[1] if len(parts) > 1 else ""

        siret_raw = step1.get("siret_raw", "")
        siret_val = ""
        tva_intra = ""
        if "—" in siret_raw:
            sp = siret_raw.split("—", 1)
            siret_val = sp[0].strip()
            tva_intra = sp[1].strip()
        elif siret_raw:
            siret_val = siret_raw.strip()

        iban_raw = self.iban.value or ""
        iban_val = bic_val = ""
        if "—" in iban_raw:
            sp = iban_raw.split("—", 1)
            iban_val = sp[0].strip()
            bic_val  = sp[1].strip()
        elif iban_raw:
            iban_val = iban_raw.strip()

        sessions[uid] = {
            "type": "facture",
            "style": step1.get("style", "standard"),
            "marque": step1.get("marque", ""),
            "adresse_emetteur": step1.get("adresse_emetteur", ""),
            "siret": siret_val,
            "tva_intra": tva_intra,
            "prenom": prenom,
            "nom": nom,
            "email": step1.get("email", ""),
            "adresse_client": self.adresse_client.value or "",
            "paiement": self.paiement.value or "Virement bancaire",
            "echeance": self.echeance.value or "30 jours",
            "iban": iban_val,
            "bic": bic_val,
            "logo_url": self.logo_url.value or "",
            "tva": 20.0,
            "articles": [],
            "numero": f"FAC-{gen_numero()}",
        }
        client_full = step1.get("client_full", "")
        marque = step1.get("marque", "")
        await interaction.response.send_message(
            f"✅ Facture pour **{client_full}** — entreprise **{marque}**\n\n"
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
#  SÉLECTION DU STYLE DE FACTURE
# ─────────────────────────────────────────

class ViewStyleFacture(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="💎 Luxe", style=discord.ButtonStyle.secondary)
    async def luxe(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalInfosFacture1("luxe"))

    @discord.ui.button(label="🛍️ Standard / Services", style=discord.ButtonStyle.primary)
    async def standard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalInfosFacture1("standard"))

    @discord.ui.button(label="🍔 Restaurant / Commerce", style=discord.ButtonStyle.secondary)
    async def restaurant(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalInfosFacture1("restaurant"))


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
        await interaction.response.send_message(
            "**Quel style de facture ?**\n\n"
            "💎 **Luxe** — Maisons de luxe, haute couture (Cinzel)\n"
            "🛍️ **Standard / Services** — Entreprises, freelances, retail (Montserrat)\n"
            "🍔 **Restaurant / Commerce** — Restauration, alimentaire (Oswald)",
            view=ViewStyleFacture(),
            ephemeral=True,
        )


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

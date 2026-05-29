#!/usr/bin/env python3
"""Generate the M&B Agency strategic plan PDF (reportlab)."""

from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether, ListFlowable, ListItem,
)

# ---- Brand palette ----
NAVY = colors.HexColor("#0F1B3C")
BLUE = colors.HexColor("#2563EB")
ACCENT = colors.HexColor("#7C3AED")
LIGHT = colors.HexColor("#EEF2FF")
GREY = colors.HexColor("#475569")
LGREY = colors.HexColor("#E2E8F0")
GREEN = colors.HexColor("#16A34A")
AMBER = colors.HexColor("#D97706")

styles = getSampleStyleSheet()


def S(name, **kw):
    styles.add(ParagraphStyle(name, **kw))


S("CoverTitle", fontName="Helvetica-Bold", fontSize=30, leading=34,
  textColor=NAVY, alignment=TA_LEFT, spaceAfter=6)
S("CoverSub", fontName="Helvetica", fontSize=14, leading=20,
  textColor=GREY, alignment=TA_LEFT)
S("CoverTag", fontName="Helvetica-Bold", fontSize=11, leading=16,
  textColor=BLUE, alignment=TA_LEFT)
S("H1", fontName="Helvetica-Bold", fontSize=17, leading=21,
  textColor=NAVY, spaceBefore=16, spaceAfter=8)
S("H2", fontName="Helvetica-Bold", fontSize=13, leading=17,
  textColor=BLUE, spaceBefore=12, spaceAfter=5)
S("Body", fontName="Helvetica", fontSize=10, leading=15,
  textColor=colors.HexColor("#1E293B"), alignment=TA_JUSTIFY, spaceAfter=6)
S("BodyL", fontName="Helvetica", fontSize=10, leading=15,
  textColor=colors.HexColor("#1E293B"), alignment=TA_LEFT, spaceAfter=6)
S("Bul", fontName="Helvetica", fontSize=10, leading=14,
  textColor=colors.HexColor("#1E293B"))
S("Small", fontName="Helvetica", fontSize=8.5, leading=12, textColor=GREY)
S("Cell", fontName="Helvetica", fontSize=8.7, leading=11.5,
  textColor=colors.HexColor("#1E293B"))
S("CellB", fontName="Helvetica-Bold", fontSize=8.7, leading=11.5,
  textColor=colors.white)
S("Callout", fontName="Helvetica", fontSize=9.5, leading=14,
  textColor=NAVY)

story = []


def h1(t): story.append(Paragraph(t, styles["H1"]))
def h2(t): story.append(Paragraph(t, styles["H2"]))
def p(t): story.append(Paragraph(t, styles["Body"]))
def pl(t): story.append(Paragraph(t, styles["BodyL"]))
def sp(h=6): story.append(Spacer(1, h))
def rule(c=LGREY): story.append(HRFlowable(width="100%", thickness=0.8, color=c,
                                           spaceBefore=4, spaceAfter=8))


def bullets(items):
    flow = [ListItem(Paragraph(t, styles["Bul"]), leftIndent=6,
                     value="•") for t in items]
    story.append(ListFlowable(flow, bulletType="bullet", start="•",
                              bulletColor=BLUE, leftIndent=10, spaceAfter=6))


def table(data, col_widths, header=True, zebra=True, font=8.7):
    rows = []
    for r, row in enumerate(data):
        styled = []
        for cell in row:
            st = "CellB" if (header and r == 0) else "Cell"
            styled.append(Paragraph(str(cell), styles[st]))
        rows.append(styled)
    t = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
    ts = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LGREY),
    ]
    if header:
        ts += [("BACKGROUND", (0, 0), (-1, 0), NAVY),
               ("TOPPADDING", (0, 0), (-1, 0), 7),
               ("BOTTOMPADDING", (0, 0), (-1, 0), 7)]
    if zebra:
        start = 1 if header else 0
        for i in range(start, len(data)):
            if (i - start) % 2 == 1:
                ts.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    t.setStyle(TableStyle(ts))
    story.append(t)
    sp(8)


def callout(title, text, bg=LIGHT, bar=BLUE):
    inner = [[Paragraph(f'<b>{title}</b><br/>{text}', styles["Callout"])]]
    t = Table(inner, colWidths=[165 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LINEBEFORE", (0, 0), (0, -1), 3, bar),
    ]))
    story.append(t)
    sp(8)


# =====================================================================
# COVER
# =====================================================================
story.append(Spacer(1, 40 * mm))
story.append(Paragraph("PLAN STRATÉGIQUE", styles["CoverTag"]))
sp(4)
story.append(Paragraph("M&amp;B Agency", styles["CoverTitle"]))
story.append(Paragraph("Du modèle agence classique au positionnement "
                       "<b>Agence IA</b>", styles["CoverSub"]))
sp(18)
story.append(HRFlowable(width="40%", thickness=2.5, color=BLUE,
                        spaceBefore=2, spaceAfter=14, hAlign="LEFT"))
meta = [
    ["Préparé pour", "M&B Agency — direction"],
    ["Périmètre", "Repositionnement + acquisition propre"],
    ["Services analysés", "Sites web · Publicité (Ads) · Communication"],
    ["Date", datetime.now().strftime("%d/%m/%Y")],
    ["Sources", "Claude Ads (/ads plan) + données Semrush (base FR)"],
]
mt = Table(meta, colWidths=[40 * mm, 110 * mm])
mt.setStyle(TableStyle([
    ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9.5),
    ("FONT", (1, 0), (1, -1), "Helvetica", 9.5),
    ("TEXTCOLOR", (0, 0), (0, -1), BLUE),
    ("TEXTCOLOR", (1, 0), (1, -1), GREY),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("ALIGN", (0, 0), (0, -1), "LEFT"),
    ("LEFTPADDING", (0, 0), (0, -1), 0),
]))
story.append(mt)
story.append(PageBreak())

# =====================================================================
# 1. SYNTHÈSE EXÉCUTIVE
# =====================================================================
h1("1. Synthèse exécutive")
p("M&B Agency dispose des trois briques qui comptent — création de sites "
  "internet, publicité en ligne et communication — au moment précis où "
  "l'IA générative redéfinit la chaîne de valeur des agences. La question "
  "n'est pas <i>« faut-il utiliser l'IA »</i> mais <i>« comment en faire un "
  "avantage concurrentiel défendable plutôt qu'une simple ligne marketing »</i>.")
p("Le risque, en 2026, est de se contenter de dire « nous utilisons l'IA » : "
  "tout le monde le revendique, cela ne différencie plus et tire les prix "
  "vers le bas. La stratégie recommandée est le <b>meta-play</b> : utiliser "
  "l'IA pour livrer plus vite, itérer davantage et réduire le coût de "
  "production — puis <b>vendre ce résultat mesurable</b>, en s'appuyant sur "
  "ses propres campagnes comme vitrine.")
callout("Le pari central",
        "Ne pas vendre « une agence qui fait de l'IA », mais « une agence qui "
        "livre en jours ce que les autres font en semaines — et qui le prouve "
        "sur ses propres chiffres ».", LIGHT, ACCENT)
callout("Point de départ mesuré (Semrush, FR)",
        "M&B est aujourd'hui quasi invisible hors marque (17 mots-clés "
        "organiques, ~29 visites/mois) et ne diffuse <b>aucune publicité</b>. "
        "Ce n'est pas un handicap : c'est une page blanche où chaque action "
        "d'acquisition produira un effet immédiat et mesurable.",
        colors.HexColor("#FEF3C7"), AMBER)
h2("Les 4 décisions à prendre")
bullets([
    "<b>Positionnement</b> — différenciation par le <b>résultat</b> "
    "(vitesse, volume créatif, data), pas par la techno.",
    "<b>Offre</b> — productiser : passer du sur-mesure facturé en jours/homme "
    "à des <b>packages à prix fixe</b> activés par l'IA.",
    "<b>Acquisition</b> — un funnel payant propre avec l'<b>Audit Ads IA "
    "gratuit</b> comme aimant à leads.",
    "<b>Preuve</b> — transformer ses propres campagnes en <b>études de cas</b> "
    "chiffrées (la meilleure arme commerciale).",
])

# =====================================================================
# 2. POSITIONNEMENT
# =====================================================================
h1("2. Positionnement : l'angle gagnant")
p("Le piège à éviter est la banalisation. L'angle gagnant consiste à rendre "
  "l'avantage IA <b>tangible et chiffré</b> sur trois axes que le client "
  "perçoit immédiatement.")
table([
    ["Pilier", "Agence classique", "M&B « IA »", "Preuve vendable"],
    ["Vitesse", "Site en 6–8 semaines", "Site en 1–2 semaines",
     "Cas client chronométré"],
    ["Volume créatif", "3–5 visuels / campagne", "20–30 variantes testées",
     "Dashboard de tests A/B"],
    ["Audit &amp; data", "Audit manuel, cher, lent", "Audit IA en 48 h",
     "Le skill Claude Ads"],
], [26 * mm, 45 * mm, 45 * mm, 49 * mm])
callout("Message de marque",
        "« On produit en jours ce que les agences classiques font en semaines, "
        "et on le prouve sur nos propres campagnes. »", LIGHT, BLUE)

# =====================================================================
# 3. REFONTE DE L'OFFRE
# =====================================================================
h1("3. Refonte de l'offre : productiser l'IA")
p("Le passage à des offres packagées à prix fixe est ce qui rend l'activité "
  "<b>scalable</b> et <b>vendable en publicité</b> (un prix clair convertit "
  "bien mieux qu'un « devis sur mesure »).")
table([
    ["Offre packagée", "Ce que l'IA permet", "Prix indicatif", "Rôle funnel"],
    ["Audit Ads IA — 48 h", "Skill Claude Ads (250+ checks)",
     "290–490 € ou offert", "Aimant à leads"],
    ["Pack Créatifs IA", "Visuels + copy multi-variantes", "990 €/mois",
     "Récurrent"],
    ["Site web express IA", "Build accéléré + contenu", "2 500–4 500 €",
     "Ticket d'entrée"],
    ["Gestion Ads + IA", "Audit continu, créa, optimisation",
     "1 500–3 000 €/mois", "Cœur de marge"],
], [33 * mm, 52 * mm, 38 * mm, 42 * mm])
callout("Action immédiate",
        "Lancer l'« Audit Ads IA gratuit » comme lead magnet : il démontre la "
        "valeur en livrant un vrai rapport — exactement ce que le skill "
        "Claude Ads produit.", colors.HexColor("#ECFDF5"), GREEN)

# =====================================================================
# 4. ANALYSE SITE & CONCURRENTS
# =====================================================================
story.append(PageBreak())
h1("4. Analyse du site &amp; des concurrents")
p("Analyse réalisée via <b>Semrush (base France)</b>. Le contenu on-page du "
  "site n'a pu être crawlé directement (le serveur bloque l'accès robot — "
  "certificat + HTTP 403), point à corriger ; en revanche la visibilité "
  "search de M&B est entièrement mesurée ci-dessous.")

h2("État de visibilité de m-bagency.com")
table([
    ["Indicateur (base FR)", "Valeur", "Lecture"],
    ["Rang Semrush", "1 479 766", "Très faible visibilité globale"],
    ["Mots-clés organiques", "17", "Empreinte SEO quasi nulle"],
    ["Trafic organique estimé", "~29 visites/mois", "Marginal"],
    ["Mots-clés payants", "0", "Aucune campagne Google Ads détectée"],
    ["Trafic payant", "0", "Aucune acquisition payante en cours"],
], [55 * mm, 38 * mm, 72 * mm])
callout("Constat central (données réelles)",
        "M&B se positionne aujourd'hui presque exclusivement sur <b>son propre "
        "nom</b> et sur quelques requêtes <b>locales</b> (« agence web "
        "carcassonne » #8, « agence web occitanie » #5, « agence communication "
        "carcassonne » #29) — à des positions faibles générant ~0 trafic. "
        "Hors marque, l'agence est <b>quasi invisible</b> et ne fait "
        "<b>aucune publicité</b>. C'est une page blanche : chaque euro investi "
        "en acquisition aura un impact immédiat.",
        colors.HexColor("#FEF3C7"), AMBER)
p("<b>Ancrage géographique confirmé</b> : M&B est une agence de "
  "<b>Carcassonne / Occitanie</b> (clients visibles en études de cas : "
  "Maxiburo, Pirate Canerie). Le plan d'acquisition doit donc combiner "
  "des requêtes <b>locales</b> (peu chères, haute intention) et l'angle "
  "<b>IA</b> différenciant.")

h2("Concurrents réels détectés (Semrush, organique)")
p("Contrairement à une première lecture, il existe de <b>vrais concurrents</b> "
  "locaux et régionaux. Les plus structurés en SEO :")
table([
    ["Concurrent", "Mots-clés", "Trafic/mois", "Profil"],
    ["miseenligne.com", "77", "~168", "Le plus visible en organique"],
    ["linkeo-toulouse.com", "105", "~46", "Réseau régional (Toulouse)"],
    ["artdim.fr", "40", "~65", "Agence créative"],
    ["speedizycom.com", "45", "~61", "Forte pertinence vs M&B"],
    ["vert-agence.fr", "41", "~30", "Concurrent régional"],
    ["agencewebcarcassonne.com", "14", "~6", "Rival direct (même ville)"],
], [50 * mm, 22 * mm, 25 * mm, 53 * mm])
callout("Lecture concurrence",
        "Aucun concurrent ne domine : même le plus fort (miseenligne.com) ne "
        "fait que ~168 visites/mois et <b>aucun ne diffuse de Google Ads</b> "
        "détectable. Le search payant local est un espace <b>quasi vide</b> — "
        "M&B peut y prendre la tête vite et à coût raisonnable.",
        LIGHT, GREEN)

h2("Opportunité mots-clés (volumes &amp; CPC réels — base FR)")
p("Volumes nationaux ci-dessous ; en pratique M&B ciblera leurs déclinaisons "
  "<b>locales</b> (« … carcassonne / occitanie »), au volume plus faible mais "
  "au CPC et à la concurrence bien moindres.")
table([
    ["Mot-clé", "Vol./mois", "CPC", "Conc.", "Lecture stratégique"],
    ["agence web", "14 800", "2,18 €", "0,27", "Cœur de cible, excellent ratio"],
    ["agence communication", "5 400", "1,63 €", "0,32", "Volume + CPC bas = efficient"],
    ["création site internet", "6 600", "3,97 €", "0,71", "Gros volume, très disputé"],
    ["agence google ads", "3 600", "10,67 €", "0,61", "Cher, haute intention"],
    ["refonte site internet", "2 900", "6,68 €", "0,35", "Intention d'achat forte"],
    ["agence marketing ia", "170", "2,30 €", "0,47", "Émergent, tendance ↑, à capter tôt"],
], [40 * mm, 20 * mm, 18 * mm, 15 * mm, 72 * mm])
callout("Lecture budget",
        "CPC réel de ~1,63 € (« agence communication ») à ~10,67 € (« agence "
        "google ads »). Meilleurs ratios volume/coût : « agence web » et "
        "« agence communication ». « agence marketing ia » est encore "
        "confidentiel (170/mois) mais en nette croissance — planter le drapeau "
        "IA maintenant coûte peu et installe le positionnement.",
        LIGHT, BLUE)

h2("Diagnostic du site (à vérifier — accès robot bloqué)")
bullets([
    "<b>Blocage robot</b> — le serveur renvoie 403 aux crawlers : à corriger "
    "en priorité (nuit au SEO, au suivi publicitaire et aux outils d'analyse).",
    "<b>Conversion</b> — traiter la home comme une landing page : promesse en "
    "5 s, preuve sociale, CTA unique (« Audit gratuit »).",
    "<b>Message match</b> — une page dédiée par service packagé, alignée sur "
    "les requêtes ci-dessus.",
    "<b>Pour affiner</b> : citer 3–5 concurrents nommément + accès GA4/Google "
    "Ads (lecture seule) → comparaison directe et baseline réelle.",
])

# =====================================================================
# 5. PLAN D'ACQUISITION
# =====================================================================
story.append(PageBreak())
h1("5. Plan d'acquisition payante de M&amp;B")
p("M&B vend des services marketing à des PME locales / B2B : il s'agit donc "
  "de <b>lead-gen B2B à intention élevée</b>, à ancrage <b>local</b> "
  "(Carcassonne / Occitanie). Recommandation de départ : <b>~3 000 €/mois</b>. "
  "Avec un CPC réel de 1,63 € à 10,67 € (cf. section 4) — et des déclinaisons "
  "locales souvent moins chères — un budget search de ~2 000 € achète de "
  "l'ordre de <b>500 à 800 clics/mois</b>, largement suffisant pour générer "
  "une première base de leads et de données d'optimisation.")
h2("Sélection des plateformes selon le budget")
table([
    ["Budget mensuel", "Mix recommandé", "Logique"],
    ["1 000–3 000 €", "Google Search seul", "Capter l'intention chaude"],
    ["3 000–5 000 € (départ)", "Google Search + Meta retargeting",
     "Intention + remarketing"],
    ["5 000 € +", "+ LinkedIn (si cible B2B)", "Ciblage fonction / secteur"],
], [40 * mm, 65 * mm, 60 * mm])

h2("Répartition recommandée (3 000 €/mois)")
table([
    ["Levier", "Budget", "Rôle"],
    ["Google Search (70%)", "~2 100 €",
     "Intention : « agence web [ville] », « agence marketing IA »…"],
    ["Meta retargeting (20%)", "~600 €",
     "Reciblage visiteurs + awareness locale (cas clients)"],
    ["Testing (10%)", "~300 €", "LinkedIn Thought Leader Ads / nouveaux angles"],
], [42 * mm, 24 * mm, 99 * mm])

h2("Architecture des campagnes")
p("Convention de nommage : <font face='Courier'>MB_[Plateforme]_[Objectif]_"
  "[Audience]_[Geo]_[Date]</font>")
bullets([
    "<b>Brand</b> (always-on) — protège la marque « M&B Agency ».",
    "<b>Google Search — Prospecting</b> : groupes « Création site web », "
    "« Publicité / Ads », et l'angle phare « Marketing IA ».",
    "<b>Meta — Retargeting</b> : visiteurs 7–30 j (offre Audit gratuit) + "
    "engagés (cas clients).",
    "<b>Testing</b> : LinkedIn Thought Leader Ads (le dirigeant = visage de "
    "l'agence).",
])

h2("Tracking à installer AVANT lancement (P1)")
table([
    ["Plateforme", "Client-side", "Server-side", "Conversion clé"],
    ["Google", "gtag.js", "Enhanced Conversions", "Formulaire + appel + RDV"],
    ["Meta", "Pixel", "CAPI", "Lead form / RDV"],
    ["GA4", "Oui", "—", "Parcours complet"],
], [30 * mm, 35 * mm, 50 * mm, 50 * mm])

# =====================================================================
# 6. CRÉATIF
# =====================================================================
h1("6. Stratégie créative")
p("Cinq piliers de contenu, tous conçus pour <b>démontrer l'IA en action</b> "
  "— « eat your own dog food » :")
table([
    ["Pilier", "Exemple d'angle pour M&B"],
    ["Pain point", "« Votre agence met 6 semaines pour un site ? »"],
    ["Preuve", "Captures de vos propres dashboards / CPA"],
    ["Démo", "Avant/après produit par IA (timelapse de production)"],
    ["Offre", "« Audit Ads IA gratuit en 48 h »"],
    ["Éducation", "« Comment on livre 5× plus vite avec Claude »"],
], [38 * mm, 127 * mm])
callout("Boucle vertueuse",
        "Produire les créatifs M&B avec vos propres skills (/ads create, "
        "/ads generate, /ads dna) prouve la méthode en l'appliquant à "
        "vous-mêmes.", LIGHT, ACCENT)

# =====================================================================
# 7. FEUILLE DE ROUTE
# =====================================================================
story.append(PageBreak())
h1("7. Feuille de route — 12 semaines")
table([
    ["Phase", "Semaines", "Actions clés"],
    ["Fondations", "S1–2",
     "Tracking, définir les 4 offres &amp; prix, landing « Audit gratuit », "
     "1er lot créatif"],
    ["Lancement", "S3–4",
     "Google Search d'abord (budget prudent), suivi quotidien, vérifier les "
     "conversions"],
    ["Optimisation", "S5–8",
     "Analyser 2 sem. de data, règle des 3× (couper les pertes), lancer Meta, "
     "A/B test landing"],
    ["Scale", "S9–12",
     "Scaler les gagnants (+20 %/sem max), tester LinkedIn, produire la 1re "
     "étude de cas"],
], [26 * mm, 20 * mm, 119 * mm])

h2("Objectifs (à calibrer après baseline)")
table([
    ["Métrique", "Mois 1", "Mois 3", "Mois 6"],
    ["Coût par lead (CPL)", "Baseline", "−20 %", "Cible"],
    ["Leads qualifiés / mois", "5–10", "15–25", "30 +"],
    ["RDV pris", "Testing", "Optimisation", "Scaling"],
], [50 * mm, 38 * mm, 38 * mm, 39 * mm])

# =====================================================================
# 8. PROCHAINES ACTIONS
# =====================================================================
h1("8. Vos 3 prochaines actions")
table([
    ["Quand", "Action"],
    ["Cette semaine", "Valider les 4 offres packagées + prix, monter la "
     "landing « Audit Ads IA gratuit »"],
    ["Avant lancement", "Installer le tracking (GA4 + Google Ads + Meta "
     "Pixel/CAPI)"],
    ["Démarrage", "Google Search ~2 000 €/mois, angle « Marketing IA » en "
     "campagne phare"],
], [34 * mm, 131 * mm])
sp(6)
rule()
story.append(Paragraph(
    "Document généré via le skill Claude Ads (/ads plan, template agence). "
    "Visibilité search et mots-clés issus de Semrush (base France). Le contenu "
    "on-page du site n'a pu être crawlé (serveur protégé — HTTP 403). "
    "Les prix d'offres et budgets sont indicatifs et à calibrer sur vos "
    "chiffres réels (panier moyen, marge, GA4/Google Ads).",
    styles["Small"]))


# ---- Footer / header ----
def decorate(canvas, doc):
    canvas.saveState()
    # top bar
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, fill=1, stroke=0)
    canvas.setFillColor(BLUE)
    canvas.rect(0, A4[1] - 6 * mm, 55 * mm, 6 * mm, fill=1, stroke=0)
    # footer
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(20 * mm, 10 * mm, "M&B Agency — Plan stratégique")
    canvas.drawRightString(A4[0] - 20 * mm, 10 * mm,
                           "Page %d" % doc.page)
    canvas.setStrokeColor(LGREY)
    canvas.setLineWidth(0.5)
    canvas.line(20 * mm, 13 * mm, A4[0] - 20 * mm, 13 * mm)
    canvas.restoreState()


doc = SimpleDocTemplate(
    "/home/user/claude-ads/MB-Agency-Plan-Strategique.pdf",
    pagesize=A4, topMargin=16 * mm, bottomMargin=18 * mm,
    leftMargin=20 * mm, rightMargin=20 * mm,
    title="M&B Agency — Plan stratégique", author="Claude Ads")
doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
print("PDF generated.")

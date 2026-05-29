#!/usr/bin/env python3
"""M&B Agency — Audit 360 stratégique (v2). Intègre Pennylane (MRR réel),
board GBM (base clients), Semrush (visibilité) et stratégie IA."""

from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, ListFlowable, ListItem,
)

NAVY = colors.HexColor("#0F1B3C")
BLUE = colors.HexColor("#2563EB")
ACCENT = colors.HexColor("#7C3AED")
LIGHT = colors.HexColor("#EEF2FF")
GREY = colors.HexColor("#475569")
LGREY = colors.HexColor("#E2E8F0")
GREEN = colors.HexColor("#16A34A")
GREENBG = colors.HexColor("#ECFDF5")
AMBER = colors.HexColor("#D97706")
AMBERBG = colors.HexColor("#FEF3C7")
RED = colors.HexColor("#DC2626")
REDBG = colors.HexColor("#FEF2F2")

styles = getSampleStyleSheet()
def S(n, **k): styles.add(ParagraphStyle(n, **k))
S("CoverTag", fontName="Helvetica-Bold", fontSize=11, leading=16, textColor=BLUE)
S("CoverTitle", fontName="Helvetica-Bold", fontSize=30, leading=34, textColor=NAVY)
S("CoverSub", fontName="Helvetica", fontSize=14, leading=20, textColor=GREY)
S("H1", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=NAVY, spaceBefore=14, spaceAfter=8)
S("H2", fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=BLUE, spaceBefore=11, spaceAfter=5)
S("Body", fontName="Helvetica", fontSize=10, leading=15, textColor=colors.HexColor("#1E293B"), alignment=TA_JUSTIFY, spaceAfter=6)
S("Bul", fontName="Helvetica", fontSize=10, leading=14, textColor=colors.HexColor("#1E293B"))
S("Small", fontName="Helvetica", fontSize=8.5, leading=12, textColor=GREY)
S("Cell", fontName="Helvetica", fontSize=8.6, leading=11.5, textColor=colors.HexColor("#1E293B"))
S("CellB", fontName="Helvetica-Bold", fontSize=8.6, leading=11.5, textColor=colors.white)
S("KpiNum", fontName="Helvetica-Bold", fontSize=22, leading=24, textColor=NAVY, alignment=1)
S("KpiLbl", fontName="Helvetica", fontSize=8, leading=10, textColor=GREY, alignment=1)
S("Callout", fontName="Helvetica", fontSize=9.5, leading=14, textColor=NAVY)

story = []
def h1(t): story.append(Paragraph(t, styles["H1"]))
def h2(t): story.append(Paragraph(t, styles["H2"]))
def p(t): story.append(Paragraph(t, styles["Body"]))
def sp(h=6): story.append(Spacer(1, h))
def rule(c=LGREY): story.append(HRFlowable(width="100%", thickness=0.8, color=c, spaceBefore=4, spaceAfter=8))
def bullets(items):
    story.append(ListFlowable([ListItem(Paragraph(t, styles["Bul"]), leftIndent=6, value="•") for t in items],
                 bulletType="bullet", start="•", bulletColor=BLUE, leftIndent=10, spaceAfter=6))
def table(data, cw, header=True, zebra=True):
    rows=[]
    for r,row in enumerate(data):
        rows.append([Paragraph(str(c), styles["CellB" if (header and r==0) else "Cell"]) for c in row])
    t=Table(rows, colWidths=cw, repeatRows=1 if header else 0)
    ts=[("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("LINEBELOW",(0,0),(-1,-1),0.4,LGREY)]
    if header: ts+=[("BACKGROUND",(0,0),(-1,0),NAVY),("TOPPADDING",(0,0),(-1,0),7),("BOTTOMPADDING",(0,0),(-1,0),7)]
    if zebra:
        st=1 if header else 0
        for i in range(st,len(data)):
            if (i-st)%2==1: ts.append(("BACKGROUND",(0,i),(-1,i),LIGHT))
    t.setStyle(TableStyle(ts)); story.append(t); sp(8)
def callout(title, text, bg=LIGHT, bar=BLUE):
    inner=[[Paragraph(f'<b>{title}</b><br/>{text}', styles["Callout"])]]
    t=Table(inner, colWidths=[165*mm])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),("LEFTPADDING",(0,0),(-1,-1),12),
        ("RIGHTPADDING",(0,0),(-1,-1),12),("TOPPADDING",(0,0),(-1,-1),9),("BOTTOMPADDING",(0,0),(-1,-1),9),
        ("LINEBEFORE",(0,0),(0,-1),3,bar)])); story.append(t); sp(8)
def kpis(items):
    cells=[[Paragraph(v,styles["KpiNum"]) for v,_ in items],[Paragraph(l,styles["KpiLbl"]) for _,l in items]]
    w=165*mm/len(items)
    t=Table(cells, colWidths=[w]*len(items))
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),LIGHT),("TOPPADDING",(0,0),(-1,0),10),
        ("BOTTOMPADDING",(0,1),(-1,1),10),("TOPPADDING",(0,1),(-1,1),0),("LINEAFTER",(0,0),(-2,-1),0.5,colors.white)]))
    story.append(t); sp(10)

# ============ COVER ============
story.append(Spacer(1, 38*mm))
story.append(Paragraph("AUDIT STRATÉGIQUE 360°", styles["CoverTag"])); sp(4)
story.append(Paragraph("M&amp;B Agency", styles["CoverTitle"]))
story.append(Paragraph("Référencement local, IA &amp; croissance du récurrent", styles["CoverSub"]))
sp(16); story.append(HRFlowable(width="40%", thickness=2.5, color=BLUE, hAlign="LEFT", spaceAfter=14))
meta=[["Préparé pour","Direction M&B Agency"],
      ["Périmètre","Finances · Base clients · Visibilité · Stratégie IA · Acquisition"],
      ["Sources de données","Pennylane (abonnements) · Monday board GBM · Semrush (FR)"],
      ["Date",datetime.now().strftime("%d/%m/%Y")]]
mt=Table(meta, colWidths=[42*mm,108*mm])
mt.setStyle(TableStyle([("FONT",(0,0),(0,-1),"Helvetica-Bold",9.5),("FONT",(1,0),(1,-1),"Helvetica",9.5),
    ("TEXTCOLOR",(0,0),(0,-1),BLUE),("TEXTCOLOR",(1,0),(1,-1),GREY),("TOPPADDING",(0,0),(-1,-1),5),
    ("BOTTOMPADDING",(0,0),(-1,-1),5),("LEFTPADDING",(0,0),(0,-1),0)]))
story.append(mt); story.append(PageBreak())

# ============ 1. SYNTHÈSE ============
h1("1. Synthèse exécutive")
p("Cet audit s'appuie sur les <b>données réelles</b> de M&B Agency : revenus "
  "d'abonnement (Pennylane), base clients opérationnelle (board GBM) et "
  "visibilité search (Semrush). Le diagnostic révèle une agence <b>plus solide "
  "et plus spécialisée</b> que son image ne le laisse penser — mais exposée à "
  "un risque de concentration et sous-exploitée sur deux leviers : "
  "l'<b>upsell IA</b> de sa base et sa <b>propre acquisition</b>.")
kpis([("9 508 €","MRR (HT/mois)"),("~114 K€","ARR annualisé"),("~17","clients récurrents"),("528 €","panier moyen/mois")])
h2("Les 4 constats qui structurent le plan")
bullets([
    "<b>Une agence de référencement local récurrent</b>, pas une agence web "
    "généraliste : le cœur de revenu est la gestion Google Business (forfaits "
    "GMB / GMB+ / GMB+Blog), confirmé par une visibilité SEO web quasi nulle.",
    "<b>Risque de concentration élevé</b> : 3 clients pèsent <b>69 % du MRR</b>. "
    "Priorité défensive n°1.",
    "<b>Forfaits déjà productisés</b> : l'opportunité n'est pas de packager "
    "(c'est fait) mais d'<b>ajouter une couche IA</b> pour monter en gamme.",
    "<b>Le cordonnier mal chaussé</b> : la fiche « Interne MB Agency » est « en "
    "retard » et le site est invisible — à corriger pour en faire la 1re preuve.",
])

# ============ 2. SANTÉ FINANCIÈRE ============
h1("2. Santé financière (données Pennylane)")
p("Revenu mensuel récurrent (MRR) calculé sur les abonnements actifs reconduits, "
  "hors taxes. Un abonnement en fin de contrat sans reconduction (Cédric "
  "Migrenne) est exclu et signalé comme churn à surveiller.")
h2("Concentration du revenu — le risque n°1")
table([
    ["Segment","Clients","MRR (HT)","Part du MRR"],
    ["Gros comptes (≥ 500 €)","3","6 570 €","69 %"],
    ["Comptes moyens (150–500 €)","9","2 428 €","26 %"],
    ["Petits comptes (< 150 €)","6","510 €","5 %"],
], [60*mm,25*mm,40*mm,40*mm])
callout("⚠ Vulnérabilité critique",
        "Les 3 plus gros comptes (FUXEDIS 3 225 €, LFC HUMAIN 1 890 €, T.P.L.M. "
        "1 455 €) représentent <b>69 % du MRR</b>. La perte du seul FUXEDIS = "
        "−34 % de revenu récurrent. Sécuriser ces comptes (preuve de valeur, "
        "reporting, contrats) est la priorité défensive immédiate.",
        REDBG, RED)
h2("Top abonnements (MRR HT mensuel)")
table([
    ["Client","MRR/mois","Profil"],
    ["SAS FUXEDIS","3 225 €","Gros compte — à sécuriser"],
    ["LFC HUMAIN","1 890 €","Gros compte — à sécuriser"],
    ["T.P.L.M.","1 455 €","Gros compte — à sécuriser"],
    ["STAR LOC EVENT'S","467 €","Événementiel"],
    ["RDP GROUPE SUSHI","467 €","Restauration"],
    ["Agence Poêle &amp; Cheminée","585 € (2 abos)","Artisan/Habitat"],
    ["GR Matériels · Liechti · Buffet Vietnam…","79–235 €","Longue traîne GMB"],
], [70*mm,30*mm,65*mm])

# ============ 3. BASE CLIENTS GBM ============
h1("3. Base clients &amp; opérations (board GBM)")
p("Le board Monday confirme le positionnement : M&B gère la présence Google "
  "Business d'une base de PME locales, organisée en forfaits et verticales claires.")
h2("Forfaits en place (déjà productisés)")
table([
    ["Forfait","Nature","Levier IA à ajouter"],
    ["GMB","Gestion fiche de base","Posts auto + réponses avis IA"],
    ["GMB / RS","+ réseaux sociaux","Calendrier + visuels générés IA"],
    ["GMB +","Offre enrichie","Reporting IA + optimisation continue"],
    ["GMB + Blog","+ contenu éditorial","Rédaction SEO local assistée IA"],
    ["Catalogues","Production de supports","Génération créative accélérée"],
], [34*mm,55*mm,76*mm])
h2("Verticales dominantes")
bullets([
    "<b>Restauration / Food</b> (An Sushi, Buffet Vietnam, RDP Sushi, Le Restaurant du Japon…)",
    "<b>Artisans / Habitat</b> (Poêle &amp; Cheminée, Liechti Plomberie, Cuisines Maxima…)",
    "<b>Services / Loisirs</b> (Padel Tolosa, Clean Car, Aud'Étour…)",
    "<b>Retail / Multi-sites</b> (Cuisines Maxima, Maxiburo…)",
])
callout("Signal opérationnel",
        "Plusieurs fiches sont « à faire » et la fiche interne est « en retard ». "
        "Si la capacité de production limite la croissance, l'IA (génération de "
        "posts/visuels en masse) débloque directement du temps facturable.",
        AMBERBG, AMBER)

# ============ 4. VISIBILITÉ ============
story.append(PageBreak())
h1("4. Visibilité &amp; concurrence (Semrush, FR)")
table([
    ["Indicateur (base FR)","Valeur","Lecture"],
    ["Mots-clés organiques","17","Empreinte SEO web quasi nulle"],
    ["Trafic organique estimé","~29 visites/mois","Marginal"],
    ["Mots-clés / trafic payant","0 / 0","Aucune publicité diffusée"],
    ["Ancrage","Carcassonne / Occitanie","Requêtes locales faibles (#5–#29)"],
    ["Accès robot du site","Bloqué (HTTP 403)","Nuit au SEO &amp; au suivi — à corriger"],
], [52*mm,42*mm,71*mm])
p("Cohérent avec le diagnostic : la valeur de M&B est dans le <b>récurrent "
  "local (GMB)</b>, pas dans le SEO web. Mais l'agence ne fait <b>aucune "
  "acquisition payante</b> — un levier entièrement inexploité.")
h2("Concurrents locaux (aucun ne domine, aucun ne fait de Google Ads)")
table([
    ["Concurrent","Mots-clés","Trafic/mois","Note"],
    ["miseenligne.com","77","~168","Le plus visible"],
    ["linkeo-toulouse.com","105","~46","Réseau régional"],
    ["agencewebcarcassonne.com","14","~6","Rival direct (même ville)"],
    ["artdim.fr · vert-agence.fr","40 / 41","~65 / ~30","Concurrents régionaux"],
], [52*mm,25*mm,28*mm,60*mm])
h2("Opportunité mots-clés (CPC réels FR)")
table([
    ["Mot-clé","Vol./mois","CPC","Lecture"],
    ["agence communication","5 400","1,63 €","Meilleur ratio volume/coût"],
    ["agence web","14 800","2,18 €","Cœur de cible"],
    ["agence marketing ia","170","2,30 €","Émergent, tendance ↑ — capter tôt"],
    ["création / refonte site","6 600 / 2 900","3,97 / 6,68 €","Intention d'achat forte"],
], [50*mm,28*mm,22*mm,65*mm])

# ============ 5. STRATÉGIE ============
h1("5. Plan stratégique")
h2("A. Repositionnement")
p("Angle : <b>« L'agence de visibilité locale augmentée par l'IA »</b>. "
  "Ne pas vendre « on utilise l'IA » (banalisé) mais le <b>résultat</b> : plus "
  "de posts, de visuels et d'avis traités, plus vite, à coût maîtrisé — prouvé "
  "sur la propre fiche et les propres campagnes de M&B.")
h2("B. Upsell IA de la base (croissance sans acquisition)")
p("Levier le plus rentable à court terme : faire monter les forfaits GMB "
  "existants vers une version « +IA ». Hypothèse prudente : +60 €/mois HT sur "
  "~12 clients de la longue traîne et du segment moyen.")
table([
    ["Scénario d'upsell","Clients visés","MRR additionnel"],
    ["Conservateur (+60 €, 8 clients)","8","+480 €/mois (+5,8 K€/an)"],
    ["Réaliste (+60 €, 12 clients)","12","+720 €/mois (+8,6 K€/an)"],
    ["Ambitieux (+90 €, 14 clients)","14","+1 260 €/mois (+15,1 K€/an)"],
], [60*mm,30*mm,75*mm])
callout("Pourquoi commencer par là",
        "Vendre à un client existant coûte bien moins cher que d'en acquérir un. "
        "Le scénario réaliste ajoute ~8,6 K€ d'ARR sans un euro de publicité — "
        "et crée les premières preuves IA pour la prospection.",
        GREENBG, GREEN)
h2("C. Acquisition payante (diversifier le risque)")
p("Objectif : faire grossir le <b>segment moyen (250–500 €)</b> pour réduire la "
  "dépendance aux 3 gros comptes. Budget de départ ~2 000–3 000 €/mois.")
table([
    ["Levier","Budget","Rôle"],
    ["Google Search (70%)","~2 100 €","« agence GMB / visibilité Google » + local + IA"],
    ["Meta retargeting (20%)","~600 €","Reciblage + preuves (cas clients)"],
    ["Testing (10%)","~300 €","LinkedIn Thought Leader Ads (dirigeant)"],
], [42*mm,24*mm,99*mm])

# ============ 6. ROADMAP ============
story.append(PageBreak())
h1("6. Feuille de route &amp; priorités")
table([
    ["Priorité","Action","Horizon"],
    ["🔴 P1 défensif","Sécuriser FUXEDIS, LFC HUMAIN, T.P.L.M. (reporting de "
     "valeur, point contractuel, anticipation churn)","Immédiat"],
    ["🔴 P1 preuve","Remettre à niveau la fiche « Interne MB Agency » + tracking "
     "site (lever le 403) → 1re étude de cas","2 semaines"],
    ["🟡 P2 revenu","Lancer l'offre « GMB +IA » et l'upseller à 12 clients "
     "(scénario réaliste : +8,6 K€ ARR)","1–2 mois"],
    ["🟡 P2 process","Industrialiser la production de posts/visuels par IA pour "
     "résorber les fiches « à faire »","1–2 mois"],
    ["🟢 P3 acquisition","Campagnes Google Search local + IA (~2 000 €/mois) "
     "pour nourrir le segment moyen","Mois 2–3"],
], [26*mm,104*mm,30*mm])
h2("Objectifs 6 mois (à valider)")
table([
    ["Indicateur","Aujourd'hui","Cible 6 mois"],
    ["MRR","9 508 €","≥ 11 000 € (+upsell +acquisition)"],
    ["Part des 3 gros comptes","69 %","< 60 % (diversification)"],
    ["Clients en abonnement","~17","20–22"],
    ["Publicité diffusée","0 €","~2 000 €/mois, CPL suivi"],
], [50*mm,35*mm,65*mm])
sp(6); rule()
story.append(Paragraph(
    "Audit généré via le skill Claude Ads. Données : Pennylane (abonnements "
    "actifs, MRR HT), board Monday GBM (forfaits/statuts), Semrush (visibilité "
    "FR). Le contenu on-page du site n'a pu être crawlé (HTTP 403). Montants "
    "d'upsell = hypothèses à calibrer avec la direction.", styles["Small"]))

def decorate(c, d):
    c.saveState()
    c.setFillColor(NAVY); c.rect(0,A4[1]-6*mm,A4[0],6*mm,fill=1,stroke=0)
    c.setFillColor(BLUE); c.rect(0,A4[1]-6*mm,55*mm,6*mm,fill=1,stroke=0)
    c.setFillColor(GREY); c.setFont("Helvetica",8)
    c.drawString(20*mm,10*mm,"M&B Agency — Audit stratégique 360°")
    c.drawRightString(A4[0]-20*mm,10*mm,"Page %d"%d.page)
    c.setStrokeColor(LGREY); c.setLineWidth(0.5); c.line(20*mm,13*mm,A4[0]-20*mm,13*mm)
    c.restoreState()

doc=SimpleDocTemplate("/home/user/claude-ads/MB-Agency-Audit-360.pdf", pagesize=A4,
    topMargin=16*mm, bottomMargin=18*mm, leftMargin=20*mm, rightMargin=20*mm,
    title="M&B Agency — Audit stratégique 360", author="Claude Ads")
doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
print("PDF v2 generated.")

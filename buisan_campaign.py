#!/usr/bin/env python3
"""Marbrerie Buisan — Google Ads campaign builder.
Generates a Google Ads Editor import CSV + a readable brief.
Character limits validated (RSA: headlines<=30, descriptions<=90)."""

import csv

CAMPAIGN = "BUISAN_Search_Local_2026"
DAILY_BUDGET = 23.00  # ~700€/mois
GEO = "Carcassonne + 30 km (rayon) ; option : département Aude (11)"

# ---- Ad groups: keyword (match type via formatting) ----
# Google Ads Editor: "Broad" = plain, '"phrase"' = phrase, '[exact]' = exact
ADGROUPS = {
    "Plans de travail": [
        ('plan de travail granit', "Phrase", 0.58, 6600),
        ('plan de travail quartz', "Phrase", 0.67, 4400),
        ('plan de travail marbre', "Phrase", 0.57, 4400),
        ('plan de travail sur mesure', "Phrase", 0.56, 8100),
        ('plan de travail cuisine', "Phrase", 0.60, 33100),
        ('plan de travail sur mesure granit', "Exact", 0.72, 170),
    ],
    "Marbrerie generale": [
        ('marbrerie', "Phrase", 0.92, 6600),
        ('marbrier', "Phrase", 0.92, 4400),
        ('marbrerie aude', "Exact", 0.59, 20),
        ('marbrerie carcassonne', "Exact", 0.00, 20),
        ('marbrier carcassonne', "Exact", 0.00, 10),
    ],
    "Funeraire": [
        ('monument funéraire', "Phrase", 0.59, 2900),
        ('pierre tombale', "Phrase", 0.72, 9900),
        ('marbrerie funéraire', "Phrase", 0.91, 1300),
    ],
    "Deco sur mesure": [
        ('table en marbre', "Phrase", 0.58, 3600),
        ('vasque en pierre', "Phrase", 0.71, 2400),
        ('escalier en pierre', "Phrase", 0.50, 590),
        ('cheminée en marbre', "Phrase", 0.58, 170),
    ],
}

NEGATIVES = [
    "emploi", "recrutement", "salaire", "formation", "métier", "fiche métier",
    "définition", "wikipedia", "leroy merlin", "castorama", "ikea", "brico",
    "occasion", "gratuit", "pas cher", "leboncoin", "stratifié", "bois",
    "nettoyer", "entretien", "réparer", "rénover soi même", "diy",
    "salaire marbrier", "cap marbrier",
]

# RSA assets per ad group (headlines<=30, descriptions<=90)
RSA = {
    "Plans de travail": {
        "headlines": [
            "Plan de Travail Sur Mesure",      # 26
            "Granit, Quartz & Marbre",          # 24
            "Marbrerie à Carcassonne",          # 24
            "Devis Gratuit en 48h",             # 21
            "Pose par des Experts",             # 20
            "Cuisine & Salle de Bain",          # 24
            "Fabrication Française",             # 22
            "Showroom dans l'Aude",             # 20
            "Matériaux Haut de Gamme",          # 24
            "Conseil Personnalisé",             # 21
            "Sur Mesure & Découpe Précise",     # 28
            "Demandez Votre Devis",             # 21
            "Artisan Marbrier Local",           # 23
            "Qualité & Finitions Soignées",     # 28
            "Plan de Travail Granit",           # 23
        ],
        "descriptions": [
            "Plans de travail sur mesure en granit, quartz et marbre. Devis gratuit sous 48h.",   # 81
            "Marbrerie artisanale dans l'Aude. Conseil, fabrication et pose par nos experts.",     # 80
            "Cuisine, salle de bain : sublimez vos espaces avec une pierre de qualité.",           # 74
            "Demandez votre devis gratuit. Showroom et accompagnement personnalisé.",              # 71
        ],
    },
    "Marbrerie generale": {
        "headlines": [
            "Marbrerie à Carcassonne",          # 24
            "Artisan Marbrier dans l'Aude",     # 28
            "Granit, Quartz, Marbre",           # 23
            "Devis Gratuit & Rapide",           # 23
            "Savoir-Faire Artisanal",           # 23
            "Sur Mesure pour Vos Projets",      # 28
            "Showroom à Visiter",               # 19
            "Pose & Fabrication Expert",        # 26
            "Marbrerie de Confiance",           # 23
            "Conseil Personnalisé",             # 21
            "Pierre Naturelle de Qualité",      # 28
            "Demandez Votre Devis",             # 21
            "Plans, Déco & Funéraire",          # 24
            "Travail Soigné Garanti",           # 23
            "Marbrier Local Réactif",           # 23
        ],
        "descriptions": [
            "Marbrerie artisanale à Carcassonne. Plans de travail, déco et funéraire sur mesure.", # 84
            "Granit, quartz, marbre : un savoir-faire au service de vos projets. Devis gratuit.",  # 83
            "Conseil personnalisé et pose par nos experts. Visitez notre showroom dans l'Aude.",   # 82
            "Un projet en pierre ? Demandez votre devis gratuit et sans engagement dès aujourd'hui.", # 87
        ],
    },
    "Funeraire": {
        "headlines": [
            "Monuments Funéraires",             # 21
            "Marbrerie Funéraire Aude",         # 25
            "Création Sur Mesure",              # 20
            "Accompagnement Respectueux",       # 26
            "Pierres Tombales Granit",          # 24
            "Devis Gratuit & Discret",          # 24
            "Savoir-Faire Artisanal",           # 23
            "Hommage Personnalisé",             # 21
            "Marbrier à Carcassonne",           # 23
            "Qualité & Durabilité",             # 21
            "Conseil avec Bienveillance",       # 27
            "Monuments Personnalisés",          # 24
            "Granit Haute Qualité",             # 21
            "À Vos Côtés dans l'Aude",          # 24
            "Demandez un Devis",                # 18
        ],
        "descriptions": [
            "Monuments funéraires sur mesure en granit. Accompagnement respectueux et discret.",   # 82
            "Marbrerie funéraire dans l'Aude. Création personnalisée pour un hommage durable.",     # 80
            "Conseil avec bienveillance et devis gratuit. Un savoir-faire artisanal reconnu.",      # 80
            "Pierres tombales et monuments de qualité. À vos côtés pour chaque étape du projet.",   # 84
        ],
    },
    "Deco sur mesure": {
        "headlines": [
            "Décoration en Pierre",             # 21
            "Tables & Vasques Marbre",          # 24
            "Escaliers en Pierre",              # 20
            "Cheminées sur Mesure",             # 21
            "Création Personnalisée",           # 23
            "Granit, Marbre, Quartz",           # 23
            "Artisan Marbrier Aude",            # 22
            "Devis Gratuit en 48h",             # 21
            "Pièces Uniques & Design",          # 24
            "Showroom à Carcassonne",           # 23
            "Sublimez Votre Intérieur",         # 25
            "Finitions Haut de Gamme",          # 24
            "Sur Mesure pour Vous",             # 21
            "Savoir-Faire Artisanal",           # 23
            "Demandez Votre Devis",             # 21
        ],
        "descriptions": [
            "Tables, vasques, escaliers, cheminées en pierre sur mesure. Devis gratuit sous 48h.", # 84
            "Sublimez votre intérieur avec des pièces uniques en marbre, granit ou quartz.",       # 78
            "Création personnalisée par un artisan marbrier de l'Aude. Finitions haut de gamme.",  # 82
            "Un projet déco en pierre ? Visitez notre showroom et demandez votre devis gratuit.",  # 82
        ],
    },
}

SITELINKS = [
    ("Plans de Travail", "Granit, quartz, marbre", "Sur mesure pour votre cuisine"),
    ("Monuments Funéraires", "Création sur mesure", "Accompagnement respectueux"),
    ("Décoration en Pierre", "Tables, vasques, escaliers", "Pièces uniques sur mesure"),
    ("Demander un Devis", "Gratuit et sans engagement", "Réponse sous 48h"),
]
CALLOUTS = ["Devis gratuit", "Pose par experts", "Fabrication française",
            "Showroom dans l'Aude", "Sur mesure", "Conseil personnalisé"]
SNIPPETS = ("Matériaux", ["Granit", "Quartz", "Marbre", "Pierre naturelle"])

def check_limits():
    issues = []
    for ag, a in RSA.items():
        for h in a["headlines"]:
            if len(h) > 30: issues.append(f"[{ag}] HEADLINE {len(h)}>30: {h}")
        for d in a["descriptions"]:
            if len(d) > 90: issues.append(f"[{ag}] DESC {len(d)}>90: {d}")
    return issues

def write_csv(path):
    rows = []
    # Keywords sheet (Editor multi-type import via one column set)
    # We emit a unified CSV that Google Ads Editor accepts for keywords + ads.
    header = ["Campaign","Ad Group","Keyword","Match Type","Max CPC",
              "Headline 1","Headline 2","Headline 3","Description 1","Description 2"]
    rows.append(header)
    # Keywords
    for ag, kws in ADGROUPS.items():
        for kw, mt, cpc, vol in kws:
            rows.append([CAMPAIGN, ag, kw, mt, "", "","","","",""])
    # Negative keywords (campaign level)
    for n in NEGATIVES:
        rows.append([CAMPAIGN, "", n, "Campaign Negative Broad", "", "","","","",""])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerows(rows)

def write_rsa_csv(path):
    # RSA-specific CSV (one row per ad group with up to 15 headlines / 4 desc)
    maxh, maxd = 15, 4
    header = ["Campaign","Ad Group","Ad type"] + \
             [f"Headline {i+1}" for i in range(maxh)] + \
             [f"Description {i+1}" for i in range(maxd)] + ["Final URL"]
    rows = [header]
    for ag, a in RSA.items():
        row = [CAMPAIGN, ag, "Responsive search ad"]
        hs = (a["headlines"] + [""]*maxh)[:maxh]
        ds = (a["descriptions"] + [""]*maxd)[:maxd]
        row += hs + ds + ["https://www.marbrerie-buisan.fr/"]
        rows.append(row)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerows(rows)

if __name__ == "__main__":
    issues = check_limits()
    print("=== Character-limit validation ===")
    print("OK — all headlines<=30 and descriptions<=90" if not issues else "\n".join(issues))
    write_csv("/home/user/claude-ads/buisan-keywords-negatives.csv")
    write_rsa_csv("/home/user/claude-ads/buisan-responsive-search-ads.csv")
    # Counts
    nk = sum(len(v) for v in ADGROUPS.values())
    print(f"\nAd groups: {len(ADGROUPS)} | Keywords: {nk} | Negatives: {len(NEGATIVES)} | RSAs: {len(RSA)}")
    print("Files: buisan-keywords-negatives.csv, buisan-responsive-search-ads.csv")

"""
Gazetteer of Tunisia's administrative regions, bilingual (French/Arabic).

Structure:
  GOVERNORATES: canonical_name -> list of surface-form variants
      (spelling variants, with/without accents, common alternates)
  DELEGATION_TO_GOVERNORATE: delegation/city/town name variant
      -> canonical governorate name it belongs to.
      This lets "Ain Draham" or "Djerba" resolve up to "Jendouba" /
      "Médenine" even though the article never names the governorate
      directly -- which, from the real Nessma/Mosaique/Watania samples
      pulled during feasibility testing, is extremely common (Tunisian
      news almost always leads with the town/delegation name, not the
      governorate).

This is a STARTING set (24 governorates fully covered; delegations
cover the ones observed during feasibility testing plus other
well-known towns). It is intentionally a plain Python dict, not a
database, so it's trivial to keep extending as you encounter new place
names in real scraped data -- see `add_missing_places.py` idea in the
README for a suggested workflow.
"""

# --- 24 governorates: canonical name -> variants (FR + AR) --------------
GOVERNORATES: dict[str, list[str]] = {
    "Tunis": ["Tunis", "تونس"],
    "Ariana": ["Ariana", "L'Ariana", "أريانة"],
    "Ben Arous": ["Ben Arous", "بن عروس"],
    "Manouba": ["Manouba", "La Manouba", "منوبة"],
    "Nabeul": ["Nabeul", "نابل"],
    "Zaghouan": ["Zaghouan", "زغوان"],
    "Bizerte": ["Bizerte", "بنزرت", "بنزرت"],
    "Béja": ["Béja", "Beja", "باجة"],
    "Jendouba": ["Jendouba", "جندوبة"],
    "Le Kef": ["Le Kef", "Kef", "الكاف"],
    "Siliana": ["Siliana", "سليانة"],
    "Kairouan": ["Kairouan", "القيروان"],
    "Kasserine": ["Kasserine", "القصرين"],
    "Sidi Bouzid": ["Sidi Bouzid", "سيدي بوزيد"],
    "Sousse": ["Sousse", "سوسة"],
    "Monastir": ["Monastir", "المنستير"],
    "Mahdia": ["Mahdia", "المهدية"],
    "Sfax": ["Sfax", "صفاقس"],
    "Gafsa": ["Gafsa", "قفصة"],
    "Tozeur": ["Tozeur", "توزر"],
    "Kebili": ["Kebili", "Kébili", "قبلي"],
    "Gabès": ["Gabès", "Gabes", "قابس"],
    "Médenine": ["Médenine", "Medenine", "مدنين"],
    "Tataouine": ["Tataouine", "تطاوين"],
}

# --- delegations / cities / towns -> parent governorate ------------------
DELEGATION_TO_GOVERNORATE: dict[str, str] = {
    # Tunis
    "Bab Souika": "Tunis", "La Marsa": "Tunis", "Le Bardo": "Tunis",
    "Carthage": "Tunis", "Sidi Bou Said": "Tunis", "Bab Bhar": "Tunis",
    "باب سويقة": "Tunis", "قرطاج": "Tunis",

    # Ariana
    "Raoued": "Ariana", "La Soukra": "Ariana", "Ettadhamen": "Ariana",

    # Ben Arous
    "Hammam-Lif": "Ben Arous", "Hammam Lif": "Ben Arous", "Radès": "Ben Arous",
    "Rades": "Ben Arous", "Mornag": "Ben Arous", "Mégrine": "Ben Arous",

    # Nabeul (Cap Bon)
    "Hammamet": "Nabeul", "Kelibia": "Nabeul", "Menzel Temime": "Nabeul",
    "Grombalia": "Nabeul", "Takelsa": "Nabeul", "Bou Argoub": "Nabeul",
    "El Haouaria": "Nabeul", "Haouaria": "Nabeul", "Slimane": "Nabeul",
    "Sidi Daoud": "Nabeul", "Cap Bon": "Nabeul", "Beni Khalled": "Nabeul",
    "Korba": "Nabeul",

    # Zaghouan
    "Zriba": "Zaghouan", "Nadhour": "Zaghouan", "Bir Mcherga": "Zaghouan",

    # Bizerte
    "Bizerte-Sud": "Bizerte", "Bizerte Sud": "Bizerte", "Ghar El Melh": "Bizerte",
    "Sejnane": "Bizerte", "Menzel Bourguiba": "Bizerte", "Mateur": "Bizerte",
    "Ras Jebel": "Bizerte", "El Alia": "Bizerte", "Sidi Ali El Mekki": "Bizerte",
    "El Houichet": "Bizerte",

    # Béja
    "Testour": "Béja", "Nefza": "Béja", "Medjez el-Bab": "Béja",
    "Amdoun": "Béja", "Djebba": "Béja",

    # Jendouba
    "Ain Draham": "Jendouba", "Aïn Draham": "Jendouba", "Tabarka": "Jendouba",
    "Ghardimaou": "Jendouba", "Bulla Regia": "Jendouba", "Fernana": "Jendouba",
    "El Feija": "Jendouba", "Dar Fatma": "Jendouba",

    # Le Kef
    "Sakiet Sidi Youssef": "Le Kef", "Dahmani": "Le Kef", "Nebeur": "Le Kef",

    # Siliana
    "Bargou": "Siliana", "Bou Arada": "Siliana", "Makthar": "Siliana",
    "Djebel Bargou": "Siliana", "Jebel Bargou": "Siliana",

    # Kairouan
    "Oueslatia": "Kairouan", "Haffouz": "Kairouan", "Sbikha": "Kairouan",
    "Ksar Lemsa": "Kairouan",

    # Kasserine
    "Sbeitla": "Kasserine", "Feriana": "Kasserine", "Thala": "Kasserine",
    "Jebel Semmama": "Kasserine", "Djebel Semmama": "Kasserine",

    # Sidi Bouzid
    "Regueb": "Sidi Bouzid", "Rgueb": "Sidi Bouzid", "Meknassy": "Sidi Bouzid",
    "Mazouna": "Sidi Bouzid",

    # Sousse
    "Kalaa Kebira": "Sousse", "Msaken": "Sousse", "Hammam Sousse": "Sousse",
    "Akouda": "Sousse",

    # Monastir
    "Moknine": "Monastir", "Ksar Hellal": "Monastir", "Jemmal": "Monastir",
    "Jemmel": "Monastir", "Sahline": "Monastir", "Sayada": "Monastir",
    "Touza": "Monastir",

    # Mahdia
    "Salakta": "Mahdia", "Ksour Essef": "Mahdia", "El Jem": "Mahdia",
    "Chebba": "Mahdia", "Sebkha Ben Ghayadha": "Mahdia",

    # Sfax
    "Kerkennah": "Sfax", "Jebeniana": "Sfax", "Sakiet Eddaier": "Sfax",
    "Mahres": "Sfax",

    # Gafsa
    "Métlaoui": "Gafsa", "Metlaoui": "Gafsa", "Redeyef": "Gafsa",
    "Om Ali": "Gafsa", "Jebel Selja": "Gafsa",

    # Tozeur
    "Nefta": "Tozeur", "Degache": "Tozeur", "Dégache": "Tozeur",
    "Hezoua": "Tozeur",

    # Kebili
    "Douz": "Kebili", "Souk Lahad": "Kebili",

    # Gabès
    "Métouia": "Gabès", "Menzel Habib": "Gabès", "Chott Essalem": "Gabès",

    # Médenine
    "Djerba": "Médenine", "Jerba": "Médenine", "Zarzis": "Médenine",
    "Ben Gardane": "Médenine", "Houmt Souk": "Médenine", "Midoun": "Médenine",

    # Tataouine
    "Dhehiba": "Tataouine", "Remada": "Tataouine", "Ghomrassen": "Tataouine",
}

# Multi-governorate regional labels sometimes used editorially instead of
# a single governorate name -- kept separate since they don't map 1:1.
REGIONAL_LABELS = {
    "Grand Tunis": ["Tunis", "Ariana", "Ben Arous", "Manouba"],
    "Cap Bon": ["Nabeul"],
    "Sahel": ["Sousse", "Monastir", "Mahdia"],
}

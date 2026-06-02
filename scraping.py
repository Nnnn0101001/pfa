#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper Immobilier Marocain — VRAI SCRAPING
===========================================
Sites : Avito.ma + Mubawab.ma
Cible : 10 000+ annonces réelles

Structure réelle observée :
  AVITO   : "Appartements dans Casablanca, Racine · Titre · 4 chambre(s) · 3 sdb(s) · 190 m² · Étage 3 · 3 800 000 DH · Agence · il y a 13h"
  MUBAWAB : "Prix 1 600 000 DH · 3 chambres · 3 salles de bains · 159 m² · 4 pièces · Bon état · Ascenseur · Belvédère, Casablanca"

Usage :
  pip install requests beautifulsoup4 lxml pandas
  python scraper_reel.py
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import re, time, random, logging, os
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

HEADERS_POOL = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "fr-MA,fr;q=0.9",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
        "Accept-Language": "fr;q=0.9,ar;q=0.8",
        "Connection": "keep-alive",
    },
]

# ── Helpers communs ───────────────────────────────────────────────────────────

def get_session():
    s = requests.Session()
    s.headers.update(random.choice(HEADERS_POOL))
    return s


def fetch(session, url, retries=4, base_delay=2.5):
    for attempt in range(retries):
        try:
            delay = base_delay + random.uniform(0, 2) + attempt * 1.5
            time.sleep(delay)
            resp = session.get(url, timeout=20)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 403:
                log.warning(f"  403 Forbidden — {url[:60]}")
                time.sleep(random.uniform(8, 15))
            elif resp.status_code == 429:
                log.warning(f"  429 Rate limit — attente 30s")
                time.sleep(30)
            else:
                log.warning(f"  HTTP {resp.status_code} — {url[:60]}")
        except requests.exceptions.RequestException as e:
            log.warning(f"  Tentative {attempt+1}/{retries} — {str(e)[:50]}")
            time.sleep(random.uniform(5, 10))
    return None


def clean_int(txt):
    if not txt:
        return None
    n = re.sub(r"[^\d]", "", str(txt))
    return int(n) if n else None


def clean_float(txt):
    if not txt:
        return None
    txt = str(txt).replace(",", ".").replace(" ", "")
    m = re.search(r"[\d.]+", txt)
    return float(m.group()) if m else None


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPER AVITO.MA
# Structure réelle : article avec data-id, paragraphes avec localisation,
# titre, attributs (X chambre(s) · Y sdb(s) · Z m² · Étage N), prix, agence, date
# ══════════════════════════════════════════════════════════════════════════════

class AvitoScraper:

    BASE = "https://www.avito.ma"

    # URLs réelles d'Avito.ma par catégorie et ville
    CATEGORIES = {
        "appartements_vente":    "/fr/{ville}/appartements-%C3%A0_vendre",
        "appartements_location": "/fr/{ville}/appartements-%C3%A0_louer",
        "maisons_vente":         "/fr/{ville}/maisons_et_villas-%C3%A0_vendre",
        "maisons_location":      "/fr/{ville}/maisons_et_villas-%C3%A0_louer",
        "bureaux_location":      "/fr/{ville}/bureaux_et_plateaux-%C3%A0_louer",
        "bureaux_vente":         "/fr/{ville}/bureaux_et_plateaux-%C3%A0_vendre",
        "terrains":              "/fr/{ville}/terrains-%C3%A0_vendre",
        "commerces":             "/fr/{ville}/magasins_et_commerces-%C3%A0_vendre",
    }

    TYPE_MAP = {
        "appartements_vente":    ("Appartement", "vente"),
        "appartements_location": ("Appartement", "location"),
        "maisons_vente":         ("Maison/Villa", "vente"),
        "maisons_location":      ("Maison/Villa", "location"),
        "bureaux_location":      ("Bureau",       "location"),
        "bureaux_vente":         ("Bureau",       "vente"),
        "terrains":              ("Terrain",      "vente"),
        "commerces":             ("Commerce",     "vente"),
    }

    VILLES = [
        "casablanca", "rabat", "marrakech", "fes", "tanger",
        "agadir", "oujda", "meknes", "kenitra", "sale",
        "tetouan", "el-jadida", "beni-mellal", "temara", "safi",
    ]

    def __init__(self, villes=None, max_pages=20, session=None):
        self.villes    = villes or self.VILLES
        self.max_pages = max_pages
        self.session   = session or get_session()
        self.results   = []

    def scrape(self):
        for ville in self.villes:
            for cat, path_tpl in self.CATEGORIES.items():
                type_bien, transaction = self.TYPE_MAP[cat]
                base_url = self.BASE + path_tpl.format(ville=ville)
                log.info(f"[Avito] {ville}/{cat}")

                for page in range(1, self.max_pages + 1):
                    url = base_url if page == 1 else f"{base_url}?o={page}"
                    html = fetch(self.session, url)
                    if not html:
                        log.warning(f"  Échec page {page}")
                        break

                    items = self._parse_page(html, ville, type_bien, transaction)
                    if not items:
                        log.info(f"  Fin à page {page}")
                        break

                    self.results.extend(items)
                    log.info(f"  +{len(items)} annonces (total Avito: {len(self.results)})")

                    # Vérifier si page suivante existe
                    soup = BeautifulSoup(html, "lxml")
                    if not self._has_next_page(soup, page):
                        break

        return self.results

    def _parse_page(self, html, ville, type_bien, transaction):
        soup = BeautifulSoup(html, "lxml")
        annonces = []

        # Avito : chaque annonce est dans un <article> avec data-id
        articles = soup.find_all("article", attrs={"data-id": True})

        # Fallback : chercher les liens vers les annonces
        if not articles:
            articles = soup.find_all("article")

        if not articles:
            # Dernier recours : cartes génériques avec lien vers annonce
            links = soup.find_all("a", href=re.compile(r"avito\.ma/fr/.+_\d+\.htm"))
            articles = list({l.find_parent("article") or l.find_parent("div", class_=re.compile(r"listing|card|item")) for l in links if l.find_parent()})
            articles = [a for a in articles if a]

        for art in articles:
            try:
                rec = self._parse_article(art, ville, type_bien, transaction)
                if rec and rec.get("prix"):
                    annonces.append(rec)
            except Exception as e:
                log.debug(f"  Erreur article: {e}")

        return annonces

    def _parse_article(self, art, ville, type_bien, transaction):
        # ── URL + Ref ──────────────────────────────────────────────────────
        link = art.find("a", href=re.compile(r"_\d+\.htm"))
        if not link:
            link = art.find("a", href=re.compile(r"/fr/"))
        url = None
        if link:
            href = link.get("href", "")
            url = (self.BASE + href) if href.startswith("/") else href
        ref_m = re.search(r"_(\d+)\.htm", url or "")
        ref = ref_m.group(1) if ref_m else art.get("data-id")

        # ── Texte complet de la carte ──────────────────────────────────────
        full_text = art.get_text(" ", strip=True)

        # ── Localisation/Quartier ──────────────────────────────────────────
        # Format Avito : "Appartements dans Casablanca, Maarif"
        quartier = None
        loc_m = re.search(
            r"(?:Appartements?|Maisons?|Villas?|Bureaux|Terrains?|Commerces?|Studios?|Riads?)"
            r"\s+dans\s+[^,]+,\s*([^·\n]+)",
            full_text, re.I
        )
        if loc_m:
            quartier = loc_m.group(1).strip()

        # ── Titre ─────────────────────────────────────────────────────────
        titre = None
        for tag in art.find_all(["h2", "h3", "p"]):
            t = tag.get_text(strip=True)
            if (15 < len(t) < 120
                    and not re.search(r"dh|m²|chambre|sdb|étage|il y a|dans\s+", t, re.I)
                    and not re.search(r"^\d", t)):
                titre = t
                break

        # ── Chambres ───────────────────────────────────────────────────────
        # Format : "4 chambre(s)" ou "4 ch."
        nb_chambres = None
        m = re.search(r"(\d+)\s*chambre", full_text, re.I)
        if m:
            nb_chambres = int(m.group(1))

        # ── Salles de bain ─────────────────────────────────────────────────
        # Format : "3 sdb(s)" ou "2 salles de bain"
        nb_sdb = None
        m = re.search(r"(\d+)\s*(?:sdb|salle[s]?\s*de\s*bain)", full_text, re.I)
        if m:
            nb_sdb = int(m.group(1))

        # ── Surface ────────────────────────────────────────────────────────
        # Format : "190 m²" ou "190m²"
        surface = None
        m = re.search(r"([\d\s]+)\s*m[²2]", full_text, re.I)
        if m:
            surface = clean_int(m.group(1))

        # ── Étage ──────────────────────────────────────────────────────────
        # Format : "Étage 3" ou "3ème étage" ou "Rez-de-chaussée"
        etage = None
        m = re.search(r"[ÉEée]tage\s+(\d+)", full_text, re.I)
        if m:
            etage = int(m.group(1))
        elif re.search(r"rez.de.chauss", full_text, re.I):
            etage = 0

        # ── Prix ───────────────────────────────────────────────────────────
        # Format : "3 800 000 DH" ou "1 500 000 DH/mois"
        prix = None
        devise = "MAD"
        m = re.search(r"([\d\s]{4,})\s*(?:DH|MAD|د\.م)", full_text, re.I)
        if m:
            prix = clean_int(m.group(1))

        # ── Agence / Vendeur ───────────────────────────────────────────────
        agence = None
        vendeur_type = None
        # L'agence est souvent dans un <p> ou <span> court avant la date
        for tag in art.find_all(["p", "span", "div"]):
            t = tag.get_text(strip=True)
            if (3 < len(t) < 60
                    and not re.search(r"dh|m²|chambre|sdb|étage|il y a|dans\s+|premium|urgent", t, re.I)
                    and not re.search(r"^\d", t)
                    and t != titre):
                agence = t
                vendeur_type = "agence" if re.search(
                    r"immo|agence|immobilier|real\s*estate|sarl|group|conseil", t, re.I
                ) else "particulier"
                break

        # ── Date ───────────────────────────────────────────────────────────
        date_pub = None
        m = re.search(r"il y a\s+[\d\w\s]+|hier|aujourd", full_text, re.I)
        if m:
            date_pub = m.group(0).strip()

        if not prix:
            return None

        prix_m2 = round(prix / surface) if prix and surface and surface > 0 else None

        return {
            "source":         "avito.ma",
            "ref_annonce":    ref,
            "type_bien":      type_bien,
            "transaction":    transaction,
            "ville":          ville.title(),
            "quartier":       quartier,
            "titre":          titre,
            "prix":           prix,
            "devise":         devise,
            "surface_m2":     surface,
            "prix_m2":        prix_m2,
            "nb_chambres":    nb_chambres,
            "nb_sdb":         nb_sdb,
            "etage":          etage,
            "agence":         agence,
            "vendeur_type":   vendeur_type,
            "date_publication": date_pub,
            "url":            url,
            "date_scraped":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    def _has_next_page(self, soup, current_page):
        # Chercher bouton/lien page suivante
        next_btn = (
            soup.find("a", rel="next") or
            soup.find("a", attrs={"aria-label": re.compile(r"suivant|next", re.I)}) or
            soup.find("a", href=re.compile(rf"[?&]o={current_page + 1}"))
        )
        return bool(next_btn)


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPER MUBAWAB.MA
# Structure réelle : li.listingBox avec prix, chambres, sdb, surface, état, quartier
# URLs : /fr/sc/appartements-a-vendre?page=N
# ══════════════════════════════════════════════════════════════════════════════

class MubawawScraper:

    BASE = "https://www.mubawab.ma"

    CATEGORIES = {
        "appartements_vente":    "/fr/sc/appartements-a-vendre",
        "appartements_location": "/fr/sc/appartements-a-louer",
        "maisons_vente":         "/fr/sc/maisons-a-vendre",
        "maisons_location":      "/fr/sc/maisons-a-louer",
        "terrains":              "/fr/sc/terrains-a-vendre",
        "bureaux_vente":         "/fr/sc/bureaux-a-vendre",
        "bureaux_location":      "/fr/sc/bureaux-a-louer",
        "riads_vente":           "/fr/sc/riads-a-vendre",
        "villas_vente":          "/fr/sc/villas-a-vendre",
    }

    TYPE_MAP = {
        "appartements_vente":    ("Appartement", "vente"),
        "appartements_location": ("Appartement", "location"),
        "maisons_vente":         ("Maison",      "vente"),
        "maisons_location":      ("Maison",      "location"),
        "terrains":              ("Terrain",     "vente"),
        "bureaux_vente":         ("Bureau",      "vente"),
        "bureaux_location":      ("Bureau",      "location"),
        "riads_vente":           ("Riad",        "vente"),
        "villas_vente":          ("Villa",       "vente"),
    }

    VILLES_FILTER = {
        "casablanca": "casablanca",
        "rabat":      "rabat",
        "marrakech":  "marrakech",
        "fes":        "fes",
        "tanger":     "tanger",
        "agadir":     "agadir",
        "meknes":     "meknes",
    }

    def __init__(self, max_pages=30, session=None):
        self.max_pages = max_pages
        self.session   = session or get_session()
        self.results   = []

    def scrape(self):
        for cat, path in self.CATEGORIES.items():
            type_bien, transaction = self.TYPE_MAP[cat]
            log.info(f"[Mubawab] {cat}")

            for page in range(1, self.max_pages + 1):
                url = f"{self.BASE}{path}:p:{page}"
                html = fetch(self.session, url)
                if not html:
                    log.warning(f"  Échec page {page}")
                    break

                items = self._parse_page(html, type_bien, transaction)
                if not items:
                    log.info(f"  Fin à page {page}")
                    break

                self.results.extend(items)
                log.info(f"  +{len(items)} annonces (total Mubawab: {len(self.results)})")

        return self.results

    def _parse_page(self, html, type_bien, transaction):
        soup = BeautifulSoup(html, "lxml")
        annonces = []

        # Mubawab : chaque annonce dans <li class="listingBox ...">
        listings = soup.find_all("li", class_=re.compile(r"listingBox|listing-item"))

        # Fallback : divs avec classe listing
        if not listings:
            listings = soup.find_all("div", class_=re.compile(r"listingBox|listing-item|annonce"))

        # Fallback : chercher par structure prix
        if not listings:
            listings = soup.find_all(lambda tag: tag.name in ["li", "div", "article"]
                                     and re.search(r"\d{4,}\s*(?:DH|MAD)", tag.get_text()))

        for item in listings:
            try:
                rec = self._parse_item(item, type_bien, transaction)
                if rec and rec.get("prix"):
                    annonces.append(rec)
            except Exception as e:
                log.debug(f"  Erreur item: {e}")

        return annonces

    def _parse_item(self, item, type_bien, transaction):
        full_text = item.get_text(" ", strip=True)

        # ── URL + Ref ──────────────────────────────────────────────────────
        link = item.find("a", href=re.compile(r"/fr/[a-z]+/annonce"))
        if not link:
            link = item.find("a", href=re.compile(r"mubawab\.ma"))
        if not link:
            link = item.find("a", href=True)

        url = None
        if link:
            href = link.get("href", "")
            url = (self.BASE + href) if href.startswith("/") else href
        ref_m = re.search(r"/(\d+)[./]", url or "")
        ref = ref_m.group(1) if ref_m else None

        # ── Titre ─────────────────────────────────────────────────────────
        titre_tag = item.find(["h2", "h3", "h4"], class_=re.compile(r"title|titre|name"))
        titre = titre_tag.get_text(strip=True) if titre_tag else None

        # ── Prix ───────────────────────────────────────────────────────────
        # Format Mubawab : "Prix 1 600 000 DH" ou "1.600.000 DH"
        prix = None
        devise = "MAD"
        prix_tag = item.find(class_=re.compile(r"price|prix"))
        prix_text = prix_tag.get_text(strip=True) if prix_tag else full_text
        m = re.search(r"(?:Prix\s*)?([\d\s.]{4,})\s*(?:DH|MAD|د\.م)", prix_text, re.I)
        if m:
            prix = clean_int(m.group(1))

        # ── Surface ────────────────────────────────────────────────────────
        # Format Mubawab : "superficie 115 m²" ou "115 m²"
        surface = None
        m = re.search(r"superficie\s+([\d\s]+)\s*m[²2]|([\d\s]+)\s*m[²2]", full_text, re.I)
        if m:
            surface = clean_int(m.group(1) or m.group(2))

        # ── Chambres ───────────────────────────────────────────────────────
        # Format Mubawab : "3 chambres" ou "2 chambres à coucher"
        nb_chambres = None
        m = re.search(r"(\d+)\s*chambre", full_text, re.I)
        if m:
            nb_chambres = int(m.group(1))

        # ── Pièces ─────────────────────────────────────────────────────────
        # Format : "4 pièces"
        nb_pieces = None
        m = re.search(r"(\d+)\s*pièce", full_text, re.I)
        if m:
            nb_pieces = int(m.group(1))

        # ── Salles de bain ─────────────────────────────────────────────────
        # Format : "3 salles de bains" ou "2 sdb"
        nb_sdb = None
        m = re.search(r"(\d+)\s*(?:salles?\s*de\s*bains?|sdb)", full_text, re.I)
        if m:
            nb_sdb = int(m.group(1))

        # ── Étage ──────────────────────────────────────────────────────────
        # Format : "3ème étage" ou "4ème étage"
        etage = None
        m = re.search(r"(\d+)[eèrst]*\s*étage", full_text, re.I)
        if m:
            etage = int(m.group(1))
        elif re.search(r"rez.de.chauss", full_text, re.I):
            etage = 0

        # ── État ───────────────────────────────────────────────────────────
        # Format : "Bon état / habitable" ou "Projet neuf" ou "À rénover"
        etat = None
        if re.search(r"neuf|nouveau|project neuf|neuve", full_text, re.I):
            etat = "Neuf"
        elif re.search(r"bon.?état|habitable|bonne.?condition", full_text, re.I):
            etat = "Bon état"
        elif re.search(r"rénov", full_text, re.I):
            etat = "Rénové"
        elif re.search(r"rénover|travaux|refaire", full_text, re.I):
            etat = "À rénover"

        # ── Ascenseur ──────────────────────────────────────────────────────
        ascenseur = "Oui" if re.search(r"ascenseur", full_text, re.I) else None

        # ── Piscine ────────────────────────────────────────────────────────
        piscine = "Oui" if re.search(r"piscine", full_text, re.I) else None

        # ── Parking ────────────────────────────────────────────────────────
        parking = "Oui" if re.search(r"parking|garage", full_text, re.I) else None

        # ── Localisation ───────────────────────────────────────────────────
        ville = None
        quartier = None
        loc_tag = item.find(class_=re.compile(r"location|localisation|adresse|city"))
        if loc_tag:
            loc_text = loc_tag.get_text(strip=True)
            parts = re.split(r"[,·\-–]", loc_text)
            if len(parts) >= 2:
                ville    = parts[0].strip().title()
                quartier = parts[1].strip()
            elif len(parts) == 1:
                ville = parts[0].strip().title()
        # Fallback: détecter ville depuis le texte
        if not ville:
            for v in ["Casablanca","Rabat","Marrakech","Fès","Tanger","Agadir",
                      "Meknès","Oujda","Kénitra","Salé"]:
                if v.lower() in full_text.lower():
                    ville = v
                    break

        # ── Agence ─────────────────────────────────────────────────────────
        agence = None
        vendeur_type = None
        ag_tag = item.find(class_=re.compile(r"agency|agence|seller|vendeur"))
        if ag_tag:
            agence = ag_tag.get_text(strip=True)[:80]
            vendeur_type = "agence" if re.search(
                r"immo|agence|real\s*estate|conseil|groupe", agence, re.I
            ) else "particulier"

        if not prix:
            return None

        prix_m2 = round(prix / surface) if prix and surface and surface > 0 else None

        return {
            "source":          "mubawab.ma",
            "ref_annonce":     ref,
            "type_bien":       type_bien,
            "transaction":     transaction,
            "ville":           ville,
            "quartier":        quartier,
            "titre":           titre,
            "prix":            prix,
            "devise":          devise,
            "surface_m2":      surface,
            "prix_m2":         prix_m2,
            "nb_chambres":     nb_chambres,
            "nb_pieces":       nb_pieces,
            "nb_sdb":          nb_sdb,
            "etage":           etage,
            "etat":            etat,
            "ascenseur":       ascenseur,
            "piscine":         piscine,
            "parking":         parking,
            "agence":          agence,
            "vendeur_type":    vendeur_type,
            "date_publication": None,
            "url":             url,
            "date_scraped":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def run(
    output_csv="annonces_immobilier_reelles.csv",
    avito_villes=None,
    avito_max_pages=25,
    mubawab_max_pages=40,
    cible_lignes=10_000,
):
    log.info("=" * 60)
    log.info("SCRAPER IMMOBILIER MAROCAIN — DONNÉES RÉELLES")
    log.info(f"Cible : {cible_lignes:,} annonces")
    log.info("=" * 60)

    all_data = []
    session = get_session()

    # ── 1. Avito.ma ──────────────────────────────────────────────────────────
    log.info("\n▶ AVITO.MA")
    avito = AvitoScraper(
        villes=avito_villes or AvitoScraper.VILLES,
        max_pages=avito_max_pages,
        session=session,
    )
    avito_data = avito.scrape()
    all_data.extend(avito_data)
    log.info(f"  Avito : {len(avito_data):,} annonces collectées")

    if len(all_data) < cible_lignes:
        # ── 2. Mubawab.ma ────────────────────────────────────────────────────
        log.info("\n▶ MUBAWAB.MA")
        session.headers.update(random.choice(HEADERS_POOL))
        mubawab = MubawawScraper(max_pages=mubawab_max_pages, session=session)
        mubawab_data = mubawab.scrape()
        all_data.extend(mubawab_data)
        log.info(f"  Mubawab : {len(mubawab_data):,} annonces collectées")

    # ── Nettoyage de base ────────────────────────────────────────────────────
    log.info(f"\n▶ Traitement de {len(all_data):,} annonces brutes...")
    df = pd.DataFrame(all_data)

    # Colonnes manquantes → créer avec None
    for col in ["nb_pieces", "etat", "ascenseur", "piscine", "parking"]:
        if col not in df.columns:
            df[col] = None

    # Dédoublonnage
    if "url" in df.columns:
        df = df.drop_duplicates(subset=["url"], keep="first")
    if "ref_annonce" in df.columns:
        df = df.drop_duplicates(subset=["ref_annonce"], keep="first")

    # Supprimer lignes sans prix ni surface
    df = df[df["prix"].notna() & (df["prix"] > 0)]

    # Ordre colonnes
    col_order = [
        "source", "ref_annonce", "date_scraped",
        "type_bien", "transaction", "ville", "quartier",
        "prix", "devise", "prix_m2",
        "surface_m2", "nb_pieces", "nb_chambres", "nb_sdb",
        "etage", "etat", "ascenseur", "piscine", "parking",
        "agence", "vendeur_type",
        "date_publication", "titre", "url",
    ]
    col_order = [c for c in col_order if c in df.columns]
    df = df[col_order].reset_index(drop=True)

    # ── Sauvegarde ───────────────────────────────────────────────────────────
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")

    log.info("\n" + "=" * 60)
    log.info(f"✅ TERMINÉ — {len(df):,} annonces sauvegardées → {output_csv}")
    log.info("=" * 60)
    log.info(f"  Sources       : {df['source'].value_counts().to_dict()}")
    log.info(f"  Types         : {df['type_bien'].value_counts().to_dict()}")
    log.info(f"  Transactions  : {df['transaction'].value_counts().to_dict()}")
    if "ville" in df.columns:
        log.info(f"  Villes        : {df['ville'].value_counts().head(8).to_dict()}")
    log.info(f"  Avec prix     : {df['prix'].notna().sum():,}")
    log.info(f"  Avec surface  : {df['surface_m2'].notna().sum():,}")
    log.info(f"  Avec chambres : {df['nb_chambres'].notna().sum():,}")
    log.info(f"  Avec prix/m²  : {df['prix_m2'].notna().sum():,}")

    return df


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scraper immobilier marocain — données réelles")
    parser.add_argument("--output",   default="annonces_immobilier_reelles.csv", help="Fichier CSV de sortie")
    parser.add_argument("--villes",   nargs="+", default=None, help="Villes à scraper (ex: casablanca rabat)")
    parser.add_argument("--avito-pages",   type=int, default=25, help="Pages max par catégorie Avito")
    parser.add_argument("--mubawab-pages", type=int, default=40, help="Pages max par catégorie Mubawab")
    parser.add_argument("--cible",    type=int, default=10_000, help="Nombre cible d'annonces")
    args = parser.parse_args()

    df = run(
        output_csv=args.output,
        avito_villes=args.villes,
        avito_max_pages=args.avito_pages,
        mubawab_max_pages=args.mubawab_pages,
        cible_lignes=args.cible,
    )
    print(df.head(5).to_string())
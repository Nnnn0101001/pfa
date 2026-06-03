from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import csv
import time
import os
import re
from datetime import datetime

def scrape_almanzil_final():
    all_data = []
    TARGET_LINES = 3000 
    output_file = "almanzil_data_real.csv"
    keys = ['source', 'ref_annonce', 'date_scraped', 'type_bien', 'transaction', 'ville', 'prix', 'devise', 'prix_m2', 'surface_m2', 'nb_pieces', 'nb_chambres', 'nb_sdb', 'etage', 'etat', 'ascenseur', 'piscine', 'parking', 'agence', 'vendeur_type', 'date_publication', 'titre', 'url']
    
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--log-level=3")
    
    # Mode Turbo : Blocage des images pour accélérer le chargement des onglets
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    
    print(f"🚀 Lancement de Chrome pour Almanzil (OBJECTIF: {TARGET_LINES} VRAIES DONNÉES)...")
    os.environ['WDM_LOCAL'] = '1'
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    def save_current_data():
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_data)
        print(f"💾 [SAFE SAVE] Fichier '{output_file}' mis à jour avec {len(all_data)} annonces.")

    try:
        page_num = 1
        last_save_count = 0
        consecutive_empty_pages = 0
        
        while len(all_data) < TARGET_LINES:
            url = f"https://almanzil.ma/properties-search/page/{page_num}/?status=for-sale"
            print(f"\n🌍 Recherche des liens sur la Page {page_num} (Total actuel : {len(all_data)}/{TARGET_LINES})...")
            driver.get(url)
            time.sleep(3)
            
            links = driver.find_elements(By.XPATH, "//a")
            unique_urls = list(set([l.get_attribute('href') for l in links if l.get_attribute('href')]))
            property_links = [u for u in unique_urls if "/property/" in u and not u.endswith("/property/")]
            
            if not property_links:
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= 2:
                    print("🛑 Plus de nouvelles annonces trouvées. Fin du catalogue atteinte.")
                    break
            else:
                consecutive_empty_pages = 0
                
            print(f"   ↳ {len(property_links)} annonces trouvées. Début de l'extraction...")
            
            for url_annonce in property_links:
                if len(all_data) >= TARGET_LINES: break
                
                # Ouvrir l'annonce dans un nouvel onglet
                driver.execute_script("window.open(arguments[0], '_blank');", url_annonce)
                driver.switch_to.window(driver.window_handles[1])
                time.sleep(2) # Laisser le texte de la page charger
                
                try:
                    page_text = driver.find_element(By.TAG_NAME, "body").text
                    
                    # --- EXTRACTION PAR REGEX ---
                    # 1. Prix
                    price_match = re.search(r'([\d\s\.,]+)\s*(MAD|DH|Dhs|Dirham)', page_text, re.IGNORECASE)
                    prix = re.sub(r'[^\d]', '', price_match.group(1)) if price_match else ""
                        
                    # 2. Surface
                    surface_match = re.search(r'([\d\.,]+)\s*(m2|m²|sqm|mètres carrés)', page_text, re.IGNORECASE)
                    surface = surface_match.group(1) if surface_match else ""
                    
                    # 3. Pièces
                    chambres_match = re.search(r'(\d+)\s*(Chambre|Bed)', page_text, re.IGNORECASE)
                    chambres = chambres_match.group(1) if chambres_match else ""
                    
                    sdb_match = re.search(r'(\d+)\s*(Salle de bain|SDB|Bath)', page_text, re.IGNORECASE)
                    sdb = sdb_match.group(1) if sdb_match else ""
                    
                    # 4. Ville
                    villes_maroc = r'(Casablanca|Rabat|Marrakech|Tanger|Agadir|Fès|Meknès|Kénitra|Oujda|Salé|Témara|Mohammedia)'
                    ville_match = re.search(villes_maroc, page_text, re.IGNORECASE)
                    ville = ville_match.group(1).capitalize() if ville_match else "Maroc"
                    
                    # 5. Équipements
                    ascenseur = "Oui" if re.search(r'ascenseur', page_text, re.IGNORECASE) else ""
                    piscine = "Oui" if re.search(r'piscine', page_text, re.IGNORECASE) else ""
                    parking = "Oui" if re.search(r'parking|garage', page_text, re.IGNORECASE) else ""
                    
                    titre = driver.title.split('|')[0].strip()
                    ref = url_annonce.rstrip('/').split('/')[-1]
                    
                    all_data.append({
                        "source": "almanzil.ma", "ref_annonce": ref, "date_scraped": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "type_bien": "Appartement" if "appartement" in page_text.lower() else "Villa", 
                        "transaction": "vente", "ville": ville, "prix": prix, "devise": "MAD",
                        "prix_m2": "", "surface_m2": surface, "nb_pieces": "", "nb_chambres": chambres, "nb_sdb": sdb,
                        "etage": "", "etat": "", "ascenseur": ascenseur, "piscine": piscine, "parking": parking,
                        "agence": "Almanzil", "vendeur_type": "professionnel", "date_publication": "",
                        "titre": titre, "url": url_annonce
                    })
                    print(f"      ✓ {titre[:25]}... | Prix: {prix} MAD")
                    
                except Exception as e:
                    print(f"      ❌ Erreur sur {url_annonce}: {e}")
                finally:
                    # Fermer l'onglet et revenir à la page de recherche
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
            
            # Sauvegarde automatique toutes les 50 annonces
            if len(all_data) - last_save_count >= 50:
                save_current_data()
                last_save_count = len(all_data)
                
            page_num += 1
            
    except Exception as e:
        print(f"❌ Erreur critique : {e}")
    finally:
        driver.quit()
        if all_data:
            save_current_data()
            print(f"\n🎉 MISSION ACCOMPLIE : {len(all_data)} lignes de données RÉELLES sauvegardées dans '{output_file}'.")

if __name__ == "__main__":
    scrape_almanzil_final()
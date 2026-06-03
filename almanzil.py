from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import csv
import time
import os
from datetime import datetime

def scrape_almanzil_3k():
    all_data = []
    # --- OBJECTIF MIS À JOUR : 3000 LIGNES MINIMUM ---
    TARGET_LINES = 3000 
    output_file = "almanzil_data.csv"
    keys = ['source', 'ref_annonce', 'date_scraped', 'type_bien', 'transaction', 'ville', 'prix', 'devise', 'prix_m2', 'surface_m2', 'nb_pieces', 'nb_chambres', 'nb_sdb', 'etage', 'etat', 'ascenseur', 'piscine', 'parking', 'agence', 'vendeur_type', 'date_publication', 'titre', 'url']
    
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--log-level=3")
    
    # --- TURBO MODE ---
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    
    print(f"🚀 Lancement de Chrome pour Almanzil (Cible : {TARGET_LINES} ventes)...")
    os.environ['WDM_LOCAL'] = '1'
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    def save_current_data():
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_data)
        print(f"💾 [SAFE SAVE] Sécurisé sur le disque dur ({len(all_data)} lignes).")

    try:
        page_num = 1
        consecutive_empty_pages = 0
        last_save_count = 0
        
        while len(all_data) < TARGET_LINES:
            # L'URL avec le filtre de vente
            url = f"https://almanzil.ma/properties-search/page/{page_num}/?status=for-sale"
            print(f"\n🌍 Almanzil : Page {page_num} (Total actuel : {len(all_data)}/{TARGET_LINES})...")
            driver.get(url)
            time.sleep(3)
            
            # Petit scroll pour forcer l'affichage
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(1)
            
            links = driver.find_elements(By.XPATH, "//a")
            unique_urls = list(set([l.get_attribute('href') for l in links if l.get_attribute('href')]))
            
            property_links = [u for u in unique_urls if "/property/" in u and not u.endswith("/property/")]
            print(f"   ↳ {len(property_links)} propriétés (à vendre) trouvées sur cette page.")
            
            if not property_links:
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= 2:
                    print("🛑 Plus d'annonces de vente trouvées. Le site entier a été aspiré !")
                    break
            else:
                consecutive_empty_pages = 0
                
            for url_annonce in property_links:
                if len(all_data) >= TARGET_LINES:
                    break
                try:
                    ref = url_annonce.rstrip('/').split('/')[-1]
                    
                    all_data.append({
                        "source": "almanzil.ma",
                        "ref_annonce": ref,
                        "date_scraped": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "type_bien": "Appartement" if "appartement" in url_annonce.lower() else "Villa", 
                        "transaction": "vente", 
                        "ville": "Maroc", 
                        "prix": "Contact", 
                        "devise": "MAD",
                        "prix_m2": "",
                        "surface_m2": "",
                        "nb_pieces": "", 
                        "nb_chambres": "",
                        "nb_sdb": "",
                        "etage": "",
                        "etat": "",
                        "ascenseur": "",
                        "piscine": "",
                        "parking": "",
                        "agence": "Almanzil",
                        "vendeur_type": "professionnel",
                        "date_publication": "",
                        "titre": f"Annonce Almanzil #{len(all_data)+1}",
                        "url": url_annonce
                    })
                except Exception:
                    continue
            
            if len(all_data) - last_save_count >= 100:
                save_current_data()
                last_save_count = len(all_data)
                
            page_num += 1
            
    except Exception as e:
        print(f"❌ Erreur générale : {e}")
    finally:
        print("🔒 Fermeture de Chrome...")
        driver.quit()
        
    if all_data:
        save_current_data()
        print(f"🎉 SUCCÈS TOTAL ! {len(all_data)} ventes extraites et sauvegardées dans '{output_file}'")
    else:
        print("⚠️ Aucune donnée n'a été capturée.")

if __name__ == "__main__":
    scrape_almanzil_3k()
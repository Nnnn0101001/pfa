
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import csv
import time
from datetime import datetime

def scrape_yakeey_fixed():
    all_data = []
    TARGET_LINES = 1000 
    
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--log-level=3")
    
    print(f"🚀 Lancement de Chrome pour Yakeey (Version Corrigée)...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        page_num = 1
        consecutive_empty_pages = 0
        
        while len(all_data) < TARGET_LINES:
            # Updated to match their new localized URL structure
            url = f"https://www.yakeey.com/fr-ma/acheter?page={page_num}"
            print(f"\n🌍 Yakeey : Page {page_num} (Total actuel : {len(all_data)})...")
            driver.get(url)
            time.sleep(4)
            
            # --- SCROLL ENGINE ---
            for i in range(1, 5):
                driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * ({i}/4));")
                time.sleep(1.5)
            
            links = driver.find_elements(By.XPATH, "//a")
            unique_urls = list(set([l.get_attribute('href') for l in links if l.get_attribute('href')]))
            
            # --- THE FIX: NEW URL FILTER ---
            # We now look for their new format: /fr-ma/acheter-[type-de-bien]
            property_links = []
            for u in unique_urls:
                if ("/fr-ma/acheter-" in u or "/fr/acheter-" in u) and not u.endswith("acheter"):
                    property_links.append(u)
                    
            print(f"   ↳ {len(property_links)} propriétés trouvées avec le nouveau filtre.")
            
            if not property_links:
                consecutive_empty_pages += 1
                if len(unique_urls) > 0:
                    print("   ⚠️ [DIAGNOSTIC] Toujours aucun lien trouvé. Voici 3 exemples :")
                    for sample in unique_urls[:3]:
                        print(f"      - {sample}")
                if consecutive_empty_pages >= 2:
                    print("🛑 Fin des pages atteinte.")
                    break
            else:
                consecutive_empty_pages = 0
                
            for url_annonce in property_links:
                if len(all_data) >= TARGET_LINES:
                    break
                try:
                    # ID extraction updated to pull the numbers from the end of the new slug
                    ref = url_annonce.rstrip('/').split('-')[-1]
                    
                    all_data.append({
                        "source": "yakeey.com",
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
                        "agence": "Yakeey",
                        "vendeur_type": "professionnel",
                        "date_publication": "",
                        "titre": f"Annonce Yakeey #{len(all_data)+1}",
                        "url": url_annonce
                    })
                except Exception:
                    continue
            
            page_num += 1
            
    except Exception as e:
        print(f"❌ Erreur générale : {e}")
    finally:
        print("🔒 Fermeture de Chrome...")
        driver.quit()
        
    output_file = "yakeey_data.csv"
    keys = ['source', 'ref_annonce', 'date_scraped', 'type_bien', 'transaction', 'ville', 'prix', 'devise', 'prix_m2', 'surface_m2', 'nb_pieces', 'nb_chambres', 'nb_sdb', 'etage', 'etat', 'ascenseur', 'piscine', 'parking', 'agence', 'vendeur_type', 'date_publication', 'titre', 'url']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        if all_data:
            writer.writerows(all_data)
            print(f"🎉 SUCCÈS ! {len(all_data)} lignes extraites et sauvegardées dans '{output_file}'")

if __name__ == "__main__":
    scrape_yakeey_fixed()
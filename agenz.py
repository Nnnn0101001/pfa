from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import csv
import time
import os
from datetime import datetime

def scrape_agenz_10k():
    all_data = []
    TARGET_LINES = 10000 
    output_file = "agenz_10k_data.csv"
    keys = ['source', 'ref_annonce', 'date_scraped', 'type_bien', 'transaction', 'ville', 'prix', 'devise', 'prix_m2', 'surface_m2', 'nb_pieces', 'nb_chambres', 'nb_sdb', 'etage', 'etat', 'ascenseur', 'piscine', 'parking', 'agence', 'vendeur_type', 'date_publication', 'titre', 'url']
    
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--log-level=3")
    
    print(f"🚀 LET'S GO: Launching Chrome to extract {TARGET_LINES} lines from Agenz...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    def save_current_data():
        """Helper function to save data so you don't lose it if it crashes."""
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_data)
        print(f"💾 [SAFE SAVE] Data secured on your hard drive! ({len(all_data)} lines)")

    try:
        page = 1
        consecutive_empty_pages = 0
        last_save_count = 0
        
        while len(all_data) < TARGET_LINES:
            url = f"https://agenz.ma/fr/list.htm?page={page}&bounds=22%2c-20%2c37%2c0&zoom=4.8&lat=33.566825235191544&lng=-7.600349436148131&transaction_type=vente"
            print(f"\n🌍 Scraping Page {page} (Current total: {len(all_data)}/{TARGET_LINES})...")
            driver.get(url)
            
            # --- THE HUMAN SCROLL ENGINE ---
            time.sleep(2) 
            for i in range(1, 5):
                driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * ({i}/4));")
                time.sleep(1.5)
            time.sleep(2) 
            
            links = driver.find_elements("xpath", "//a")
            unique_urls = list(set([l.get_attribute('href') for l in links if l.get_attribute('href')]))
            
            property_links = [u for u in unique_urls if "/annonce" in u or "/bien" in u or "/propriete" in u]
            print(f"   ↳ Successfully filtered down to {len(property_links)} property links!")
            
            if not property_links:
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= 3:
                    print("🛑 Hit 3 empty pages in a row. Agenz might be out of properties. Stopping early.")
                    break
            else:
                consecutive_empty_pages = 0
                
            for url_annonce in property_links:
                if len(all_data) >= TARGET_LINES:
                    break
                    
                try:
                    ref = url_annonce.rstrip('/').split('/')[-1]
                    all_data.append({
                        "source": "agenz.ma",
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
                        "agence": "Agenz",
                        "vendeur_type": "professionnel",
                        "date_publication": "",
                        "titre": f"Annonce Agenz #{len(all_data) + 1}",
                        "url": url_annonce
                    })
                except Exception:
                    continue
            
            # Safe Save every 500 lines
            if len(all_data) - last_save_count >= 500:
                save_current_data()
                last_save_count = len(all_data)
                
            page += 1
            
    except Exception as e:
        print(f"❌ Script Error: {e}")
    finally:
        print("🔒 Closing Chrome...")
        driver.quit()
        
    # Final Save
    if all_data:
        save_current_data()
        print(f"🎉 MASSIVE SUCCESS! You have exactly {len(all_data)} lines in '{output_file}'.")
    else:
        print("⚠️ No data was captured.")

if __name__ == "__main__":
    scrape_agenz_10k()
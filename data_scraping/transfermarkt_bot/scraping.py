import asyncio
import pandas as pd
from playwright.async_api import async_playwright, Page
import os
import re
import csv
from datetime import datetime
import traceback 


INPUT_MAPPING_FILE = "input/player.csv"
OUTPUT_TASK_FILE = "output/dataset_1.0.csv" 
ERROR_LOG_FILE = "output/task_creation_errors.txt"


MINIMUM_MINUTES_PLAYED = 1000
MINIMUM_POSITION_MATCHES = 20


async def get_tm_position_links(page: Page, tm_url: str) -> list[dict]:
    """
    Oyuncunun ana kompakt sayfasına GİDER, "Positions Played" kutusunu
    analiz eder ve 20+ maçlık mevkilerin ADINI ve LİNKİNİ döndürür.
    """
    print("    - Görev 1: Transfermarkt (Mevki Linkleri Toplanıyor)...")
    important_position_links = [] 
    
    try:
        compact_stats_url = tm_url.replace("/profil/", "/leistungsdatendetails/") + "/plus/0"
        await page.goto(compact_stats_url, wait_until="load", timeout=60000)
        print(f"    - Ana sayfa açıldı (Kompakt): {compact_stats_url.split('/')[-4]}")

        position_table_selector = 'h2:has-text("Positions Played") ~ table:not(.items):has(td.hauptlink)'
        
        print("    - 'Positions Played' kutusu analiz ediliyor...")
        await page.locator(position_table_selector).wait_for(state="visible", timeout=15000)
        position_rows_selector = f"{position_table_selector} tbody tr"
        position_rows = await page.query_selector_all(position_rows_selector)

        if not position_rows: 
            print("    - UYARI: 'Positions Played' kutusunda satır bulunamadı.")
        else:
            print(f"    - 'Positions Played' kutusunda {len(position_rows)} satır bulundu.")
            for row in position_rows:
                pos_link_element = await row.query_selector("td.hauptlink a")
                match_count_element = await row.query_selector("td.zentriert")
                if pos_link_element and match_count_element:
                    pos_name = (await pos_link_element.inner_text()).strip()
                    match_count_text = (await match_count_element.inner_text()).strip()
                    if pos_name and match_count_text.isdigit():
                        match_count = int(match_count_text)
                        if match_count >= MINIMUM_POSITION_MATCHES:
                            href_value = await pos_link_element.get_attribute('href')
                            if href_value:
                                 print(f"    -> Link Eklendi: {pos_name} ({match_count} maç)")
                                 important_position_links.append({"name": pos_name, "href": href_value})
                        else: 
                            print(f"    - Atlanıyor (Az Maç): {pos_name} ({match_count} maç)")
        
        # Eğer önemli mevki bulunamazsa, ana tabloyu ("All positions") işlemesi için None linki ekle
        if not important_position_links:
            print("    - Önemli mevki bulunamadı, varsayılan tablo işlenecek.")
            important_position_links.append({"name": "Tüm Mevkiler (Varsayılan)", "href": None})

        return important_position_links

    except Exception as e:
        print(f"❌ 'Positions Played' kutusu okunurken KRİTİK HATA: {e}")
        return [] # Hata durumunda boş liste döndür
        

async def main():
    try:
        player_map_df = pd.read_csv(INPUT_MAPPING_FILE)
    except FileNotFoundError:
        print(f"❌ HATA: Ana harita dosyası bulunamadı: '{INPUT_MAPPING_FILE}'")
        return
        
  
    print("--- Ön Filtreleme Başlatılıyor ---")
    processed_slugs = set()
    output_exists = os.path.exists(OUTPUT_TASK_FILE)
    if output_exists:
        try: 
            temp_df = pd.read_csv(OUTPUT_TASK_FILE)
            if 'sofascore_slug' in temp_df.columns:
                processed_slugs = set(temp_df['sofascore_slug'])
                print(f"📝 {len(processed_slugs)} oyuncu '{OUTPUT_TASK_FILE}' dosyasında bulundu (başarılı).")
            else: output_exists = False 
        except pd.errors.EmptyDataError: output_exists = False 
        except Exception as e:
             print(f"⚠️ Çıktı dosyası ('{OUTPUT_TASK_FILE}') okunurken hata: {e}. Baştan başlanacak.")
             output_exists = False 
    error_slugs = set()
    if os.path.exists(ERROR_LOG_FILE):
        try:
            with open(ERROR_LOG_FILE, 'r', encoding='utf-8') as f_err:
                for line in f_err:
                    slug = line.split(' - ')[0].strip() 
                    if slug and '/' in slug: error_slugs.add(slug)
            print(f"🚫 {len(error_slugs)} oyuncu '{ERROR_LOG_FILE}' dosyasında bulundu (başarısız).")
        except Exception as e:
            print(f"⚠️ Hata dosyası ('{ERROR_LOG_FILE}') okunurken hata: {e}")
    slugs_to_skip = processed_slugs.union(error_slugs)
    if slugs_to_skip:
        original_count = len(player_map_df)
        player_map_df = player_map_df[~player_map_df['sofascore_slug'].isin(slugs_to_skip)]
        new_count = len(player_map_df)
        print(f"▶️ Kalan {new_count} oyuncu işlenecek (Toplam {original_count} oyuncudan {len(slugs_to_skip)} tanesi atlandı).")
    else:
        print("▶️ Tüm oyuncular işlenecek (İlk çalıştırma veya temiz başlangıç).")
   

    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False) 
        tm_page = await browser.new_page(locale="en-US") 
        
        await tm_page.route("**/*.{png,jpg,jpeg,css,woff,gif,svg}", lambda route: route.abort())
        print("🚀 Hızlandırma aktif: Resimler, CSS ve fontlar engellendi.")
        
        total_players = len(player_map_df) 
        
        with open(OUTPUT_TASK_FILE, 'a', encoding='utf-8', newline='') as f_output, \
             open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f_err:
            
            writer = csv.writer(f_output)
            
            if not output_exists or (os.path.exists(OUTPUT_TASK_FILE) and os.path.getsize(OUTPUT_TASK_FILE) == 0):
                writer.writerow(['sofascore_slug', 'transfermarkt_url', 'lig', 'sezon', 'etiket'])
            
            for i, row in player_map_df.iterrows():
                ss_slug = row['sofascore_slug']
                tm_url = row['transfermarkt_url']
                player_name = ss_slug.split('/')[0].replace('-', ' ').title()
                
                print(f"\n--- OYUNCU (İndeks {i}) İŞLENİYOR: {player_name} ---")
                
                tasks_found_for_player = False # Bu oyuncu için en az 1 görev bulduk mu?
                
                try:
                    # 1. MEVKİ LİNKLERİNİ TOPLA
                    position_links = await get_tm_position_links(tm_page, tm_url)
                    
                    if not position_links:
                        print("    - Bu oyuncu için Transfermarkt'ta işlenecek mevki bulunamadı.")
                        f_err.write(f"{ss_slug} - TM'de mevki kutusu okunamadı.\n")
                        continue
                    
                    # 2. HER BİR MEVKİ LİNKİNE GİT VE VERİLERİ ÇEK
                    base_url = "https://www.transfermarkt.com"
                    main_table_rows_selector = "table.items tbody tr"
                    
                    for position_info in position_links:
                        position_name = position_info["name"]
                        position_href = position_info["href"]
                        
                        print(f"\n    --- Mevki İşleniyor: {position_name} ---")

                        if position_href: # Eğer gidilecek bir link varsa
                            try:
                                full_position_url = base_url + position_href
                                print(f"    - Mevki sayfasına gidiliyor: {full_position_url}")
                                await tm_page.goto(full_position_url, wait_until="load", timeout=60000) 
                                print("    - Sayfa yüklendi.")
                                await tm_page.locator(main_table_rows_selector).first.wait_for(state="visible", timeout=20000)
                                print("    - Tablo görünür.")
                            except Exception as goto_e:
                                print(f"    - UYARI: Mevki sayfasına ('{position_name}') gidilirken/beklenirken hata oluştu: {goto_e}. Bu mevki atlanıyor.")
                                continue 
                        else:
                             print("    - Varsayılan tablo işleniyor (İlk sayfa)...")
                            
                             try:
                                  await tm_page.locator(main_table_rows_selector).first.wait_for(state="visible", timeout=15000)
                             except Exception:
                                  print(f"    - UYARI: Varsayılan ana tablo yüklenemedi.")
                                  continue 

                        
                        table_rows = await tm_page.query_selector_all(main_table_rows_selector)
                        if not table_rows:
                             print(f"    - UYARI: '{position_name}' için tablo sorgulama sonucu BOŞ.")
                             continue
                        print(f"    - '{position_name}' için tabloda {len(table_rows)} satır bulundu. Satırlar işleniyor...")

                        rows_written_for_this_position = 0
                        for i, row in enumerate(table_rows):
                            columns = await row.query_selector_all("td")
                            if len(columns) < 8: continue
                            try:
                                season_element = await row.query_selector("td:nth-child(1)")
                                league_element = await row.query_selector("td:nth-child(3) a") 
                                minutes_element = await row.query_selector("td.rechts:last-child") 
                                if not season_element or not league_element or not minutes_element: continue
                                season = (await season_element.inner_text()).strip()
                                league = (await league_element.get_attribute("title")).strip()
                                minutes_text_raw = await minutes_element.inner_text()
                                minutes = None
                                try:
                                    cleaned_minutes_text = re.sub(r"\D", "", minutes_text_raw)
                                    if cleaned_minutes_text: minutes = int(cleaned_minutes_text)
                                except Exception as parse_e: print(f"      -> DAKİKA DÖNÜŞTÜRME HATASI: {parse_e}")
                                
                                if minutes is not None:
                                    # 1000 DAKİKA FİLTRESİ BURADA
                                    if minutes < MINIMUM_MINUTES_PLAYED: 
                                        continue 
                                    
                                    print(f"      -> Yazılıyor: {season}, {league}, {minutes} dk, Etiket: {position_name}")
                                    new_row = [
                                        ss_slug, tm_url, league,
                                        season, position_name
                                    ]
                                    writer.writerow(new_row)
                                    rows_written_for_this_position += 1
                                    tasks_found_for_player = True # Bu oyuncu için en az 1 geçerli satır bulduk
                            except Exception as row_e:
                                continue
                        
                        if rows_written_for_this_position == 0:
                            print(f"    - UYARI: '{position_name}' mevkisi için 1000+ dk oynanmış geçerli sezon bulunamadı.")
                    
                    # Tüm mevkiler işlendikten sonra...
                    if not tasks_found_for_player:
                        print("    - Bu oyuncu için Transfermarkt'ta geçerli (1000+ dk) sezon bulunamadı (tüm mevkiler denendi).")
                        f_err.write(f"{ss_slug} - TM'de 1000+ dk sezon bulunamadı.\n")

                except Exception as e:
                    print(f"❌❌ OYUNCU İŞLEMESİNDE ANA HATA: {ss_slug} - {e}")
                    f_err.write(f"{ss_slug} - {e}\n")
                    continue

        await browser.close()
        
    print(f"\n\n✅✅✅ GÖREV LİSTESİ OLUŞTURMA TAMAMLANDI! ✅✅✅")
    print(f"Tüm görevler (veya eklemeler) şuraya kaydedildi: {OUTPUT_TASK_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
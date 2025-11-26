import asyncio
import pandas as pd
from playwright.async_api import async_playwright, Page
import os
import re
import csv
import traceback 

# --- GİRDİ VE ÇIKTI DOSYALARI ---
INPUT_TASK_FILE = "input/input.csv" # Hata ayıklama dosyasından devam ediyoruz
OUTPUT_DATASET_FILE = "output/dataset.csv"
ERROR_LOG_FILE = "output/sofascore_scraping_errors-2.txt"
HEATMAP_DIR = "output/heatmaps-3"

TAB_HEADERS = {
    "General": ["MP", "MIN", "GLS", "AST", "ASR"],
    "Shooting": ["MP", "GLS", "TOS", "SOT", "BCM"],
    "Team play": ["MP", "AST", "KEYP", "BCC", "SDR"],
    "Passing": ["MP", "APS", "APS%", "ALB", "LBA%", "ACR", "CA%"], 
    "Defending": ["MP", "CLS", "YC", "RC", "ELTG", "DRP", "TACK", "INT", "BLS", "ADW"],
    "Additional": ["MP", "GLS", "xG", "AST", "xA", "GI", "xGI"]
}

STATS_TABS = ["General", "Shooting", "Team play", "Passing", "Defending", "Additional"]

TAB_SELECTORS = {
    "General": "tab-summaryGroup",
    "Shooting": "tab-shootingGroup",
    "Team play": "tab-teamPlayGroup",
    "Passing": "tab-passingGroup",
    "Defending": "tab-defendingGroup",
    "Additional": "tab-additionalGroup"
}

# ----------------------------------------------------------------------------------
# 1. ISI HARİTASINI İNDİRME FONKSİYONU 
# ----------------------------------------------------------------------------------
async def scrape_season_heatmap(page: Page, ss_slug: str, league_name: str, season: str) -> str | None:
    print(f"       - Görev 2c: Isı Haritası Çekiliyor ({season} - {league_name})...")
    try:
        await page.get_by_role("tab", name="Season").click(timeout=5000)
        
        league_dropdown_selector = page.get_by_role('combobox', name='tournaments')
        await league_dropdown_selector.first.click(timeout=10000)
        
        try:
            await page.get_by_role("option", name=league_name, exact=True).click(timeout=3000)
        except Exception:
            await page.get_by_role("option", name=league_name.split(" ")[0]).first.click()
            
        await page.wait_for_timeout(2500)
        
        season_dropdown_selector = page.get_by_role('combobox', name='seasons')
        await season_dropdown_selector.first.click()
        await page.get_by_role("option", name=season, exact=True).click(timeout=5000) 
        await page.wait_for_timeout(2500) 
            
        heatmap_container_selector = "#player-page-heatmap" 
        heatmap_container = page.locator(heatmap_container_selector)
        
        await heatmap_container.wait_for(state="attached", timeout=5000) 
        await heatmap_container.scroll_into_view_if_needed()
        await heatmap_container.wait_for(state="visible", timeout=5000)
        await page.wait_for_timeout(1000)

        safe_league = re.sub(r'[^a-zA-Z0-9]', '', league_name)
        safe_season = season.replace('/', '-')
        heatmap_filename = f"{ss_slug.replace('/', '_')}_{safe_season}_{safe_league}.png"
        heatmap_filepath = os.path.join(HEATMAP_DIR, heatmap_filename)
        
        await heatmap_container.screenshot(path=heatmap_filepath)
        return heatmap_filename
        
    except Exception as e:
        print(f"       - ❌ HATA: Isı haritası çekilemedi ({season} - {league_name}): {e}")
        return None

# ----------------------------------------------------------------------------------
# 2. HİBRİT VERİ ÇEKME FONKSİYONU
# ----------------------------------------------------------------------------------
async def scrape_data_from_active_tab(page: Page, tab_name: str) -> dict:
    tab_data = {}
    try:
        if tab_name not in TAB_HEADERS: return {}
        
        expected_headers = TAB_HEADERS[tab_name]
        stat_headers = [f"{tab_name}_{h}" for h in expected_headers]

        # Sol Sütun
        season_container_selector = "div[class*='cceZpO'][class*='kWzByL'] div[direction='column']"
        try: await page.wait_for_selector(season_container_selector, state='visible', timeout=5000)
        except: return {}

        left_rows = await page.query_selector_all(season_container_selector)
        season_texts = []
        for row in left_rows:
            main_text_span = await row.query_selector("span")
            text_from_span = (await main_text_span.inner_text()).strip() if main_text_span else ""
            if re.match(r"^\d{2}/\d{2}$", text_from_span):
                season_texts.append(text_from_span)
        
        if not season_texts: return {}

        # Sağ Sütun
        stats_container_selector = "div[class*='fEBZed'][class*='iWGVcA'] div[direction='column']"
        await page.wait_for_selector(stats_container_selector, state='visible', timeout=5000)
        right_rows_all = await page.query_selector_all(stats_container_selector)
        stat_rows = right_rows_all[1:] 
        
        loop_count = min(len(season_texts), len(stat_rows))

        for i in range(loop_count):
            season = season_texts[i]
            tab_data[season] = {}
            current_row = stat_rows[i] 
            stat_values = [] 
            
            if tab_name == "General":
                spans = await current_row.query_selector_all("span")
                temp_values = []
                for span in spans:
                    txt = (await span.inner_text()).strip()
                    if txt and txt != '-': temp_values.append(txt)
                
                if len(temp_values) >= len(stat_headers):
                    stat_values = temp_values
                else:
                    full_text = await current_row.inner_text()
                    parts = [p.strip() for p in full_text.split('\n') if p.strip() and p.strip() != '-']
                    stat_values = parts
            else:
                stat_container = await current_row.query_selector("div[class*='ggRYVx']")
                if not stat_container: value_divs = await current_row.query_selector_all("> div")
                else: value_divs = await stat_container.query_selector_all("> div")
                
                for div in value_divs:
                    text = (await div.inner_text()).strip().split('\n')[0]
                    if text and text != "-": stat_values.append(text)
                    elif text == "-": stat_values.append(None)

            expected_count = len(stat_headers)
            
            if len(stat_values) > expected_count:
                stat_values = stat_values[-expected_count:]
            elif len(stat_values) < expected_count:
                missing = expected_count - len(stat_values)
                stat_values.extend([None] * missing)

            for j, header in enumerate(stat_headers):
                tab_data[season][header] = stat_values[j]
            
        return tab_data

    except Exception as e:
        if "Timeout" not in str(e):
            print(f"       - ❌ HATA: '{tab_name}' veri okuma hatası: {e}")
        return {}

    
# ----------------------------------------------------------------------------------
# 3. KARİYER İSTATİSTİKLERİNİ ÇEKME FONKSİYONU (is_visible DÜZELTMESİ)
# ----------------------------------------------------------------------------------
async def scrape_all_career_stats(page: Page, required_leagues: set) -> tuple[dict, dict]:
    print("       - Görev 2a: Tüm Kariyer İstatistikleri Çekiliyor...")
    stats_by_season_league = {} 
    league_name_mappings = {} 
    
    try:
        await page.get_by_role("tab", name="Career").click(timeout=5000)
        
        await page.get_by_role("combobox", name='Select competition category').click()
        await page.get_by_role("option", name="Domestic leagues").click(timeout=5000)
        await page.wait_for_timeout(2000)

        # --- LİG SEÇİMİ ---
        league_filter_dropdown = page.get_by_role('combobox', name='Select unique tournament in')
        is_dropdown_enabled = await league_filter_dropdown.is_enabled()
        available_leagues_map = {} 

        if is_dropdown_enabled:
            await league_filter_dropdown.click()
            league_options = await page.get_by_role("option").all()
            for option in league_options:
                name = (await option.inner_text()).strip()
                if name and "All" not in name: 
                    available_leagues_map[name] = True
            await league_filter_dropdown.click() 
        else:
            current_text = await league_filter_dropdown.inner_text()
            clean_name = current_text.strip()
            if clean_name:
                print(f"         - Bilgi: Oyuncunun tek bir ligi var: '{clean_name}' (Dropdown kilitli)")
                available_leagues_map[clean_name] = False 

        available_leagues_set = set(available_leagues_map.keys())

        for task_league_name in required_leagues: 
            sofascore_league_name = None
            if task_league_name in available_leagues_set:
                sofascore_league_name = task_league_name
            else:
                for available_league in available_leagues_set: 
                    if task_league_name.lower() in available_league.lower():
                        sofascore_league_name = available_league 
                        print(f"         --- Eşleştirme: '{task_league_name}' -> '{sofascore_league_name}'")
                        break 
            
            if sofascore_league_name is None:
                print(f"         --- UYARI: '{task_league_name}' SofaScore'da bulunamadı.")
                continue
            
            league_name_mappings[task_league_name] = sofascore_league_name
            print(f"\n         --- Lig İşleniyor: '{sofascore_league_name}' ---")
            
            try:
                needs_click = available_leagues_map[sofascore_league_name]
                if needs_click:
                    await league_filter_dropdown.click()
                    await page.get_by_role('option', name=sofascore_league_name, exact=True).click()
                    await page.wait_for_timeout(1500) 
                else:
                    await page.wait_for_timeout(500)

                # --- FIX: DÜZELTİLEN KISIM (is_visible) ---
                if not is_dropdown_enabled:
                    try:
                        print("           -> Tek lig modu: Açık gelen sezon kapatılıyor (Özel Selector)...")
                        
                        # Senin tespit ettiğin selector
                        collapse_arrow = page.locator('.Box.Flex.jBQtbp > .SvgWrapper').first
                        
                        # BURASI DÜZELTİLDİ: isVisible() -> is_visible()
                        if await collapse_arrow.is_visible(): 
                            await collapse_arrow.click()
                            print("           -> Ok işaretine tıklandı.")
                            await page.wait_for_timeout(1500) 
                        else:
                            print("           - Uyarı: Kapatma oku (jBQtbp) görünür değil.")
                            
                    except Exception as e:
                        print(f"           - Uyarı: Sezon satırı kapatılamadı: {e}")

                # --- GENERAL SEKMESİNE SIFIRLAMA ---
                try:
                    general_btn = page.get_by_test_id(TAB_SELECTORS["General"])
                    await general_btn.click()
                    await page.wait_for_timeout(1000)
                except Exception: pass

                # 1. General Verisini Çek
                print(f"             - 'General' sekmesi işleniyor...")
                general_data = await scrape_data_from_active_tab(page, "General")
                
                for season, stats in general_data.items():
                    if season not in stats_by_season_league: stats_by_season_league[season] = {}
                    if sofascore_league_name not in stats_by_season_league[season]:
                        stats_by_season_league[season][sofascore_league_name] = {}
                    stats_by_season_league[season][sofascore_league_name].update(stats)

                # 2. Diğer Sekmeleri Çek
                for tab_name in STATS_TABS[1:]: 
                    print(f"             - '{tab_name}' sekmesi işleniyor...")
                    try:
                        testid = TAB_SELECTORS[tab_name]
                        await page.get_by_test_id(testid).click()
                        await page.wait_for_timeout(500)
                        
                        tab_data = await scrape_data_from_active_tab(page, tab_name)
                        
                        for season, stats in tab_data.items():
                            if season in stats_by_season_league and sofascore_league_name in stats_by_season_league[season]:
                                stats_by_season_league[season][sofascore_league_name].update(stats)
                            else: 
                                if season not in stats_by_season_league: stats_by_season_league[season] = {}
                                if sofascore_league_name not in stats_by_season_league[season]:
                                    stats_by_season_league[season][sofascore_league_name] = {}
                                stats_by_season_league[season][sofascore_league_name].update(stats)
                                
                    except Exception as e:
                        print(f"             - ❌ HATA ({tab_name}): {e}")
                        continue 
            
            except Exception as e:
                print(f"         - ❌ HATA (Lig Seçimi): {e}")
                continue
                
    except Exception as e:
        print(f"       - ❌ HATA (Genel Kariyer): {e}")
        return {}, {}
        
    return stats_by_season_league, league_name_mappings

async def main():
    os.makedirs(HEATMAP_DIR, exist_ok=True)
    
    try:
        task_df = pd.read_csv(INPUT_TASK_FILE)
    except FileNotFoundError:
        print(f"❌ HATA: '{INPUT_TASK_FILE}' bulunamadı.")
        return
        
    processed_slugs_seasons = set()
    output_exists = os.path.exists(OUTPUT_DATASET_FILE)
    all_headers_in_file = []

    if output_exists:
        try:
            with open(OUTPUT_DATASET_FILE, 'r', encoding='utf-8') as f_read:
                reader = csv.reader(f_read)
                try: all_headers_in_file = next(reader)
                except StopIteration: output_exists = False

            if output_exists and all_headers_in_file:
                temp_df = pd.read_csv(OUTPUT_DATASET_FILE)
                if 'sofascore_slug' in temp_df.columns:
                    for _, row in temp_df.iterrows():
                        processed_slugs_seasons.add((row['sofascore_slug'], row['season'], row['league']))
                    print(f"📝 {len(processed_slugs_seasons)} veri daha önce işlenmiş, atlanacak.")
                else: output_exists = False
        except Exception: output_exists = False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ss_page = await browser.new_page(locale="en-US")
        
        await ss_page.route(re.compile(r"\.(jpg|png|jpeg|woff|gif)$"), lambda route: route.abort())

        try:
            await ss_page.goto("https://www.sofascore.com", timeout=10000)
            try: await ss_page.locator('button:has-text("Accept all")').click(timeout=5000)
            except: pass
        except: pass
        
        grouped_tasks = task_df.groupby('sofascore_slug')
        print(f"Toplam {len(grouped_tasks)} oyuncu işlenecek.")
        
        with open(OUTPUT_DATASET_FILE, 'a', encoding='utf-8', newline='') as f_output:
            writer = None
            if output_exists:
                writer = csv.DictWriter(f_output, fieldnames=all_headers_in_file, extrasaction='ignore')
            
            player_count = 0
            for ss_slug, tasks_for_player in grouped_tasks:
                player_count += 1
                player_name = ss_slug.split('/')[0].replace('-', ' ').title()
                tm_url = tasks_for_player.iloc[0]['transfermarkt_url']
                
                print(f"\n--- OYUNCU {player_count} İŞLENİYOR: {player_name} ---")
                
                tasks_to_do = []
                for task in tasks_for_player.itertuples():
                    if (ss_slug, task.sezon, task.lig) not in processed_slugs_seasons:
                        tasks_to_do.append(task)
                
                if not tasks_to_do:
                    print("       - Tüm sezonlar tamamlanmış.")
                    continue

                try:
                    await ss_page.goto(f"https://www.sofascore.com/player/{ss_slug}", wait_until="load", timeout=10000)
                    leagues_to_scrape = set(task.lig for task in tasks_to_do)
                    
                    all_career_stats, league_mappings = await scrape_all_career_stats(ss_page, leagues_to_scrape)
                    
                    if not all_career_stats: continue

                    rows_to_write = []
                    for task in tasks_to_do:
                        season = task.sezon
                        league_tm = task.lig
                        ss_league = league_mappings.get(league_tm)
                        
                        if not ss_league: continue
                        
                        heatmap_filename = await scrape_season_heatmap(ss_page, ss_slug, ss_league, season)
                        
                        if season in all_career_stats and ss_league in all_career_stats[season]:
                            season_stats = all_career_stats[season][ss_league]
                            final_row = {
                                "sofascore_slug": ss_slug,
                                "transfermarkt_url": tm_url,
                                "player_name": player_name,
                                "season": season,
                                "league": league_tm,
                                "position_label": task.etiket,
                                "heatmap_filename": heatmap_filename,
                                **season_stats 
                            }
                            rows_to_write.append(final_row)
                        else:
                            print(f"         - Veri Yok: {season} - {ss_league}")

                    if rows_to_write:
                        all_new_headers = set()
                        for row in rows_to_write: all_new_headers.update(row.keys())
                        
                        if not writer:
                            base_headers = ["sofascore_slug", "transfermarkt_url", "player_name", "season", "league", "position_label", "heatmap_filename"]
                            stat_headers = sorted([h for h in list(all_new_headers) if h not in base_headers])
                            final_headers = base_headers + stat_headers
                            
                            writer = csv.DictWriter(f_output, fieldnames=final_headers, extrasaction='ignore')
                            if not output_exists: writer.writeheader()
                            all_headers_in_file = final_headers[:]
                        else:
                            for h in all_new_headers:
                                if h not in all_headers_in_file:
                                    all_headers_in_file.append(h)
                        
                        writer.writerows(rows_to_write)
                        f_output.flush() 
                        print(f"       ✅ {len(rows_to_write)} veri kaydedildi.")

                except Exception as e:
                    print(f"❌ ANA HATA ({player_name}): {e}")
                    with open(ERROR_LOG_FILE, 'a') as f_err: f_err.write(f"{ss_slug}: {e}\n")

        await browser.close()
    print(f"\n✅ İŞLEM TAMAMLANDI: {OUTPUT_DATASET_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
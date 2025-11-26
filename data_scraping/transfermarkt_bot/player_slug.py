import asyncio
from playwright.async_api import async_playwright
import os

LEAGUES = "input/leagues_link.csv"
output_dir = "output"

def load_leagues_from_file(file_path=LEAGUES):
    leagues = {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if "," in line:
                    name, url = line.strip().split(",", 1)
                    clean_url = url.split("#")[0]
                    leagues[name] = clean_url
    except FileNotFoundError:
        print(f"❌ HATA: '{file_path}' dosyası bulunamadı. Lütfen dosyayı oluşturduğunuzdan emin olun.")
        return None
    return leagues

async def scrape_league_player_slugs(page, league_name, league_url):
    """Belirli bir ligin URL'sinden tüm oyuncu slug'larını çeker ve bir set olarak döndürür."""
    all_slugs = set()
    print(f"\n--- İşleniyor: {league_name} ---")
    
    await page.goto(league_url, timeout=60000)
    
    team_links = await page.query_selector_all("a[href^='/team/football']")
    team_urls = set()
    for link in team_links:
        href = await link.get_attribute('href')
        if href:
            clean_url = f"https://www.sofascore.com{href.split('?')[0]}"
            team_urls.add(clean_url)
    
    print(f"📌 {len(team_urls)} takım bulundu.")

    for team_url in team_urls:
        players_page_url = f"{team_url}#tab:players"
        try:
            print(f"  🔍 Oyuncu listesi açılıyor: {team_url.split('/')[-2]}")
            await page.goto(players_page_url, timeout=60000)
            
            wait_selector = "div#tabpanel-squad a[href*='/player/']"
            await page.wait_for_selector(wait_selector, timeout=20000)

            player_links = await page.query_selector_all(wait_selector)
            print(f"    -> {len(player_links)} oyuncu bulundu.")

            for a in player_links:
                href = await a.get_attribute("href")
                if href and "/player/" in href:
                    slug = href.split("/player/")[-1]
                    all_slugs.add(slug)

        except Exception as e:
            print(f"  ❌ Bu takım işlenirken hata oluştu (atlanıyor): {team_url.split('/')[-2]} | Hata: Timeout")
            continue
            
    return all_slugs

async def main():
    leagues_to_scrape = load_leagues_from_file()
    if not leagues_to_scrape:
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(locale="en-US")

        await page.goto("https://www.sofascore.com", timeout=60000)
        try:
            await page.get_by_role("button", name="Accept all").click(timeout=5000)
            print("🍪 Çerezler kabul edildi.")
        except Exception:
            print("🍪 Çerez banner'ı bulunamadı veya zaten kabul edilmiş.")
            
        all_leagues_slugs = set()

        for league_name, league_url in leagues_to_scrape.items():
            league_slugs = await scrape_league_player_slugs(page, league_name, league_url)
            all_leagues_slugs.update(league_slugs)
            
        await browser.close()

        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, "all_player_slugs.txt")
        
        with open(file_path, "w", encoding="utf-8") as f:
            for slug in sorted(list(all_leagues_slugs)):
                f.write(f"{slug}\n")

        print(f"\n✅✅✅ İŞLEM TAMAMLANDI! ✅✅✅")
        print(f"Toplam {len(leagues_to_scrape)} ligden {len(all_leagues_slugs)} benzersiz oyuncu slug'ı dosyaya kaydedildi → {file_path}")

if __name__ == "__main__":
    asyncio.run(main())
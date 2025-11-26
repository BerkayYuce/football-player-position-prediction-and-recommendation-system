import pandas as pd
import os

# --- DOSYA YOLLARI ---
ERROR_LOG_FILE = "output/sofascore_scraping_errors.txt"  # Hata kayıtlarının olduğu dosya
MASTER_INPUT_FILE = "input/players.csv"                   # Tüm oyuncuların olduğu ana dosya (players.csv dediğin)
RETRY_OUTPUT_FILE = "output/retry_input.csv"             # Yeni oluşturulacak, sadece hata verenlerin olduğu dosya

def create_retry_dataset():
    # 1. Hata dosyasının varlığını kontrol et
    if not os.path.exists(ERROR_LOG_FILE):
        print(f"❌ Hata: '{ERROR_LOG_FILE}' dosyası bulunamadı.")
        return

    if not os.path.exists(MASTER_INPUT_FILE):
        print(f"❌ Hata: '{MASTER_INPUT_FILE}' dosyası bulunamadı.")
        return

    print("🔄 Hata dosyası taranıyor ve oyuncu kimlikleri (slug) ayıklanıyor...")

    # 2. Hata dosyasından sadece oyuncu slug'larını (ID'lerini) çek
    failed_slugs = set()
    
    try:
        with open(ERROR_LOG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Satır yapısı: "karel-pojezny/999632 - SofaScore'da..."
                # " - " karakterine göre bölüp ilk kısmı alıyoruz.
                parts = line.split(' - ')
                if parts:
                    slug = parts[0].strip()
                    failed_slugs.add(slug)
                    
    except Exception as e:
        print(f"❌ Hata dosyası okunurken sorun oluştu: {e}")
        return

    print(f"⚠️ Toplam {len(failed_slugs)} benzersiz oyuncu hata almış.")

    # 3. Ana veri dosyasını oku
    print(f"🔄 Ana veri dosyası okunuyor: {MASTER_INPUT_FILE}")
    try:
        df = pd.read_csv(MASTER_INPUT_FILE)
    except Exception as e:
        print(f"❌ CSV okunurken hata: {e}")
        return

    # 4. Sadece hata alan slug'lara sahip satırları filtrele
    # 'sofascore_slug' sütunu, failed_slugs kümesinde olanları seç
    if 'sofascore_slug' not in df.columns:
        print("❌ Hata: Ana CSV dosyasında 'sofascore_slug' sütunu bulunamadı.")
        return

    retry_df = df[df['sofascore_slug'].isin(failed_slugs)]

    # 5. Sonucu kaydet
    if not retry_df.empty:
        retry_df.to_csv(RETRY_OUTPUT_FILE, index=False, encoding='utf-8')
        print(f"\n✅ BAŞARILI! Yeni dosya oluşturuldu: {RETRY_OUTPUT_FILE}")
        print(f"   - Toplam Satır Sayısı: {len(retry_df)}")
        print(f"   - Benzersiz Oyuncu Sayısı: {retry_df['sofascore_slug'].nunique()}")
        print("\n👉 Şimdi 'main.py' dosyasındaki 'INPUT_TASK_FILE' yolunu 'input/retry_input.csv' olarak değiştirip tekrar çalıştırabilirsin.")
    else:
        print("❌ Uyarı: Hata dosyasındaki oyuncular ana CSV dosyasında bulunamadı. Eşleşme yok.")

if __name__ == "__main__":
    create_retry_dataset()
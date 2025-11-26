import pandas as pd
import os

# Temizlenecek dosyanın yolu
INPUT_FILE = "input/transfermarkt_dataset.csv" 

# Temizlenmiş verinin kaydedileceği yer
OUTPUT_FILE = "output/tm_dataset_temiz.csv" 

# Kaldırılacak pozisyonların (etiketlerin) listesi
FORBIDDEN_POSITIONS = ['Goalkeeper', 'Tüm Mevkiler (Varsayılan)']
# --- AYARLAR SONU ---

def clean_dataset():
    print(f"🧹 Temizleme betiği başlatıldı...")
    
    # 1. Girdi dosyasını oku
    try:
        df = pd.read_csv(INPUT_FILE)
        print(f"📄 '{INPUT_FILE}' dosyası okundu. Başlangıçtaki satır sayısı: {len(df)}")
    except FileNotFoundError:
        print(f"❌ HATA: Girdi dosyası bulunamadı: '{INPUT_FILE}'")
        return
    except Exception as e:
        print(f"❌ HATA: Dosya okunurken bir hata oluştu: {e}")
        return


    if 'etiket' not in df.columns:
        print(f"⚠️ UYARI: 'etiket' sütunu '{INPUT_FILE}' dosyasında bulunamadı. Temizleme yapılamadı.")
        print("❌ Program durduruldu. Lütfen CSV dosyanızı ve 'etiket' sütun adını kontrol edin.")
        return

    # 3. Filtreleme işlemi
    initial_rows = len(df)
    
    # Filtreleme için pozisyonları küçük harfe çevir
    forbidden_positions_lower = [p.lower() for p in FORBIDDEN_POSITIONS]
    
    try:
        df_cleaned = df[~df['etiket'].astype(str).str.strip().str.lower().isin(forbidden_positions_lower)]
    except Exception as e:
        print(f"❌ HATA: Filtreleme sırasında bir hata oluştu: {e}")
        return

    final_rows = len(df_cleaned)
    removed_rows = initial_rows - final_rows

    print(f"✅ Temizleme tamamlandı.")
    print(f"   - Kaldırılan satır sayısı ('Goalkeeper' veya 'Tüm Mevkiler'): {removed_rows}")
    print(f"   - Kalan satır sayısı: {final_rows}")

    # 4. Temizlenmiş veriyi yeni dosyaya kaydet
    try:
        # output klasörünün var olduğundan emin ol
        os.makedirs("output", exist_ok=True)
        
        df_cleaned.to_csv(OUTPUT_FILE, index=False, encoding='utf-8')
        print(f"💾 Temizlenmiş veri başarıyla '{OUTPUT_FILE}' dosyasına kaydedildi.")
        
    except Exception as e:
        print(f"❌ HATA: Temizlenmiş dosya kaydedilirken bir hata oluştu: {e}")

if __name__ == "__main__":
    clean_dataset()
import pandas as pd
import os

# --- DOSYA YOLLARI ---
# Bir önceki adımda oluşturduğumuz dosyayı girdi olarak alıyoruz
INPUT_CSV = "output/dataset_final_cleaned.csv"
# Sonuç dosyası (Aynı ismi vererek üzerine de yazabiliriz ama güvenli olsun diye yeni isim veriyorum)
OUTPUT_CSV = "output/dataset_ready_to_use.csv"

def remove_duplicates_final():
    # 1. Dosya Kontrolü
    if not os.path.exists(INPUT_CSV):
        print(f"❌ Hata: '{INPUT_CSV}' dosyası bulunamadı. Önceki adımı çalıştırdın mı?")
        return

    print(f"📂 Dosya okunuyor: {INPUT_CSV} ...")
    try:
        # Tüm veriyi 'string' (metin) olarak okuyoruz ki 35 ile 35.0 farkı olmasın,
        # önceki adımda zaten temizlemiştik ama garanti olsun.
        df = pd.read_csv(INPUT_CSV, dtype=str)
    except Exception as e:
        print(f"❌ Okuma hatası: {e}")
        return

    original_count = len(df)
    print(f"   -> Toplam Satır Sayısı: {original_count}")

    print("🧹 Mükerrer (Kendini tekrar eden) satırlar taranıyor...")

    # 2. DUPLICATE SİLME İŞLEMİ
    # keep='first': İlk bulduğunu tut, sonrakileri sil.
    df.drop_duplicates(inplace=True)

    final_count = len(df)
    removed_count = original_count - final_count

    # 3. Kaydet
    print(f"💾 Temizlenmiş dosya kaydediliyor: {OUTPUT_CSV}")
    df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')

    print(f"\n✅✅✅ TEMİZLİK TAMAMLANDI! ✅✅✅")
    print(f"---------------------------------------------")
    print(f"Başlangıç Satır Sayısı : {original_count}")
    print(f"Silinen Tekrar Sayısı  : {removed_count}")
    print(f"Kalan Net Satır Sayısı : {final_count}")
    print(f"---------------------------------------------")
    print(f"Dosyanız kullanıma hazır: {OUTPUT_CSV}")

if __name__ == "__main__":
    remove_duplicates_final()
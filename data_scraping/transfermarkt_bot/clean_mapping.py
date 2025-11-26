import os
import csv

INPUT_RAW_FILE = 'output/player_mapping.csv'
OUTPUT_CLEAN_FILE = 'output/player_mapping_temiz.csv'
OUTPUT_REJECTED_FILE = 'output/hatali_linkler.txt'

def clean_mapping_file():
    """
    Ham mapping dosyasını okur, sadece gerçek oyuncu linklerini içeren
    temiz bir dosya oluşturur ve hatalı linkleri ayıklar.
    """
    if not os.path.exists(INPUT_RAW_FILE):
        print(f"❌ HATA: Temizlenecek dosya bulunamadı: '{INPUT_RAW_FILE}'")
        return

    print(f"🧹 '{INPUT_RAW_FILE}' dosyası temizleniyor...")
    clean_count = 0
    rejected_count = 0

    with open(INPUT_RAW_FILE, 'r', encoding='utf-8') as f_raw, \
         open(OUTPUT_CLEAN_FILE, 'w', encoding='utf-8', newline='') as f_clean, \
         open(OUTPUT_REJECTED_FILE, 'w', encoding='utf-8') as f_rejected:
        
        reader = csv.reader(f_raw)
        writer = csv.writer(f_clean)
        header = next(reader)
        writer.writerow(header)

        for row in reader:
            if len(row) < 2: continue
            sofascore_slug, transfermarkt_url = row[0], row[1]

            if "/profil/spieler/" in transfermarkt_url:
                writer.writerow(row)
                clean_count += 1
            else:
                f_rejected.write(f"{sofascore_slug},{transfermarkt_url}\n")
                rejected_count += 1
                
    print("\n✅ TEMİZLEME İŞLEMİ TAMAMLANDI!")
    print(f"👍 {clean_count} adet doğru oyuncu linki bulundu ve '{OUTPUT_CLEAN_FILE}' dosyasına kaydedildi.")
    print(f"🗑️ {rejected_count} adet hatalı link ayıklandı ve '{OUTPUT_REJECTED_FILE}' dosyasına kaydedildi.")

if __name__ == "__main__":
    clean_mapping_file()
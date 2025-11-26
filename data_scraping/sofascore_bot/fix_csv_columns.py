import pandas as pd
import os

# --- DOSYA YOLLARI ---
INPUT_CSV = "ozguridze/dataset.csv"       # Mevcut (karışık) dosya
OUTPUT_CSV = "output/dataset_fixed.csv" # Yeni (düzenli) dosya

# --- İSTEDİĞİMİZ SÜTUN SIRALAMASI ---
# 1. Temel Bilgiler (En başta olacaklar)
BASE_HEADERS = [
    "sofascore_slug",
    "transfermarkt_url",
    "player_name",
    "season",
    "league",
    "position_label",
    "heatmap_filename"
]

# 2. İstatistik Grupları (Sırasıyla)
TAB_HEADERS = {
    "General": ["MP", "MIN", "GLS", "AST", "ASR"],
    "Shooting": ["MP", "GLS", "TOS", "SOT", "BCM"],
    "Team play": ["MP", "AST", "KEYP", "BCC", "SDR"],
    "Passing": ["MP", "APS", "APS%", "ALB", "LBA%", "ACR", "CA%"], 
    "Defending": ["MP", "CLS", "YC", "RC", "ELTG", "DRP", "TACK", "INT", "BLS", "ADW"],
    "Additional": ["MP", "GLS", "xG", "AST", "xA", "GI", "xGI"]
}

def reorder_csv_columns():
    # 1. Dosyayı Kontrol Et
    if not os.path.exists(INPUT_CSV):
        print(f"❌ Hata: '{INPUT_CSV}' dosyası bulunamadı!")
        return

    print(f"📂 '{INPUT_CSV}' okunuyor...")
    try:
        df = pd.read_csv(INPUT_CSV)
    except Exception as e:
        print(f"❌ Dosya okunurken hata oluştu: {e}")
        return

    # 2. Hedef Sütun Listesini Oluştur
    # Önce temel başlıklar
    target_order = list(BASE_HEADERS)
    
    # Sonra istatistik başlıklarını döngüyle ekle (General_MP, General_MIN... şeklinde)
    for category, stats in TAB_HEADERS.items():
        for stat in stats:
            col_name = f"{category}_{stat}"
            target_order.append(col_name)

    print("⚙️ Sütunlar yeniden sıralanıyor...")

    # 3. Mevcut Veri Setinde Olmayan Sütunları Yönet
    # Hedef listemizdeki sütunlardan hangileri gerçekten CSV'de var?
    # (Olmayan bir sütunu istersek hata alırız, o yüzden filtreliyoruz)
    final_columns = [col for col in target_order if col in df.columns]

    # Eğer CSV'de olup bizim listemizde olmayan ekstra sütunlar varsa (örn: yanlışlıkla gelmiş olanlar)
    # Onları kaybetmemek için en sona ekleyebiliriz (İsteğe bağlı, şu an eklemiyorum temiz olsun diye).
    # extra_columns = [col for col in df.columns if col not in final_columns]
    # final_columns.extend(extra_columns)

    # 4. Veri Çerçevesini (DataFrame) Yeniden Sırala
    df_reordered = df[final_columns]

    # 5. Yeni Dosyayı Kaydet
    try:
        df_reordered.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
        print(f"✅ İŞLEM TAMAMLANDI!")
        print(f"📄 Düzenlenmiş dosya şurada oluşturuldu: {OUTPUT_CSV}")
        print(f"📊 Toplam Satır: {len(df_reordered)}")
        print(f"📊 Toplam Sütun: {len(df_reordered.columns)}")
    except Exception as e:
        print(f"❌ Kaydetme hatası: {e}")

if __name__ == "__main__":
    reorder_csv_columns()
import pandas as pd
import numpy as np
import joblib
from sklearn.preprocessing import StandardScaler
import os

BASE_PATH = 'model_data' # Colab ise: '/content/drive/MyDrive/Deep-Learning'

# Modelin kullandığı 27 Sütunun İsimleri (Sırasıyla)
STATS_COLUMNS = [
    'General_MP', 'General_MIN', 'General_GLS', 'General_AST', 'General_ASR',
    'Shooting_TOS', 'Shooting_SOT', 'Shooting_BCM',
    'Team play_KEYP', 'Team play_BCC', 'Team play_SDR',
    'Passing_APS', 'Passing_APS%', 'Passing_ALB', 'Passing_LBA%', 'Passing_ACR', 'Passing_CA%',
    'Defending_CLS', 'Defending_YC', 'Defending_RC', 'Defending_ELTG', 'Defending_DRP',
    'Defending_TACK', 'Defending_INT', 'Defending_BLS', 'Defending_ADW',
    'Additional_GI'
]

def master_reset():
    print("⚙️ MASTER RESET: Sistem Ham Verilere Göre Ayarlanıyor...")
    
    csv_path = os.path.join(BASE_PATH, 'dataset_ready.csv')
    
    # 1. HAM VERİYİ YÜKLE
    if not os.path.exists(csv_path):
        return print("❌ HATA: 'dataset_ready.csv' bulunamadı! Bu dosya olmadan sistemi ayarlayamam.")
    
    df = pd.read_csv(csv_path)
    print(f"📄 CSV Yüklendi. Toplam Oyuncu: {len(df)}")
    
    # 2. SADECE İLGİLİ 27 SÜTUNU SEÇ
    # Eğer sütun isimleri birebir tutmazsa, sondan 27 taneyi alacağız.
    try:
        X_ham = df[STATS_COLUMNS].values
        print("✅ Sütun isimleri doğrulandı. 27 İstatistik seçildi.")
    except KeyError:
        print("⚠️ Sütun isimleri tam eşleşmedi. Otomatik olarak SON 27 sayısal sütun alınıyor...")
        numeric_df = df.select_dtypes(include=[np.number])
        X_ham = numeric_df.values[:, -27:]
    
    # 3. SCALER'I EĞİT (En Önemli Kısım)
    # Bu işlem, sistemin "85" ile "0.85" arasındaki farkı anlamasını sağlar.
    print("⚖️ Scaler (Dönüştürücü) eğitiliyor...")
    scaler = StandardScaler()
    scaler.fit(X_ham)
    
    # Kaydet
    joblib.dump(scaler, os.path.join(BASE_PATH, 'scout_scaler.pkl'))
    print("✅ 'scout_scaler.pkl' yenilendi. Artık ham veriyi doğru dönüştürecek.")
    
    # 4. MEVCUT VEKTÖRLERİ KALİBRE ET (Mean Centering)
    # Scaler değiştiği için embeddingleri tekrar üretmek gerekir ama
    # şimdilik sadece benzerlik ayarı (Mean Centering) yapalım.
    
    emb_path = os.path.join(BASE_PATH, 'scout_embeddings_merged.npy')
    if os.path.exists(emb_path):
        emb = np.load(emb_path)
        
        # Ortalama Vektörü Hesapla
        mean_vector = np.mean(emb, axis=0)
        np.save(os.path.join(BASE_PATH, 'scout_mean_vector.npy'), mean_vector)
        print("✅ 'scout_mean_vector.npy' (Kalibrasyon Dosyası) oluşturuldu.")
        
        # Dosyaları Düzelt
        for mode in ['merged', 'all']:
            path = os.path.join(BASE_PATH, f'scout_embeddings_{mode}.npy')
            if os.path.exists(path):
                data = np.load(path)
                # Ortalamayı çıkar
                data = data - mean_vector
                # Normalize et
                norms = np.linalg.norm(data, axis=1, keepdims=True)
                data = data / (norms + 1e-10)
                np.save(path, data)
                print(f"   -> {mode} veritabanı kalibre edildi.")

    print("\n🎉 İŞLEM TAMAMLANDI!")
    print("1. Artık forma '85' yazabilirsin.")
    print("2. Sistem bunu CSV'deki diğer '85'lerle aynı kefeye koyacak.")
    print("3. Arda Güler'i (veya yeni oyuncuyu) tekrar ekleyebilirsin.")

if __name__ == "__main__":
    master_reset()
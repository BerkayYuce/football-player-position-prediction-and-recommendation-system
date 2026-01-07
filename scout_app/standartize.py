import numpy as np
import os

BASE_PATH = 'model_data'

def fix_and_save_mean():
    print("🔧 SİSTEM KALİBRASYONU BAŞLIYOR...")
    
    # 1. Ana veriyi yükle (Merged olanı referans alıyoruz)
    path_merged = os.path.join(BASE_PATH, 'scout_embeddings_merged.npy')
    
    if not os.path.exists(path_merged):
        return print("❌ Dosya bulunamadı!")
        
    emb = np.load(path_merged)
    
    # 2. ORTALAMA VEKTÖRÜ HESAPLA (Global Mean)
    # Bu, "Standart bir futbolcunun" matematiksel karşılığıdır.
    mean_vector = np.mean(emb, axis=0)
    
    # Bu ortalamayı kaydedelim, çünkü yeni oyuncu eklerken de bunu çıkaracağız!
    np.save(os.path.join(BASE_PATH, 'scout_mean_vector.npy'), mean_vector)
    print("✅ Ortalama vektör (Kalibrasyon Dosyası) kaydedildi: scout_mean_vector.npy")
    
    # 3. DOSYALARI DÜZELT (Merged ve All)
    for fname in ['scout_embeddings_merged.npy', 'scout_embeddings_all.npy']:
        fpath = os.path.join(BASE_PATH, fname)
        if not os.path.exists(fpath): continue
        
        data = np.load(fpath)
        
        # Ortalamayı çıkar (Merkezileştirme)
        data = data - mean_vector
        
        # Tekrar Normalize et
        norms = np.linalg.norm(data, axis=1, keepdims=True)
        data = data / (norms + 1e-10)
        
        np.save(fpath, data)
        print(f"✅ {fname} kalibre edildi.")

if __name__ == "__main__":
    fix_and_save_mean()
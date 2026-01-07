from flask import Flask, render_template, request, redirect, url_for, flash
import numpy as np
import pandas as pd
import os
import torch
import torch.nn as nn
import timm
from PIL import Image
from torchvision import transforms
import joblib
from sklearn.metrics.pairwise import cosine_similarity
import warnings

warnings.filterwarnings("ignore")

app = Flask(__name__)
app.secret_key = 'super_secret_key_scout_v2'

BASE_PATH = 'model_data'
DEVICE = 'cpu'

# --- MODEL (AYNI) ---
class EarlyFusionModel(nn.Module):
    def __init__(self, num_classes=9):
        super(EarlyFusionModel, self).__init__()
        self.img_net = timm.create_model('resnet18', pretrained=False, num_classes=0) 
        self.tab_net = nn.Sequential(
            nn.Linear(27, 128), nn.BatchNorm1d(128), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(128, 256), nn.BatchNorm1d(256), nn.ReLU()
        )
        self.head = nn.Sequential(
            nn.Linear(512 + 256, 256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, num_classes)
        )
    def forward_features(self, i, t):
        f_i = torch.nn.functional.normalize(self.img_net(i), p=2, dim=1)
        f_t = torch.nn.functional.normalize(self.tab_net(t), p=2, dim=1)
        return torch.cat((f_i, f_t), dim=1)

# --- SİSTEM YÜKLEME ---
print("⚙️ Sistem Başlatılıyor...")
data_store = {'merged': {}, 'all': {}}
model = None
scaler = None
mean_vector = None # YENİ: Ortalama Vektör

transforms_val = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

try:
    # 1. Veritabanlarını Yükle
    for mode in ['merged', 'all']:
        data_store[mode]['emb'] = np.load(os.path.join(BASE_PATH, f'scout_embeddings_{mode}.npy'))
        data_store[mode]['meta'] = pd.read_csv(os.path.join(BASE_PATH, f'scout_metadata_{mode}.csv'))

    # 2. Modeli, Scaler'ı ve Mean Vector'ü Yükle
    scaler = joblib.load(os.path.join(BASE_PATH, 'scout_scaler.pkl'))
    
    # YENİ: Kalibrasyon dosyasını yükle
    if os.path.exists(os.path.join(BASE_PATH, 'scout_mean_vector.npy')):
        mean_vector = np.load(os.path.join(BASE_PATH, 'scout_mean_vector.npy'))
        print("✅ Kalibrasyon (Mean Vector) Yüklendi.")
    else:
        print("⚠️ UYARI: Mean Vector bulunamadı! Yeni eklenen oyuncular uyumsuz olabilir.")
        mean_vector = np.zeros((768,)) # Hata vermesin diye boş vektör

    model = EarlyFusionModel()
    model.load_state_dict(torch.load(os.path.join(BASE_PATH, 'scout_model.pth'), map_location=DEVICE), strict=False)
    model.to(DEVICE)
    model.eval()
    
    print("✅ TÜM SİSTEM HAZIR!")
except Exception as e:
    print(f"❌ HATA: {e}")

# --- ANA SAYFA ---
@app.route('/', methods=['GET', 'POST'])
def index():
    target_player = None
    similar_players = []
    error_msg = None
    selected_mode = 'merged'

    if request.method == 'POST':
        query = request.form.get('player_name')
        selected_mode = request.form.get('search_mode')
        
        if query and selected_mode in data_store:
            embeddings = data_store[selected_mode]['emb']
            df_meta = data_store[selected_mode]['meta']
            
            matches = df_meta[df_meta['scout_name'].str.contains(query, case=False, na=False)]
            
            if len(matches) == 0:
                error_msg = f"'{query}' bulunamadı."
            else:
                target_idx = matches.index[0]
                target_name = matches.iloc[0]['scout_name']
                target_pos = matches.iloc[0]['position_label']
                target_player = {'name': target_name, 'pos': target_pos, 'mode': selected_mode}

                # Benzerlik
                target_vec = embeddings[target_idx].reshape(1, -1)
                sims = cosine_similarity(target_vec, embeddings)[0]
                idxs = sims.argsort()[::-1][:15]

                for i in idxs:
                    if sims[i] > 0.99999: continue
                    p_name = df_meta.iloc[i]['scout_name']
                    if selected_mode == 'merged' and p_name == target_name: continue

                    score = sims[i] * 100
                    # Eksi puanları 0 yap (Nadiren olabilir)
                    score = max(0, score)
                    
                    similar_players.append({
                        'name': p_name,
                        'score': round(score, 1),
                        'pos': df_meta.iloc[i]['position_label'],
                        'bar_width': int(score)
                    })
                    if len(similar_players) >= 10: break

    return render_template('index.html', target=target_player, similars=similar_players, error=error_msg, current_mode=selected_mode)

# --- OYUNCU EKLEME ---
@app.route('/add_player', methods=['GET', 'POST'])
def add_player():
    if request.method == 'POST':
        try:
            name = request.form['name']
            team = request.form['team']
            position = request.form['position']
            full_name = f"{name} ({team})"
            
            # Verileri Al
            stats_list = [float(request.form.get(f'stat_{i}')) for i in range(1, 28)]
            stats_vector = np.array([stats_list])
            
            # Normalize Et (Scaler)
            stats_scaled = scaler.transform(stats_vector)
            stats_tensor = torch.FloatTensor(stats_scaled).to(DEVICE)
            
            # Resim
            file = request.files['heatmap']
            img = Image.open(file).convert('RGB')
            img_tensor = transforms_val(img).unsqueeze(0).to(DEVICE)
            
            # Modelden Ham DNA Çıkar
            with torch.no_grad():
                raw_dna = model.forward_features(img_tensor, stats_tensor).cpu().numpy().flatten()
            
            # --- KRİTİK ADIM: MERKEZİLEŞTİRME (Calibration) ---
            # Yeni oyuncudan da ortalamayı çıkarıyoruz ki diğerleriyle uyumlu olsun
            calibrated_dna = raw_dna - mean_vector
            
            # L2 Normalize (Tekrar boyunu 1 yap)
            norm = np.linalg.norm(calibrated_dna)
            if norm > 0: calibrated_dna = calibrated_dna / norm
            
            # Kaydet
            final_vector = calibrated_dna.reshape(1, -1)
            
            for mode in ['merged', 'all']:
                data_store[mode]['emb'] = np.vstack([data_store[mode]['emb'], final_vector])
                np.save(os.path.join(BASE_PATH, f'scout_embeddings_{mode}.npy'), data_store[mode]['emb'])
                
                new_row = pd.DataFrame({'scout_name': [full_name], 'position_label': [position]})
                data_store[mode]['meta'] = pd.concat([data_store[mode]['meta'], new_row], ignore_index=True)
                data_store[mode]['meta'].to_csv(os.path.join(BASE_PATH, f'scout_metadata_{mode}.csv'), index=False)
            
            flash(f'✅ {full_name} sisteme başarıyla eklendi!', 'success')
            return redirect(url_for('index'))

        except Exception as e:
            flash(f'Hata: {str(e)}', 'error')
            return redirect(request.url)

    return render_template('add_player.html')

if __name__ == '__main__':
    app.run(debug=True, port=9000)
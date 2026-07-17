import streamlit as st
import pandas as pd
import traceback
import re
import numpy as np

# Setup Halaman
st.set_page_config(page_title="Dashboard Affiliate Open9", layout="wide")

# CSS Kustom
st.markdown("""
<style>
    .metric-card { background-color: #ffffff; border-radius: 10px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #f0f2f6; height: 100%; }
    .metric-title { font-size: 0.8rem; color: #7f8c8d; font-weight: 600; text-transform: uppercase; margin-bottom: 10px; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #2c3e50; }
    .text-green { color: #27ae60; font-weight: bold;}
    .text-red { color: #c0392b; font-weight: bold;}
    .badge-profit { background-color: #e8f8f5; color: #27ae60; padding: 3px 8px; border-radius: 15px; font-size: 0.7rem; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.sidebar.header("Upload File (Bisa pilih banyak file sekaligus)")
meta_files = st.sidebar.file_uploader("Meta Ads CSV (Opsional)", type=["csv"], accept_multiple_files=True)
tiktok_files = st.sidebar.file_uploader("TikTok Ads (Opsional)", type=["csv", "xlsx"], accept_multiple_files=True) 
click_files = st.sidebar.file_uploader("Shopee Click Report CSV (Wajib)", type=["csv"], accept_multiple_files=True)
commission_files = st.sidebar.file_uploader("Shopee Commission CSV (Wajib)", type=["csv"], accept_multiple_files=True)

st.markdown("### 📊 Laporan Harian", unsafe_allow_html=True)
st.write("---")

# 1. FUNGSI PEMBERSIH ANGKA
def clean_number(series):
    def parse_string_number(val):
        if pd.isnull(val): return 0.0
        if isinstance(val, (int, float)): return float(val)
        val = str(val).strip().upper().replace('RP', '').replace('IDR', '')
        if '.' in val and ',' in val:
            if val.rfind('.') > val.rfind(','): val = val.replace(',', '')
            else: val = val.replace('.', '').replace(',', '.')
        elif ',' in val:
            if len(val.split(',')[-1]) == 3: val = val.replace(',', '')
            else: val = val.replace(',', '.')
        elif '.' in val:
            if len(val.split('.')[-1]) == 3: val = val.replace('.', '')
        val = re.sub(r'[^\d.-]', '', val)
        try: return float(val)
        except: return 0.0
    return series.apply(parse_string_number)

# 2. FUNGSI PEMBERSIH KUNCI PENCARIAN (SYNC_KEY)
def clean_campaign_name(series):
    return series.astype(str).str.lower().str.replace(r'[^a-z0-9]', '', regex=True)

# 3. FUNGSI UNTUK MENDETEKSI NAMA KOLOM SECARA OTOMATIS
def find_column(df, possibilities):
    for p in possibilities:
        match = [col for col in df.columns if col.strip().lower() == p.strip().lower()]
        if match:
            return match[0]
    return None

# 4. FUNGSI UNTUK MEMBACA CSV DENGAN AUTO-DETEKSI SEPARATOR
def safe_read_csv(file_buffer):
    file_buffer.seek(0)
    try:
        df = pd.read_csv(file_buffer)
        if len(df.columns) <= 1:
            file_buffer.seek(0)
            df = pd.read_csv(file_buffer, sep=';')
    except:
        file_buffer.seek(0)
        df = pd.read_csv(file_buffer, sep=';')
    return df

# 5. FUNGSI UNTUK MEMBACA DAN MENGGABUNGKAN BANYAK FILE SEKALIGUS
def read_multiple_files(files):
    if not files:
        return None
    dfs = []
    for f in files:
        if f.name.endswith('.csv'):
            dfs.append(safe_read_csv(f))
        else:
            f.seek(0)
            dfs.append(pd.read_excel(f))
    return pd.concat(dfs, ignore_index=True)

# LOGIKA UTAMA
if (meta_files or tiktok_files) and click_files and commission_files:
    
    clicks = read_multiple_files(click_files)
    commission = read_multiple_files(commission_files)
    
    st.sidebar.success("Semua file berhasil dimuat & digabungkan!")

    # --- KONFIGURASI KOLOM SHOPEE ---
    SHP_CLICK_TAG_COL = 'Tag_link'
    SHP_COMM_TAG_COL = 'Tag_link1'
    SHP_COMM_ITEM_COL = 'Jumlah'
    SHP_COMM_TOTAL_COL = 'Komisi Bersih Affiliate (Rp)'
    # -------------------------

    try:
        ad_dfs = [] 

        # === PROSES META JIKA DIUPLOAD ===
        if meta_files:
            meta = read_multiple_files(meta_files)
            
            META_CAMP_COL = find_column(meta, ['Nama iklan', 'Ad name', 'Campaign name', 'Nama kampanye'])
            META_SPEND_COL = find_column(meta, ['Jumlah yang dibelanjakan (IDR)', 'Amount spent (IDR)', 'Amount spent', 'Spend'])
            META_CLICK_COL = find_column(meta, ['Klik tautan', 'Link clicks', 'Clicks'])
            
            if not META_CAMP_COL or not META_SPEND_COL:
                st.error("❌ Kolom nama iklan atau total spend tidak ditemukan di file Meta Ads. Periksa header file Anda.")
            else:
                meta = meta[~meta[META_CAMP_COL].astype(str).str.contains('Total|Jumlah', case=False, na=False)]
                meta = meta[meta[META_CAMP_COL].astype(str).str.strip() != '-'] 
                
                meta[META_SPEND_COL] = clean_number(meta[META_SPEND_COL])
                if META_CLICK_COL:
                    meta[META_CLICK_COL] = clean_number(meta[META_CLICK_COL])
                else:
                    meta['KLIK_DUMMY'] = 0
                    META_CLICK_COL = 'KLIK_DUMMY'
                    
                meta['SYNC_KEY'] = clean_campaign_name(meta[META_CAMP_COL])
                meta = meta[meta['SYNC_KEY'] != ''] 
                
                meta_agg = meta.groupby('SYNC_KEY').agg({
                    META_CAMP_COL: 'first', 
                    META_SPEND_COL: 'sum', 
                    META_CLICK_COL: 'sum'
                }).reset_index()
                
                meta_agg.rename(columns={META_CAMP_COL: 'NAMA KAMPANYE', META_SPEND_COL: 'SPEND ADS', META_CLICK_COL: 'KLIK ADS'}, inplace=True)
                meta_agg['PLATFORM'] = 'Meta Ads'
                ad_dfs.append(meta_agg)

        # === PROSES TIKTOK JIKA DIUPLOAD ===
        if tiktok_files:
            tiktok = read_multiple_files(tiktok_files)
                
            # PERBAIKAN: Deteksi kombinasi pintar untuk mengatasi beda format 'Nama Iklan' vs 'Nama Grup Iklan'
            camp_cols = [c for c in tiktok.columns if c.strip().lower() in ['nama iklan', 'nama grup iklan', 'ad group name', 'ad name', 'campaign name', 'nama kampanye']]
            if camp_cols:
                tiktok['NAMA_KAMPANYE_GABUNGAN'] = tiktok[camp_cols[0]]
                for col in camp_cols[1:]:
                    tiktok['NAMA_KAMPANYE_GABUNGAN'] = tiktok['NAMA_KAMPANYE_GABUNGAN'].fillna(tiktok[col])
                TT_CAMP_COL = 'NAMA_KAMPANYE_GABUNGAN'
            else:
                TT_CAMP_COL = None
                
            TT_SPEND_COL = find_column(tiktok, ['Cost', 'Biaya', 'Spend', 'Belanja'])
            TT_CLICK_COL = find_column(tiktok, ['Klik (destinasi)', 'Clicks (destination)', 'Clicks', 'Klik', 'Klik (tujuan)'])
            
            if not TT_CAMP_COL or not TT_SPEND_COL:
                st.error("❌ Kolom nama iklan/grup iklan atau Biaya tidak ditemukan di file TikTok Ads.")
            else:
                tiktok = tiktok[~tiktok[TT_CAMP_COL].astype(str).str.contains('Total|Jumlah', case=False, na=False)]
                tiktok = tiktok[tiktok[TT_CAMP_COL].astype(str).str.strip() != '-'] 
                
                tiktok[TT_SPEND_COL] = clean_number(tiktok[TT_SPEND_COL])
                if TT_CLICK_COL:
                    tiktok[TT_CLICK_COL] = clean_number(tiktok[TT_CLICK_COL])
                else:
                    tiktok['KLIK_DUMMY'] = 0
                    TT_CLICK_COL = 'KLIK_DUMMY'

                tiktok['SYNC_KEY'] = clean_campaign_name(tiktok[TT_CAMP_COL])
                tiktok = tiktok[tiktok['SYNC_KEY'] != ''] 
                
                tiktok_agg = tiktok.groupby('SYNC_KEY').agg({
                    TT_CAMP_COL: 'first', 
                    TT_SPEND_COL: 'sum', 
                    TT_CLICK_COL: 'sum'
                }).reset_index()
                
                tiktok_agg.rename(columns={TT_CAMP_COL: 'NAMA KAMPANYE', TT_SPEND_COL: 'SPEND ADS', TT_CLICK_COL: 'KLIK ADS'}, inplace=True)
                tiktok_agg['PLATFORM'] = 'TikTok Ads'
                ad_dfs.append(tiktok_agg)

        # Gabungkan data Iklan yang tersedia
        if ad_dfs:
            df_ads = pd.concat(ad_dfs, ignore_index=True)
            df_ads = df_ads.groupby('SYNC_KEY').agg({'NAMA KAMPANYE': 'first', 'PLATFORM': 'first', 'SPEND ADS': 'sum', 'KLIK ADS': 'sum'}).reset_index()
        else:
            df_ads = pd.DataFrame(columns=['SYNC_KEY', 'NAMA KAMPANYE', 'PLATFORM', 'SPEND ADS', 'KLIK ADS'])

        # Agregasi Shopee
        commission[SHP_COMM_ITEM_COL] = clean_number(commission[SHP_COMM_ITEM_COL])
        commission[SHP_COMM_TOTAL_COL] = clean_number(commission[SHP_COMM_TOTAL_COL])
        clicks['SYNC_KEY'] = clean_campaign_name(clicks[SHP_CLICK_TAG_COL])
        commission['SYNC_KEY'] = clean_campaign_name(commission[SHP_COMM_TAG_COL])

        clicks_agg = clicks.groupby('SYNC_KEY').size().reset_index(name='KLIK SHOPEE')
        
        comm_agg_komisi = commission.groupby('SYNC_KEY').agg({SHP_COMM_TOTAL_COL: 'sum'}).reset_index()
        comm_agg_komisi.rename(columns={SHP_COMM_TOTAL_COL: 'KOMISI'}, inplace=True)
        
        valid_sales = commission[commission[SHP_COMM_TOTAL_COL] > 0]
        comm_agg_item = valid_sales.groupby('SYNC_KEY').agg({SHP_COMM_ITEM_COL: 'sum'}).reset_index()
        comm_agg_item.rename(columns={SHP_COMM_ITEM_COL: 'TOTAL PENJUALAN'}, inplace=True)
        
        comm_agg = pd.merge(comm_agg_komisi, comm_agg_item, on='SYNC_KEY', how='left')

        # Base merge semua data
        all_sync_keys = pd.DataFrame({'SYNC_KEY': pd.concat([df_ads['SYNC_KEY'], clicks_agg['SYNC_KEY'], comm_agg['SYNC_KEY']]).dropna().unique()})
        df_final = pd.merge(all_sync_keys, df_ads, on='SYNC_KEY', how='left')
        df_final = pd.merge(df_final, clicks_agg, on='SYNC_KEY', how='left')
        df_final = pd.merge(df_final, comm_agg, on='SYNC_KEY', how='left')
        
        # Pengisian Data Kosong
        kolom_angka = ['SPEND ADS', 'KLIK ADS', 'KLIK SHOPEE', 'TOTAL PENJUALAN', 'KOMISI']
        for col in kolom_angka:
            if col not in df_final.columns:
                df_final[col] = 0
        df_final[kolom_angka] = df_final[kolom_angka].fillna(0)

        mask_empty_name = df_final['NAMA KAMPANYE'].isna()
        df_final.loc[mask_empty_name, 'NAMA KAMPANYE'] = df_final.loc[mask_empty_name, 'SYNC_KEY'].apply(lambda x: f"{str(x)}")
        
        mask_empty_platform = df_final['PLATFORM'].isna()
        df_final.loc[mask_empty_platform, 'PLATFORM'] = 'Organik / Lainnya'
        
        df_final['TAG'] = df_final['NAMA KAMPANYE'].apply(lambda x: x if str(x).startswith('#') else f"#{x}")

        # Hitung Metrik
        df_final['KEBOCORAN (%)'] = np.where(df_final['KLIK ADS'] > 0, ((df_final['KLIK ADS'] - df_final['KLIK SHOPEE']) / df_final['KLIK ADS'] * 100), 0)
        df_final['PROFIT/RUGI (Rp)'] = df_final['KOMISI'] - df_final['SPEND ADS']
        df_final['ROAS_NUM'] = np.where(df_final['SPEND ADS'] > 0, df_final['KOMISI'] / df_final['SPEND ADS'], 0)
        df_final['CPC (Rp)'] = np.where(df_final['KLIK ADS'] > 0, df_final['SPEND ADS'] / df_final['KLIK ADS'], 0)
        df_final['KONVERSI (%)'] = np.where(df_final['KLIK SHOPEE'] > 0, df_final['TOTAL PENJUALAN'] / df_final['KLIK SHOPEE'] * 100, 0)

        def get_status(row):
            if row['SPEND ADS'] <= 0: return "ORGANIK"
            if row['ROAS_NUM'] < 1: return "KILL"
            if row['ROAS_NUM'] >= 1.5: return "SCALE"
            return "MONITOR"
        df_final['STATUS'] = df_final.apply(get_status, axis=1)

        # Summary Metrics
        total_spend = df_final['SPEND ADS'].sum()
        total_komisi = df_final['KOMISI'].sum()
        total_item = df_final['TOTAL PENJUALAN'].sum()
        komisi_bersih = total_komisi - total_spend
        roas_global = total_komisi / total_spend if total_spend > 0 else 0
        total_klik_ads = df_final['KLIK ADS'].sum()
        total_klik_shopee = df_final['KLIK SHOPEE'].sum()
        kualitas_klik = (total_klik_shopee / total_klik_ads * 100) if total_klik_ads > 0 else 0

        # KARTU METRIK UI
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1: st.markdown(f'<div class="metric-card"><div class="metric-title">TOTAL SPEND ADS</div><div class="metric-value">Rp {total_spend:,.0f}</div></div>', unsafe_allow_html=True)
        with col2: st.markdown(f'<div class="metric-card"><div class="metric-title">KOMISI SHOPEE (GROSS)</div><div style="font-size: 0.7rem; color: #7f8c8d;">{int(total_item)} Item Valid Terjual</div><div class="metric-value">Rp {total_komisi:,.0f}</div></div>', unsafe_allow_html=True)
        warna_bersih = "text-green" if komisi_bersih > 0 else "text-red"
        tanda_bersih = "+" if komisi_bersih > 0 else ""
        with col3: st.markdown(f'<div class="metric-card"><div class="metric-title">KOMISI BERSIH (NET)</div><div style="font-size: 0.7rem; color: #7f8c8d;">Komisi - Spend Ads</div><div class="metric-value {warna_bersih}">{tanda_bersih}Rp {komisi_bersih:,.0f}</div></div>', unsafe_allow_html=True)
        with col4: st.markdown(f'<div class="metric-card"><div class="metric-title">ROAS KESELURUHAN</div><div class="metric-value {warna_bersih}" style="margin-bottom: 5px;">{roas_global:.2f}x</div><span class="badge-profit">{"Profit" if roas_global >= 1 else "Loss"}</span></div>', unsafe_allow_html=True)
        with col5: st.markdown(f'<div class="metric-card"><div class="metric-title">KUALITAS KLIK</div><div class="metric-value">{kualitas_klik:.1f}%</div><div style="font-size: 0.7rem; color: #7f8c8d; margin-top:5px;">Ads: {int(total_klik_ads)} &nbsp; | &nbsp; Shopee: {int(total_klik_shopee)}</div></div>', unsafe_allow_html=True)

        st.write("<br><br>", unsafe_allow_html=True)

        # TABEL UI
        st.markdown("#### 🎯 Data Per Kampanye")
        st.caption("KILL = ROAS<1 (rugi) | SCALE = ROAS>=1.5 (menguntungkan) | MONITOR = belum ada komisi atau ROAS 1–1.5 | ORGANIK = tanpa iklan.")
        
        df_tampil = df_final[['TAG', 'PLATFORM', 'SPEND ADS', 'KLIK ADS', 'KLIK SHOPEE', 'KEBOCORAN (%)', 'TOTAL PENJUALAN', 'KOMISI', 'PROFIT/RUGI (Rp)', 'ROAS_NUM', 'CPC (Rp)', 'KONVERSI (%)', 'STATUS']].copy()
        
        df_tampil.rename(columns={'SPEND ADS': 'SPEND ADS (Rp)', 'KOMISI': 'KOMISI (Rp)'}, inplace=True)
        
        df_tampil['ROAS'] = df_tampil['ROAS_NUM'].apply(lambda x: f"{x:.2f}x")
        df_tampil['KEBOCORAN (%)'] = df_tampil['KEBOCORAN (%)'].apply(lambda x: f"{x:.1f}%")
        df_tampil['KONVERSI (%)'] = df_tampil['KONVERSI (%)'].apply(lambda x: f"{x:.1f}%")
        df_tampil['CPC (Rp)'] = df_tampil['CPC (Rp)'].astype(int).apply(lambda x: f"Rp {x:,}")
        
        df_tampil['SPEND ADS (Rp)'] = df_tampil['SPEND ADS (Rp)'].apply(lambda x: f"Rp {x:,.0f}")
        df_tampil['KOMISI (Rp)'] = df_tampil['KOMISI (Rp)'].apply(lambda x: f"Rp {x:,.0f}")
        df_tampil['PROFIT/RUGI (Rp)'] = df_tampil['PROFIT/RUGI (Rp)'].apply(lambda x: f"Rp {x:,.0f}")
        df_tampil['KLIK ADS'] = df_tampil['KLIK ADS'].astype(int)
        df_tampil['KLIK SHOPEE'] = df_tampil['KLIK SHOPEE'].astype(int)
        df_tampil['TOTAL PENJUALAN'] = df_tampil['TOTAL PENJUALAN'].astype(int)

        df_tampil = df_tampil.drop(columns=['ROAS_NUM'])
        df_tampil = df_tampil[['TAG', 'PLATFORM', 'SPEND ADS (Rp)', 'KLIK ADS', 'KLIK SHOPEE', 'KEBOCORAN (%)', 'TOTAL PENJUALAN', 'KOMISI (Rp)', 'PROFIT/RUGI (Rp)', 'ROAS', 'CPC (Rp)', 'KONVERSI (%)', 'STATUS']]

        def color_status(val):
            if val == 'SCALE': return 'color: white; background-color: #27ae60; font-weight: bold; border-radius: 5px;'
            elif val == 'KILL': return 'color: white; background-color: #c0392b; font-weight: bold; border-radius: 5px;'
            elif val == 'MONITOR': return 'color: #f39c12; font-weight: bold;'
            elif val == 'ORGANIK': return 'color: #8e44ad; font-weight: bold;'
            return ''

        styled_df = df_tampil.style.map(color_status, subset=['STATUS']).map(lambda x: 'color: #c0392b; font-weight: bold;', subset=['KEBOCORAN (%)'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Error tidak terduga: {str(e)}")
        st.code(traceback.format_exc())

else:
    st.info("👈 Silakan upload minimal 1 file Ads (Meta/TikTok) DAN ke-2 file Shopee di panel kiri.")

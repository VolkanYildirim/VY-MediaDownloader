import sys
import os
import threading
import queue
import subprocess
import time

# Güvenli kütüphane importları
try:
    import customtkinter as ctk
    from customtkinter import filedialog
    import yt_dlp
    from colorama import init, Fore
except ImportError as e:
    print(f"KRİTİK HATA: Gerekli kütüphaneler eksik! Hata: {e}")
    sys.exit(1)

init(autoreset=True)

# Arayüz Teması
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# --- DİZİN VE YOL YÖNETİMİ (Program Files/User-Space Uyumluluğu) ---
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# YENİ İKON ADI ENTEGRE EDİLDİ
ICON_PATH = os.path.join(APP_DIR, "vy_logo.ico")
FFMPEG_PATH = os.path.join(APP_DIR, "ffmpeg.exe") if sys.platform == "win32" else "ffmpeg"


class SecureStreamApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Kurumsal Başlık
        self.title("VY Media Downloader (Pro Edition)")
        self.geometry("950x750")

        # --- YENİ LOGO ENTEGRASYONU (Ana Pencere) ---
        if os.path.exists(ICON_PATH):
            try:
                self.iconbitmap(ICON_PATH)
            except Exception as e:
                print(f"Uyarı: Simge yüklenemedi. Hata: {str(e)}")

        self.log_queue = queue.Queue()
        self.download_thread = None
        
        # Güvenli Kayıt Dizini (C:\Users\KullaniciAdi\Downloads)
        self.save_path = os.path.join(os.path.expanduser("~"), "Downloads")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(7, weight=1) 

        # --- 0. ÜST BAR (Başlık ve Hakkında) ---
        self.frame_top = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_top.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        self.label_title = ctk.CTkLabel(self.frame_top, text="VY Media Downloader", font=ctk.CTkFont(size=24, weight="bold"))
        self.label_title.pack(side="left")

        # Önce Hakkında butonu (En sağda durması için)
        self.btn_about = ctk.CTkButton(self.frame_top, text="Hakkında", width=80, command=self.show_about)
        self.btn_about.pack(side="right", padx=(10, 0))
        
        # Yanına Sürüm Geçmişi butonu eklendi
        self.btn_changelog = ctk.CTkButton(self.frame_top, text="Sürüm Geçmişi", width=110, fg_color="#333333", hover_color="#555555", command=self.show_changelog)
        self.btn_changelog.pack(side="right")

        # --- 1. LİNK GİRİŞİ ---
        self.entry_url = ctk.CTkEntry(self, placeholder_text="YouTube Müzik veya Video linki yapıştırın...", height=45)
        self.entry_url.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        # --- 2. AYARLAR PANELİ ---
        self.frame_settings = ctk.CTkFrame(self)
        self.frame_settings.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.frame_settings.grid_columnconfigure(3, weight=1)

        # 2.1 Format Seçici (Satır 0)
        self.label_format = ctk.CTkLabel(self.frame_settings, text="Format:", font=ctk.CTkFont(weight="bold"))
        self.label_format.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.format_var = ctk.StringVar(value="Audio")
        self.radio_audio = ctk.CTkRadioButton(self.frame_settings, text="Ses (MP3)", variable=self.format_var, value="Audio", command=self.update_quality_options)
        self.radio_audio.grid(row=0, column=1, padx=5, pady=10)
        
        self.radio_video = ctk.CTkRadioButton(self.frame_settings, text="Video (MP4)", variable=self.format_var, value="Video", command=self.update_quality_options)
        self.radio_video.grid(row=0, column=2, padx=5, pady=10)

        # 2.2 Kalite Seçici (Satır 0)
        self.label_quality = ctk.CTkLabel(self.frame_settings, text="Kalite:", font=ctk.CTkFont(weight="bold"))
        self.label_quality.grid(row=0, column=3, padx=(20, 5), pady=10, sticky="e")
        
        self.combo_quality = ctk.CTkComboBox(self.frame_settings, values=["320 kbps", "256 kbps", "192 kbps", "128 kbps"])
        self.combo_quality.grid(row=0, column=4, padx=5, pady=10)
        self.combo_quality.set("320 kbps") 

        # 2.3 Klasör Seçici (Satır 0)
        self.btn_folder = ctk.CTkButton(self.frame_settings, text="Klasör Seç", command=self.choose_directory, width=100)
        self.btn_folder.grid(row=0, column=5, padx=10, pady=10)
        
        # 2.4 Klasör Yolu Etiketi (Satır 1 - Alta Kaydırıldı)
        self.label_folder = ctk.CTkLabel(self.frame_settings, text=f"Hedef: {self.save_path}", text_color="gray")
        self.label_folder.grid(row=1, column=0, columnspan=6, padx=10, pady=(0, 5), sticky="w")

        # 2.5 Tarayıcı Seçici (Satır 2) - Baş harfler büyütüldü
        self.label_browser = ctk.CTkLabel(self.frame_settings, text="Tarayıcı (Oturum):", font=ctk.CTkFont(weight="bold"))
        self.label_browser.grid(row=2, column=0, padx=(10, 5), pady=(5, 0), sticky="w")

        self.combo_browser = ctk.CTkComboBox(self.frame_settings, values=["Yok (Anonim)", "Chrome", "Edge", "Firefox", "Brave", "Opera"])
        self.combo_browser.grid(row=2, column=1, columnspan=2, padx=5, pady=(5, 0), sticky="w")
        self.combo_browser.set("Yok (Anonim)") # Varsayılanı güvenli/sorunsuz mod yaptık
        
        # 2.6 UX Uyarısı (Satır 3)
        self.label_browser_info = ctk.CTkLabel(self.frame_settings, text="*Gizli listeler veya yaş kısıtlamalı içeriklerde, seçili tarayıcıda YouTube oturumu açık olmalıdır.", font=ctk.CTkFont(size=11, slant="italic"), text_color="gray")
        self.label_browser_info.grid(row=3, column=0, columnspan=6, padx=10, pady=(0, 10), sticky="w")

        # --- 3. İNDİRME BUTONU ---
        self.btn_download = ctk.CTkButton(self, text="İNDİRMEYİ BAŞLAT", height=45, font=ctk.CTkFont(size=16, weight="bold"), command=self.start_download_thread)
        self.btn_download.grid(row=3, column=0, padx=20, pady=15, sticky="ew")

        # --- 4. YÜKLEME BARI VE YÜZDE ---
        self.progress_bar = ctk.CTkProgressBar(self, mode="determinate")
        self.progress_bar.grid(row=4, column=0, padx=20, pady=5, sticky="ew")
        self.progress_bar.set(0)

        self.label_percent = ctk.CTkLabel(self, text="%0", font=ctk.CTkFont(size=12))
        self.label_percent.grid(row=5, column=0, pady=0)

        # --- 5. LOG ALANI ---
        self.txt_logs = ctk.CTkTextbox(self, height=250, font=ctk.CTkFont(size=12))
        self.txt_logs.grid(row=6, column=0, padx=20, pady=(5, 20), sticky="nsew")
        self.txt_logs.configure(state="disabled")

        self.check_core_update_silent()
        self.check_queue()

        # --- ANA EKRANI GİZLE VE GÜVENLİK DUVARINI BAŞLAT ---
        self.withdraw() 
        self.show_vpn_gatekeeper()

    # --- STARTUP GATEKEEPER (AÇILIŞ GÜVENLİK DUVARI) ---
    def show_vpn_gatekeeper(self):
        self.gate_window = ctk.CTkToplevel(self)
        self.gate_window.title("Sistem Güvenlik Kontrolü")
        self.gate_window.geometry("450x230")
        self.gate_window.resizable(False, False)
        self.gate_window.attributes("-topmost", True) # Her zaman en üstte tut
        self.gate_window.protocol("WM_DELETE_WINDOW", self.exit_app) # Çarpıya basarsa komple kapat
        
        if os.path.exists(ICON_PATH):
            self.gate_window.after(10, lambda: self.gate_window.iconbitmap(ICON_PATH))

        lbl_warn = ctk.CTkLabel(self.gate_window, text="⚠️ AĞ BAĞLANTISI KONTROLÜ", font=ctk.CTkFont(weight="bold", size=18), text_color="#FFCC00")
        lbl_warn.pack(pady=(20, 10))

        lbl_desc = ctk.CTkLabel(self.gate_window, text="YouTube güvenlik algoritmaları, VPN trafiğini\nengellemektedir. Sorunsuz bir indirme yapabilmek için\nVPN bağlantınızın KAPALI olması gerekmektedir.\n\nŞu anda VPN kapalı mı?", justify="center", font=ctk.CTkFont(size=13))
        lbl_desc.pack(pady=(0, 20))

        btn_frame = ctk.CTkFrame(self.gate_window, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20)
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        btn_yes = ctk.CTkButton(btn_frame, text="EVET (VPN Kapalı)", height=40, fg_color="green", hover_color="darkgreen", font=ctk.CTkFont(weight="bold"), command=self.unlock_app)
        btn_yes.grid(row=0, column=0, padx=10, sticky="ew")

        btn_no = ctk.CTkButton(btn_frame, text="HAYIR (VPN Açık)", height=40, fg_color="darkred", hover_color="#8B0000", font=ctk.CTkFont(weight="bold"), command=self.reject_app)
        btn_no.grid(row=0, column=1, padx=10, sticky="ew")

    def unlock_app(self):
        """Kullanıcı VPN kapalı derse, duvarı yıkıp ana programı gösterir."""
        self.gate_window.destroy()
        self.deiconify() 

    def reject_app(self):
        """Kullanıcı VPN açık derse, ekranı kırmızı bir uyarıya çevirir."""
        for widget in self.gate_window.winfo_children():
            widget.destroy()

        lbl_rej = ctk.CTkLabel(self.gate_window, text="❌ ERİŞİM REDDEDİLDİ", font=ctk.CTkFont(weight="bold", size=20), text_color="red")
        lbl_rej.pack(pady=(40, 10))
        
        lbl_desc = ctk.CTkLabel(self.gate_window, text="Lütfen arka planda çalışan VPN bağlantınızı\nkapatıp programı yeniden başlatın.", font=ctk.CTkFont(size=14))
        lbl_desc.pack()
        
        btn_exit = ctk.CTkButton(self.gate_window, text="PROGRAMI KAPAT", fg_color="transparent", border_width=1, command=self.exit_app)
        btn_exit.pack(pady=20)

    def exit_app(self):
        """Sistemi tamamen kapatır."""
        self.destroy()
        sys.exit(0)

    # --- SÜRÜM GEÇMİŞİ (CHANGELOG) EKRANI ---
    def show_changelog(self):
        log_window = ctk.CTkToplevel(self)
        log_window.title("Sürüm Geçmişi")
        log_window.geometry("600x450")
        log_window.resizable(False, False)
        log_window.attributes("-topmost", True)
        
        if os.path.exists(ICON_PATH):
            log_window.after(10, lambda: log_window.iconbitmap(ICON_PATH))

        txt_log = ctk.CTkTextbox(log_window, width=560, height=410, font=ctk.CTkFont(size=13), wrap="word")
        txt_log.pack(padx=20, pady=20)

        changelog_text = """ VY Media Downloader - Sürüm Geçmişi

--------------------------------------------------
v2.0.0 (Gelişmiş Güvenlik ve Otonomi Güncellemesi)
--------------------------------------------------
# Otonom Gatekeeper: VPN ve WAF (Güvenlik Duvarı) çakışmalarını önlemek için program açılışına akıllı bir ağ kontrol modülü entegre edildi.

# Dinamik Oturum Yönetimi: Gizli ve liste dışı oynatma listelerine erişebilmek için yerel tarayıcı (Chrome, Edge, Firefox vb.) çerez entegrasyonu sağlandı.

# Premium Paradoksu (DRM) Çözümü: Şifrelenmiş (DRM) Premium içeriklerde çökme yaşanmaması için "Sessiz Fallback" algoritması geliştirildi. Motor, engelleri otonom olarak aşar.

# Otonom URL Temizleme: 'music.youtube.com' uzantılı linkler, DRM kilitlerini atlatmak amacıyla arka planda otomatik olarak standart yapıya dönüştürülür.

# Akıllı İç Casus (Logger): Motor hataları terminalden izole edilerek, kullanıcıya anında ve doğru geri bildirim (VPN/Gizlilik uyarıları) veren yerleşik olay dinleyicisi eklendi.

# Arayüz İyileştirmeleri: Yeni tarayıcı seçim menüsü eklendi, bilgi ekranları ve grid (ızgara) yapıları modernize edildi.

--------------------------------------------------
v1.0.0 (İlk Sürüm - Çekirdek İnşası)
--------------------------------------------------
# Privacy-First Mimarisi: Hiçbir kullanıcı verisi toplamayan ve dışarıya telemetri göndermeyen "Sıfır İz" yapısı kuruldu.

# Çekirdek Motor: Güvenli indirme işlemleri için açık kaynaklı yt-dlp API'si entegre edildi.

# Yerel Format Dönüştürme: FFmpeg entegrasyonu ile indirilen medyalar bilgisayarınızda işlenip veri kaybı olmadan dönüştürüldü.

# Dinamik Kalite Seçimi: Ses (MP3) ve Video (MP4) için detaylı çözünürlük ve bitrate seçim altyapısı oluşturuldu.

# Otonom Motor Güncelleyici: YouTube algoritmalarına karşı çekirdek motoru her açılışta sessizce kontrol edip güncelleyen modül yazıldı.
"""
        txt_log.insert("0.0", changelog_text)
        txt_log.configure(state="disabled")

    # --- HAKKINDA PENCERESİ ---
    def show_about(self):
        about_window = ctk.CTkToplevel(self)
        about_window.title("Hakkında")
        about_window.geometry("400x250")
        about_window.resizable(False, False)
        about_window.attributes("-topmost", True)

        if os.path.exists(ICON_PATH):
            about_window.after(10, lambda: about_window.iconbitmap(ICON_PATH))

        about_window.transient(self)
        about_window.grab_set()

        lbl_title = ctk.CTkLabel(about_window, text="VY Media Downloader", font=ctk.CTkFont(size=18, weight="bold"))
        lbl_title.pack(pady=(20, 5))

        lbl_version = ctk.CTkLabel(about_window, text="Version 2.0 (Pro Edition)", font=ctk.CTkFont(size=12), text_color="gray")
        lbl_version.pack(pady=(0, 15))

        desc = ("Bu yazılım; dijital mahremiyet (Privacy-First) ilkeleri\n"
                "gözetilerek, tamamen açık kaynaklı altyapılar kullanılarak\n"
                "geliştirilmiştir. Hiçbir kullanıcı verisi veya telemetri\n"
                "toplamaz ve dışarıya aktarmaz.\n\n"
                "🛡️ Developed by Volkan YILDIRIM - Proctives\n"
                "www.volkanyildirim.com.tr")
        
        lbl_desc = ctk.CTkLabel(about_window, text=desc, justify="center", font=ctk.CTkFont(size=12))
        lbl_desc.pack(padx=20, pady=5)

    def update_quality_options(self):
        selected_format = self.format_var.get()
        if selected_format == "Audio":
            self.combo_quality.configure(values=["320 kbps", "256 kbps", "192 kbps", "128 kbps"])
            self.combo_quality.set("320 kbps")
        else:
            self.combo_quality.configure(values=["4K (2160p)", "2K (1440p)", "1080p", "720p", "480p", "360p"])
            self.combo_quality.set("1080p")

    def choose_directory(self):
        selected_dir = filedialog.askdirectory(title="Müziklerin Kaydedileceği Klasörü Seçin")
        if selected_dir:
            if os.access(selected_dir, os.W_OK):
                self.save_path = selected_dir
                display_path = self.save_path if len(self.save_path) < 70 else "..." + self.save_path[-67:]
                self.label_folder.configure(text=f"Hedef: {display_path}")
            else:
                self.log_to_gui("HATA: Seçilen klasöre yazma yetkiniz bulunmuyor! Yönetici izni gerekebilir.", msg_type="log")

    def log_to_gui(self, data, msg_type="log"):
        self.log_queue.put((msg_type, data))

    def check_queue(self):
        while True:
            try:
                msg_type, data = self.log_queue.get_nowait()
                if msg_type == "log":
                    self.txt_logs.configure(state="normal")
                    self.txt_logs.insert("end", f"[*] {data}\n")
                    self.txt_logs.see("end")
                    self.txt_logs.configure(state="disabled")
                elif msg_type == "progress":
                    self.progress_bar.set(data)
                    self.label_percent.configure(text=f"%{int(data * 100)}")
            except queue.Empty:
                break
        self.after(100, self.check_queue) 

    def check_core_update_silent(self):
        threading.Thread(target=self._update_core_worker, daemon=True).start()

    def _update_core_worker(self):
        self.log_to_gui("Sistem Başlatılıyor: Çekirdek motor (yt-dlp) güncelliği denetleniyor...")
        try:
            result = subprocess.run(["python", "-m", "pip", "install", "--upgrade", "yt-dlp"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if "Successfully installed" in result.stdout:
                self.log_to_gui("Çekirdek motor güncellendi! Algoritmalar senkronize edildi.")
            else:
                self.log_to_gui("Çekirdek motor zaten güncel. Güvenli bağlantı hazır.")
        except Exception:
            self.log_to_gui("Çevrimdışı mod veya motor kontrolü atlandı. Bağlantı hazır.")

    def start_download_thread(self):
        url = self.entry_url.get().strip()
        
        # --- OTONOM LİNK OPTİMİZASYONU ---
        if "music.youtube.com" in url:
            url = url.replace("music.youtube.com", "www.youtube.com")
            
        if not url or ("youtube.com" not in url and "youtu.be" not in url):
            self.log_to_gui("Lütfen geçerli bir YouTube Music/Video linki yapıştırın.")
            return

        if not os.path.exists(FFMPEG_PATH):
            self.log_to_gui(f"KRİTİK HATA: ffmpeg.exe bulunamadı! Aranan Dizin: {FFMPEG_PATH}")
            return

        self.btn_download.configure(state="disabled", text="İNDİRİLİYOR...")
        self.progress_bar.set(0)
        self.label_percent.configure(text="%0")
        
        format_type = self.format_var.get()
        raw_quality = self.combo_quality.get()
        
        # Kalite ayrıştırma
        if format_type == "Audio":
            quality_val = raw_quality.replace(" kbps", "")
        else:
            if "4K" in raw_quality: quality_val = "2160"
            elif "2K" in raw_quality: quality_val = "1440"
            else: quality_val = raw_quality.replace("p", "")
        
        # Tarayıcı seçimini okuma
        browser_choice = self.combo_browser.get()
        
        # Thread başlatma
        self.download_thread = threading.Thread(target=self._download_worker, args=(url, format_type, quality_val, raw_quality, self.save_path, browser_choice), daemon=True)
        self.download_thread.start()

    def _download_worker(self, url, format_type, quality, display_quality, path, browser_choice):
        self.log_to_gui("-" * 50)
        self.log_to_gui(f"Veri akışı başlatıldı. Tür: {format_type} | Kalite: {display_quality} | Oturum: {browser_choice} | Hedef: {path}")
        
        ffmpeg_location = APP_DIR

        # --- PREMIUM PARADOKSU İÇİN SESSİZ FALLBACK DÖNGÜSÜ ---
        for attempt in range(2):
            spy_status = {"vpn_block": False, "private_block": False, "drm_block": False}
            
            class ytLogger:
                def debug(self, msg): pass
                def warning(self, msg): pass
                def error(self, msg):
                    msg_lower = msg.lower()
                    if "sign in to confirm" in msg_lower or "bot" in msg_lower or "http error 403" in msg_lower:
                        spy_status["vpn_block"] = True
                    elif "requested format is not available" in msg_lower:
                        spy_status["drm_block"] = True
                    elif "video unavailable" in msg_lower or "private video" in msg_lower:
                        spy_status["private_block"] = True

            if format_type == "Audio":
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(path, '%(playlist_title|Müzikler)s', '%(artist,uploader)s - %(track,title)s.%(ext)s'),
                    'ffmpeg_location': ffmpeg_location,
                    'writethumbnail': True, 
                    'postprocessors': [
                        {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': quality},
                        {'key': 'FFmpegThumbnailsConvertor', 'format': 'png'},
                        {'key': 'EmbedThumbnail'}
                    ],
                    'postprocessor_args': {
                        'thumbnailsconvertor+ffmpeg_o': ['-vf', "crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'"]
                    }
                }
            else:
                ydl_opts = {
                    'format': f'bestvideo[height<={quality}]+bestaudio/best',
                    'merge_output_format': 'mp4',
                    'outtmpl': os.path.join(path, '%(playlist_title|Videolar)s', '%(uploader)s - %(title)s.%(ext)s'),
                    'ffmpeg_location': ffmpeg_location,
                    'postprocessors': [{'key': 'EmbedThumbnail'}], 
                }

            ydl_opts.update({
                'ignoreerrors': True,
                'writethumbnail': True, 
                'quiet': True, 
                'no_warnings': True,
                'extract_flat': False, 
                'progress_hooks': [self._progress_hook],
                'logger': ytLogger()
            })

            if attempt == 0 and browser_choice != "Yok (Anonim)":
                ydl_opts['cookiesfrombrowser'] = (browser_choice.lower(), )

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    if spy_status["drm_block"] and attempt == 0 and browser_choice != "Yok (Anonim)":
                        continue 
                    
                    if spy_status["vpn_block"]:
                        self.log_to_gui("\n[X] BAĞLANTI REDDEDİLDİ: YouTube güvenlik duvarına (Bot Koruması) takıldınız!")
                        self.log_to_gui("-> Lütfen arka planda çalışan VPN'in GERÇEKTEN KAPALI olduğundan emin olun.")
                        break
                    elif spy_status["private_block"]:
                        self.log_to_gui("\n[X] İÇERİK REDDEDİLDİ: Bu video gizli, silinmiş veya telifli.")
                        self.log_to_gui("-> Gizli bir listeniz ise Tarayıcı (Oturum) seçtiğinizden emin olun.")
                        break
                    elif spy_status["drm_block"]:
                        self.log_to_gui("\n[X] İŞLEM BAŞARISIZ: Bu video desteklenen bir formata (Örn: MP3) dönüştürülemiyor.")
                        break
                    else:
                        self.log_to_gui("\n[+] OPERASYON BAŞARIYLA TAMAMLANDI!")
                        break 

            except Exception as e:
                self.log_to_gui(f"\n[X] Kritik Sistem Hatası: {str(e)}")
                break 

        self.after(100, self._reset_gui)

    def _progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            if total and total > 0:
                percent = downloaded / total
                self.log_to_gui(percent, msg_type="progress")
                
        elif d['status'] == 'finished':
            self.log_to_gui("Veri çekildi, FFmpeg ile kodlama (Encoding) ve kapak gömme işlemi yapılıyor...")

    def _reset_gui(self):
        self.btn_download.configure(state="normal", text="İNDİRMEYİ BAŞLAT")
        self.progress_bar.set(1)
        self.label_percent.configure(text="%100")

if __name__ == "__main__":
    app = SecureStreamApp()
    app.mainloop()
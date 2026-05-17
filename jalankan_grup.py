from camoufox import Camoufox
import sys
import os
import re
import time
import logging
from datetime import datetime
import signal

# ============================================================
# KONFIGURASI
# ============================================================
LEBAR_JENDELA = int(os.environ.get('BROWSER_WIDTH', 1200))
TINGGI_JENDELA = int(os.environ.get('BROWSER_HEIGHT', 700))
LOG_DIR = "logs"
SENSITIVE_DOMAINS = ['accounts.google.com', 'mail.google.com', 'myaccount.google.com']

# Mencegah traceback panjang Playwright saat Ctrl+C
signal.signal(signal.SIGINT, signal.SIG_DFL)

def validate_group_name(nama_grup):
    """Validasi nama grup untuk mencegah path traversal."""
    if not re.match(r'^[a-zA-Z0-9_-]+$', nama_grup):
        raise ValueError(f"Nama grup tidak valid: {nama_grup}")
    if nama_grup.startswith(('.', '-')):
        raise ValueError("Nama grup tidak boleh dimulai dengan '.' atau '-'")
    return nama_grup

def setup_logger(nama_grup):
    """Setup logger: file (lengkap, append per hari) + console (minimal)."""
    os.makedirs(LOG_DIR, exist_ok=True)
    
    tanggal = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(LOG_DIR, f"{tanggal}_{nama_grup}.log")
    
    # Unique logger name per invocation
    logger = logging.getLogger(f"camoufox_{nama_grup}_{os.getpid()}")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_fmt)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_fmt = logging.Formatter(fmt="%(message)s")
    console_handler.setFormatter(console_fmt)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger, log_file

def is_sensitive_url(url):
    """Check apakah URL mengandung sensitive domain."""
    return any(domain in url for domain in SENSITIVE_DOMAINS)

def tulis_header_log(logger, nama_grup, log_file):
    """Tulis header START sesi ke file log."""
    garis = "=" * 60
    logger.debug("")
    logger.debug(garis)
    logger.debug(f"  SESI DIMULAI — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.debug(garis)
    logger.debug(f"Profil       : {nama_grup}")
    logger.debug(f"File log     : {log_file}")
    logger.debug(f"Ukuran window: {LEBAR_JENDELA}x{TINGGI_JENDELA}")
    logger.debug(f"Platform     : {sys.platform}")
    logger.debug(f"Python       : {sys.version}")
    logger.debug(garis)

def tulis_footer_log(logger, waktu_mulai):
    """Tulis footer END sesi ke file log."""
    durasi = time.time() - waktu_mulai
    menit, detik = divmod(int(durasi), 60)
    garis = "=" * 60
    logger.debug(garis)
    logger.debug(f"  SESI SELESAI — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Durasi: {menit}m {detik}s")
    logger.debug(garis)
    logger.debug("")

def pasang_pemantau_navigasi(browser, logger):
    """Pasang event listener di semua tab untuk mencatat aktivitas browsing."""
    def pantau_page(page):
        def on_navigasi(frame):
            if frame == page.main_frame:
                url = frame.url
                if url and url != "about:blank":
                    if is_sensitive_url(url):
                        logger.debug("[NAVIGASI] [REDACTED - Sensitive URL]")
                    else:
                        logger.debug(f"[NAVIGASI] {url}")
        
        def on_load():
            title = ""
            try:
                title = page.title()
            except Exception:
                pass
            logger.debug(f"[LOADED]   Judul: \"{title}\"")
        
        def on_download(download):
            logger.debug(f"[DOWNLOAD] {download.suggested_filename} dari {download.url}")
        
        def on_popup(popup):
            logger.debug(f"[TAB BARU] Popup dibuka: {popup.url}")
            pantau_page(popup)
        
        def on_page_error(error):
            logger.debug(f"[WEB ERR]  {error}")
        
        page.on("framenavigated", on_navigasi)
        page.on("load", on_load)
        page.on("download", on_download)
        page.on("popup", on_popup)
        page.on("pageerror", on_page_error)
    
    for page in browser.pages:
        pantau_page(page)
        logger.debug(f"Pemantau dipasang di tab: {page.url or 'about:blank'}")
    
    def on_page_baru(page):
        logger.debug(f"[TAB BARU] Tab baru dibuka.")
        pantau_page(page)
    
    def on_page_tutup(page):
        logger.debug(f"[TAB TUTUP] Tab ditutup: {page.url}")
    
    browser.on("page", on_page_baru)
    browser.on("close", lambda: logger.debug("[BROWSER]  Browser ditutup oleh pengguna."))

def main():
    if len(sys.argv) < 2:
        print("Penggunaan: python jalankan_grup.py <nama_grup>")
        print("Contoh    : python jalankan_grup.py Grup_1")
        sys.exit(1)

    try:
        nama_grup = validate_group_name(sys.argv[1])
    except ValueError as e:
        print(f"[!] ERROR: {e}")
        sys.exit(1)

    waktu_mulai = time.time()
    logger, log_file = setup_logger(nama_grup)
    tulis_header_log(logger, nama_grup, log_file)
    
    print(f"[*] Membuka profil '{nama_grup}'...")
    print(f"[i] Log lengkap: {log_file}")
    print()
    
    logger.debug("Memulai proses buka Camoufox...")

    try:
        with Camoufox(
            user_data_dir=nama_grup,
            persistent_context=True,
            headless=False,
            window=(LEBAR_JENDELA, TINGGI_JENDELA)
        ) as browser:
            logger.debug("Browser Camoufox berhasil dibuka.")
            logger.debug(f"Tab aktif: {len(browser.pages)} tab terbuka.")
            
            pasang_pemantau_navigasi(browser, logger)
            logger.debug("Pemantau navigasi & aktivitas web aktif.")
            
            page = browser.pages[0] if browser.pages else browser.new_page()
            
            logger.debug("Navigasi awal ke whatismyipaddress.com...")
            page.goto('https://whatismyipaddress.com/')
            
            try:
                info = page.evaluate("""() => ({
                    innerW: window.innerWidth,
                    innerH: window.innerHeight,
                    outerW: window.outerWidth,
                    outerH: window.outerHeight,
                    screenW: screen.width,
                    screenH: screen.height,
                    dpr: window.devicePixelRatio,
                    ua: navigator.userAgent
                })""")
                
                logger.debug("-" * 60)
                logger.debug("INFO BROWSER (dilihat oleh website):")
                logger.debug(f"  window.inner : {info['innerW']}x{info['innerH']}")
                logger.debug(f"  window.outer : {info['outerW']}x{info['outerH']}")
                logger.debug(f"  screen       : {info['screenW']}x{info['screenH']}")
                logger.debug(f"  devicePixelRatio: {info['dpr']}")
                logger.debug(f"  userAgent    : {info['ua']}")
                logger.debug("-" * 60)
            except Exception as e:
                logger.warning(f"Gagal ambil info browser: {e}")
            
            print("[+] Browser terbuka! Silakan gunakan browser.")
            print("[!] Tutup jendela browser jika sudah selesai.")
            print()
            
            logger.debug("Menunggu pengguna menutup browser...")
            
            try:
                # Menggunakan event-based wait
                if hasattr(browser, 'contexts') and len(browser.contexts) > 0:
                    browser.contexts[0].wait_for_event('close')
                else:
                    page.wait_for_timeout(999999999)
            except Exception as e:
                logger.debug(f"Browser ditutup. Detail: {e}")
    
    except Exception as e:
        logger.error(f"ERROR tidak terduga: {e}", exc_info=True)
        print(f"[!] ERROR: {e}")
        print(f"[i] Lihat log untuk detail: {log_file}")
    
    finally:
        tulis_footer_log(logger, waktu_mulai)
        print(f"[*] Selesai. Log tersimpan di: {log_file}")

if __name__ == "__main__":
    main()

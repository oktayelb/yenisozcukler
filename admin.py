import tkinter as tk
from tkinter import ttk, messagebox
from flask_sqlalchemy import SQLAlchemy
from flask import Flask 
from datetime import datetime
from sqlalchemy import or_ # Sadece tek bir satırda

# --- VERİTABANI VE MODEL TANIMLARI ---
# Flask uygulaması olmadan SQLAlchemy'yi kullanmak için gerekli boilerplate
app = Flask(__name__)
# SQLite dosyasının yolunu tanımla
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sozluk.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app) 

# Word Modelinin admin.py'de de aynı şekilde tanımlanması GEREKLİDİR.
class Word(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(50), nullable=False)
    definition = db.Column(db.String(300), nullable=False)
    author = db.Column(db.String(20), default='Anonymous')
    likes = db.Column(db.Integer, default=0)
    # Status: 'pending' (beklemede) veya 'approved' (onaylanmış)
    status = db.Column(db.String(10), default='pending') 
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Word {self.id}: {self.word} | Status: {self.status}>"
    
# --- ANA YÖNETİM UYGULAMASI ---
class AdminApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sözlük Yönetim Paneli (SQLite DB)")
        self.root.geometry("800x700") # Boyut artırıldı
        
        # Flask Application Context'i manuel olarak oluştur
        self.app_context = app.app_context()
        self.app_context.push()
        
        # Tüm veriyi depolamak için tek bir liste kullanacağız
        self.all_words = [] 
        self.load_words()

        # GUI Setup
        self.setup_ui()

    def load_words(self):
        # Tüm sözcükleri (pending ve approved) veritabanından çeker
        self.all_words = Word.query.order_by(Word.timestamp.desc()).all()
        
        # Her objeye geçici 'action' özniteliği ekle (approved olanlar için delete, pending olanlar için approve/reject)
        for word in self.all_words:
            word.action = 'none' 
            word.ui_ref = None

    def setup_ui(self):
        # Notebook (Sekmeli Görünüm) oluşturulması
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(pady=10, padx=10, fill="both", expand=True)

        # Sekme 1: Pending Submissions (Onay Bekleyenler)
        self.pending_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.pending_frame, text='Onay Bekleyenler')
        self.setup_pending_tab(self.pending_frame)

        # Sekme 2: All Words (Tüm Sözcükler)
        self.all_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.all_frame, text='Tüm Sözcükler')
        self.setup_all_tab(self.all_frame)
        
        # Bottom Action Bar
        action_bar = tk.Frame(self.root, bg="#bdc3c7", height=50)
        action_bar.pack(fill="x", side="bottom")
        
        btn_save = tk.Button(action_bar, text="Değişiklikleri Uygula ve Çık", bg="#27ae60", fg="white", 
                             font=("Segoe UI", 10, "bold"), padx=20, pady=10,
                             command=self.on_close)
        btn_save.pack(pady=10, padx=10, side='right')
        
        btn_refresh = tk.Button(action_bar, text="Yenile", bg="#3498db", fg="white", 
                             font=("Segoe UI", 10, "bold"), padx=20, pady=10,
                             command=self.refresh_ui)
        btn_refresh.pack(pady=10, padx=10, side='left')

        self.refresh_ui_title()
        
    def refresh_ui_title(self):
        pending_count = sum(1 for w in self.all_words if w.status == 'pending')
        all_count = sum(1 for w in self.all_words if w.status == 'approved')
        self.notebook.tab(0, text=f'Onay Bekleyenler ({pending_count})')
        self.notebook.tab(1, text=f'Tüm Sözcükler ({all_count})')


    def setup_pending_tab(self, parent):
        # Scrollable Area for pending items
        self.pending_canvas = tk.Canvas(parent, bg="#ecf0f1")
        self.pending_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.pending_canvas.yview)
        self.pending_scrollable_frame = tk.Frame(self.pending_canvas, bg="#ecf0f1")

        self.pending_scrollable_frame.bind("<Configure>", lambda e: self.pending_canvas.configure(scrollregion=self.pending_canvas.bbox("all")))
        self.pending_canvas.create_window((0, 0), window=self.pending_scrollable_frame, anchor="nw")
        self.pending_canvas.configure(yscrollcommand=self.pending_scrollbar.set)

        self.pending_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.pending_scrollbar.pack(side="right", fill="y")
        self.populate_list(self.pending_scrollable_frame, 'pending')

    def setup_all_tab(self, parent):
        # Scrollable Area for all items
        self.all_canvas = tk.Canvas(parent, bg="#f4f6f8")
        self.all_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.all_canvas.yview)
        self.all_scrollable_frame = tk.Frame(self.all_canvas, bg="#f4f6f8")

        self.all_scrollable_frame.bind("<Configure>", lambda e: self.all_canvas.configure(scrollregion=self.all_canvas.bbox("all")))
        self.all_canvas.create_window((0, 0), window=self.all_scrollable_frame, anchor="nw")
        self.all_canvas.configure(yscrollcommand=self.all_scrollbar.set)

        self.all_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.all_scrollbar.pack(side="right", fill="y")
        self.populate_list(self.all_scrollable_frame, 'approved')


    def clear_frame(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()

    def populate_list(self, scrollable_frame, list_type):
        self.clear_frame(scrollable_frame)
        
        items_to_show = [w for w in self.all_words if (list_type == 'pending' and w.status == 'pending') or (list_type == 'approved' and w.status == 'approved')]
        
        if not items_to_show:
            lbl = tk.Label(scrollable_frame, text=f"Bu alanda bekleyen sözcük yok.", bg="#ecf0f1" if list_type == 'pending' else "#f4f6f8", fg="#7f8c8d")
            lbl.pack(pady=20)
            return

        for submission in items_to_show:
            # Card Frame
            card = tk.Frame(scrollable_frame, bg="white", bd=1, relief="solid")
            card.pack(fill="x", pady=5, padx=5, ipady=5)
            
            # Text Info
            info_frame = tk.Frame(card, bg="white")
            info_frame.pack(side="left", fill="both", expand=True, padx=10)
            
            # Word Title
            tk.Label(info_frame, text=f"ID: {submission.id} | {submission.word}", font=("Segoe UI", 12, "bold"), bg="white", anchor="w").pack(fill="x")
            # Definition
            tk.Label(info_frame, text=submission.definition, font=("Segoe UI", 10), fg="#555", bg="white", wraplength=450, justify="left", anchor="w").pack(fill="x")
            # Author & Time
            tk.Label(info_frame, text=f"Ekleyen: {submission.author} - {submission.timestamp.strftime('%Y-%m-%d %H:%M')} | Beğeni: {submission.likes}", font=("Segoe UI", 9, "italic"), fg="#999", bg="white", anchor="w").pack(fill="x")

            # Buttons
            btn_frame = tk.Frame(card, bg="white")
            btn_frame.pack(side="right", padx=10)

            if list_type == 'pending':
                # Onay Bekleyenler için: Onayla ve Reddet
                btn_yes = tk.Button(btn_frame, text="✔ Onayla", bg="#d4edda", fg="#155724", width=8,
                                    command=lambda s=submission, c=card: self.mark_action(s, 'approve', c))
                btn_yes.pack(side="left", padx=2)

                btn_no = tk.Button(btn_frame, text="✖ Reddet", bg="#f8d7da", fg="#721c24", width=8,
                                    command=lambda s=submission, c=card: self.mark_action(s, 'reject', c))
                btn_no.pack(side="left", padx=2)
            
            elif list_type == 'approved':
                # Tüm Sözcükler için: Sil
                btn_delete = tk.Button(btn_frame, text="🗑 Sil", bg="#f8d7da", fg="#721c24", width=8,
                                    command=lambda s=submission, c=card: self.mark_action(s, 'delete', c))
                btn_delete.pack(side="left", padx=2)


            submission.ui_ref = card

    def mark_action(self, submission, action, card_widget):
        # Update Logic
        submission.action = action
        
        # Update Visuals
        new_bg = ""
        if action == 'approve':
            new_bg = "#d4edda" # Light Green
        elif action == 'reject' or action == 'delete':
            new_bg = "#f8d7da" # Light Red
        elif action == 'none':
            new_bg = "white"

        # Görünümü güncelle
        card_widget.configure(bg=new_bg)
        for child in card_widget.winfo_children(): 
            child.configure(bg=new_bg)
            for sub_child in child.winfo_children():
                if 'button' not in sub_child.winfo_class().lower():
                     sub_child.configure(bg=new_bg)

    def refresh_ui(self):
        # UI'ı tamamen yeniden yüklemeden önce sadece veriyi yeniden çek
        self.load_words()
        # Eski çerçeveleri temizle ve yeniden doldur
        self.setup_pending_tab(self.pending_frame)
        self.setup_all_tab(self.all_frame)
        self.refresh_ui_title()
        messagebox.showinfo("Yenileme", "Veriler veritabanından başarıyla yenilendi.")

    def on_close(self):
        # Değişiklikleri bul
        changes = [w for w in self.all_words if w.action != 'none']
        
        if not changes:
            self.app_context.pop() 
            self.root.destroy()
            return

        if messagebox.askyesno("Değişiklikleri Kaydet", f"Veritabanına {len(changes)} değişiklik uygulanacak. Devam etmek istiyor musunuz?"):
            self.apply_changes(changes)
            self.app_context.pop() 
            self.root.destroy()
        else:
            messagebox.showinfo("İşlem İptal Edildi", "Değişiklikler uygulanmadı. Paneli tekrar açtığınızda tüm bekleyen sözcükleri görebilirsiniz.")

    def apply_changes(self, changes):
        try:
            for word in changes:
                if word.action == 'approve':
                    # Onaylama: status'ü approved yap
                    word.status = 'approved' 
                    db.session.add(word) 
                elif word.action == 'reject' or word.action == 'delete':
                    # Reddetme veya Silme: kaydı DB'den sil
                    db.session.delete(word) 
            
            db.session.commit() 
            messagebox.showinfo("Başarılı", f"Toplam {len(changes)} sözcük işlemi başarıyla uygulandı.")

        except Exception as e:
            db.session.rollback() 
            messagebox.showerror("Hata", f"Değişiklikler uygulanırken bir veritabanı hatası oluştu: {e}")
            
if __name__ == "__main__":
    # Uygulama çalışmadan önce DB'nin ve tablonun var olduğundan emin olunur.
    with app.app_context():
        db.create_all()
        
    root = tk.Tk()
    app = AdminApp(root)
    
    # Handle the "X" button on the window
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    
    root.mainloop()
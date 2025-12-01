import tkinter as tk
from tkinter import ttk, messagebox
from flask_sqlalchemy import SQLAlchemy
from flask import Flask 
from datetime import datetime
from sqlalchemy import or_ 
from sqlalchemy.orm import relationship, backref 

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
    status = db.Column(db.String(10), default='pending') 
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    comments = db.relationship("Comment", backref="word_rel", cascade="all, delete-orphan", lazy='dynamic')
    
    def __repr__(self):
        return f"<Word {self.id}: {self.word} | Status: {self.status}>"

# Yorum Modelini (Comment) ekliyoruz
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False) 
    author = db.Column(db.String(50), default='Anonim') 
    comment = db.Column(db.String(200), nullable=False) 
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Comment {self.id}: {self.comment[:20]} | Author: {self.author}>"
    
# --- ANA YÖNETİM UYGULAMASI ---
class AdminApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sözlük Yönetim Paneli (SQLite DB)")
        self.root.geometry("800x700") 
        
        self.app_context = app.app_context()
        self.app_context.push()
        
        self.all_words = [] 
        self.load_words()

        # GUI Setup
        self.setup_ui()

    def load_words(self):
        # DÜZELTME YOK (Zaten doğru çalışıyor): Tüm sözcükleri veritabanından çeker ve üzerine yazar
        self.all_words = Word.query.order_by(Word.timestamp.desc()).all()
        
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
        self.setup_tab_content(self.pending_frame, 'pending') # Tek fonksiyona bağla

        # Sekme 2: All Words (Tüm Sözcükler)
        self.all_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.all_frame, text='Tüm Sözcükler')
        self.setup_tab_content(self.all_frame, 'approved') # Tek fonksiyona bağla
        
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
    
    # YENİ METOT: Her iki sekmenin içeriğini de kurar ve temizler
    def setup_tab_content(self, parent_frame, list_type):
        self.clear_frame(parent_frame) # Çerçevenin kendisini temizle

        # Scrollable Area
        canvas = tk.Canvas(parent_frame, bg="#ecf0f1" if list_type == 'pending' else "#f4f6f8")
        scrollbar = ttk.Scrollbar(parent_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#ecf0f1" if list_type == 'pending' else "#f4f6f8")

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")
        
        self.populate_list(scrollable_frame, list_type)

    def refresh_ui_title(self):
        pending_count = sum(1 for w in self.all_words if w.status == 'pending')
        all_count = sum(1 for w in self.all_words if w.status == 'approved')
        self.notebook.tab(0, text=f'Onay Bekleyenler ({pending_count})')
        self.notebook.tab(1, text=f'Tüm Sözcükler ({all_count})')


    def clear_frame(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()

    def populate_list(self, scrollable_frame, list_type):
        # DÜZELTME: Bu fonksiyonun başında clear_frame'e gerek kalmadı çünkü setup_tab_content yapıyor.
        
        items_to_show = [w for w in self.all_words if (list_type == 'pending' and w.status == 'pending') or (list_type == 'approved' and w.status == 'approved')]
        
        if not items_to_show:
            lbl = tk.Label(scrollable_frame, text=f"Bu alanda bekleyen sözcük yok.", bg=scrollable_frame['bg'], fg="#7f8c8d")
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

            # Yorum Sayısı ve Görüntüleme Düğmesi
            comment_count = submission.comments.count()
            btn_comments = tk.Button(info_frame, 
                                     text=f"💬 Yorumlar ({comment_count})", 
                                     bg="#e6f0ff", fg="#2980b9", 
                                     font=("Segoe UI", 8), 
                                     command=lambda s=submission: self.open_comments_window(s))
            btn_comments.pack(fill="x", pady=5)


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

    # ... (open_comments_window, delete_comment_permanently ve mark_action metotları aynı kalır)

    def open_comments_window(self, word_submission):
        # Yorum penceresini oluştur
        comment_window = tk.Toplevel(self.root)
        comment_window.title(f"Yorumlar: {word_submission.word} (ID: {word_submission.id})")
        comment_window.geometry("550x550") 

        lbl_title = tk.Label(comment_window, text=f"'{word_submission.word}' Yorum Yönetimi", font=("Segoe UI", 14, "bold"), pady=10)
        lbl_title.pack(fill="x")
        
        # Yorumlar veritabanından anlık çekilir
        comments = word_submission.comments.order_by(Comment.timestamp.asc()).all()

        # Scrollable Area for comments
        comment_canvas = tk.Canvas(comment_window)
        comment_scrollbar = ttk.Scrollbar(comment_window, orient="vertical", command=comment_canvas.yview)
        comment_frame = tk.Frame(comment_canvas)
        
        comment_frame.bind("<Configure>", lambda e: comment_canvas.configure(scrollregion=comment_canvas.bbox("all")))
        comment_canvas.create_window((0, 0), window=comment_frame, anchor="nw")
        comment_canvas.configure(yscrollcommand=comment_scrollbar.set)
        
        comment_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        comment_scrollbar.pack(side="right", fill="y")
        
        if not comments:
            tk.Label(comment_frame, text="Bu kelimeye ait yorum bulunmamaktadır.", fg="#7f8c8d").pack(pady=20)
            return

        for comment in comments:
            # Yorum Kartı
            comment_card = tk.Frame(comment_frame, bg="#f4f4f4", bd=1, relief="groove")
            comment_card.pack(fill="x", pady=4, padx=5)

            # Yorum Detayları
            time_str = comment.timestamp.strftime('%Y-%m-%d %H:%M')
            lbl_info = tk.Label(comment_card, text=f"ID: {comment.id} | Yazan: {comment.author} ({time_str})", font=("Segoe UI", 10, "bold"), bg="#f4f4f4", anchor="w")
            lbl_info.pack(fill="x", padx=5, pady=2)
            
            lbl_comment = tk.Label(comment_card, text=comment.comment, font=("Segoe UI", 10), bg="#f4f4f4", wraplength=450, justify="left", anchor="w")
            lbl_comment.pack(fill="x", padx=5)

            # Silme Düğmesi
            btn_delete = tk.Button(comment_card, text="🗑 Sil", bg="#e74c3c", fg="white", width=6, 
                                   command=lambda c=comment, w=comment_window: self.delete_comment_permanently(c, w))
            btn_delete.pack(side="right", padx=5, pady=5)


    def delete_comment_permanently(self, comment, window):
        if messagebox.askyesno("Yorum Silme Onayı", f"'{comment.comment[:30]}...' yorumunu kalıcı olarak silmek istediğinizden emin misiniz?"):
            try:
                db.session.delete(comment)
                db.session.commit()
                messagebox.showinfo("Başarılı", "Yorum başarıyla silindi.")
                
                # Pencereyi kapat ve ana paneli yenile
                window.destroy()
                self.refresh_ui() 
                
            except Exception as e:
                db.session.rollback()
                messagebox.showerror("Hata", f"Yorum silinirken bir hata oluştu: {e}")

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
        # DÜZELTME: Veri ve GUI yenileme burada gerçekleşir.
        self.load_words()
        self.setup_tab_content(self.pending_frame, 'pending')
        self.setup_tab_content(self.all_frame, 'approved')
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
                    word.status = 'approved' 
                    db.session.add(word) 
                elif word.action == 'reject' or word.action == 'delete':
                    # Reddetme veya Silme: kaydı DB'den sil (İlişkili yorumlar/beğeniler cascade ile silinir)
                    db.session.delete(word) 
            
            db.session.commit() 
            messagebox.showinfo("Başarılı", f"Toplam {len(changes)} sözcük işlemi başarıyla uygulandı.")

        except Exception as e:
            db.session.rollback() 
            messagebox.showerror("Hata", f"Değişiklikler uygulanırken bir veritabanı hatası oluştu: {e}")
            
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        
    root = tk.Tk()
    app = AdminApp(root)
    
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    
    root.mainloop()
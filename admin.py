import tkinter as tk
from tkinter import ttk, messagebox
import os

SUBMISSIONS_FILE = 'submissions.txt'
WORDS_FILE = 'words.txt'

class AdminApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Moderation Panel - Yeni Sözcükler")
        self.root.geometry("600x700")
        
        # Data storage
        self.entries = [] # List of dictionaries: {'line': str, 'action': 'none'}
        self.load_submissions()

        # GUI Setup
        self.setup_ui()
        self.populate_list()

    def setup_ui(self):
        # Header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.pack(fill="x")
        lbl_title = tk.Label(header_frame, text="Review Submissions", font=("Segoe UI", 16, "bold"), fg="white", bg="#2c3e50")
        lbl_title.pack(pady=15)

        # Scrollable Area for items
        self.canvas = tk.Canvas(self.root, bg="#f4f6f8")
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#f4f6f8")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.scrollbar.pack(side="right", fill="y")

        # Bottom Action Bar
        action_bar = tk.Frame(self.root, bg="#ecf0f1", height=50)
        action_bar.pack(fill="x", side="bottom")
        
        btn_save = tk.Button(action_bar, text="Save & Quit", bg="#27ae60", fg="white", 
                             font=("Segoe UI", 10, "bold"), padx=20, pady=10,
                             command=self.on_close)
        btn_save.pack(pady=10)

    def load_submissions(self):
        if not os.path.exists(SUBMISSIONS_FILE):
            open(SUBMISSIONS_FILE, 'w').close()
            
        with open(SUBMISSIONS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                if ':' in line:
                    parts = line.strip().split(':', 1)
                    if len(parts) == 2:
                        self.entries.append({
                            'word': parts[0], 
                            'def': parts[1], 
                            'original_line': line,
                            'action': 'none', # none, approve, reject
                            'ui_ref': None # Will store the frame widget
                        })

    def populate_list(self):
        if not self.entries:
            lbl = tk.Label(self.scrollable_frame, text="No pending submissions.", bg="#f4f6f8", fg="#7f8c8d")
            lbl.pack(pady=20)
            return

        for index, item in enumerate(self.entries):
            # Card Frame
            card = tk.Frame(self.scrollable_frame, bg="white", bd=1, relief="solid")
            card.pack(fill="x", pady=5, padx=5, ipady=5)
            
            # Text Info
            info_frame = tk.Frame(card, bg="white")
            info_frame.pack(side="left", fill="both", expand=True, padx=10)
            
            tk.Label(info_frame, text=item['word'], font=("Segoe UI", 12, "bold"), bg="white", anchor="w").pack(fill="x")
            tk.Label(info_frame, text=item['def'], font=("Segoe UI", 10), fg="#555", bg="white", wraplength=350, justify="left", anchor="w").pack(fill="x")

            # Buttons
            btn_frame = tk.Frame(card, bg="white")
            btn_frame.pack(side="right", padx=10)

            btn_yes = tk.Button(btn_frame, text="✔", bg="#ecf0f1", width=3,
                                command=lambda i=index, c=card: self.mark_action(i, 'approve', c))
            btn_yes.pack(side="left", padx=2)

            btn_no = tk.Button(btn_frame, text="✖", bg="#ecf0f1", width=3,
                               command=lambda i=index, c=card: self.mark_action(i, 'reject', c))
            btn_no.pack(side="left", padx=2)
            
            item['ui_ref'] = card

    def mark_action(self, index, action, card_widget):
        # Update Logic
        self.entries[index]['action'] = action
        
        # Update Visuals
        if action == 'approve':
            card_widget.configure(bg="#d4edda") # Light Green
            for child in card_widget.winfo_children(): child.configure(bg="#d4edda")
        elif action == 'reject':
            card_widget.configure(bg="#f8d7da") # Light Red
            for child in card_widget.winfo_children(): child.configure(bg="#f8d7da")

    def on_close(self):
        # Check if we have work to do
        changes = [e for e in self.entries if e['action'] != 'none']
        if not changes and not self.entries:
            self.root.destroy()
            return

        if messagebox.askyesno("Save Changes", "Apply these changes to the live website?"):
            self.apply_changes()
            self.root.destroy()

    def apply_changes(self):
        new_submissions = [] # What stays in queue
        approved_lines = []  # What goes to live site

        for item in self.entries:
            if item['action'] == 'approve':
                # Reconstruct line ensuring newline
                approved_lines.append(f"{item['word']}:{item['def']}\n")
            elif item['action'] == 'reject':
                pass # Do nothing, effectively deletes it
            else:
                # Keep in submissions
                new_submissions.append(item['original_line'])

        # 1. Append approved to words.txt
        if approved_lines:
            with open(WORDS_FILE, 'a', encoding='utf-8') as f:
                f.writelines(approved_lines)

        # 2. Overwrite submissions.txt with whatever is left
        with open(SUBMISSIONS_FILE, 'w', encoding='utf-8') as f:
            f.writelines(new_submissions)
            
        print("Batch process complete.")

if __name__ == "__main__":
    root = tk.Tk()
    app = AdminApp(root)
    
    # Handle the "X" button on the window
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    
    root.mainloop()
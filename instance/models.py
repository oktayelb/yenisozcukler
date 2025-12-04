from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, UTC

# SQLAlchemy nesnesini global olarak başlatır, ancak henüz hiçbir uygulamaya bağlanmaz (Application Factory deseni).
# app.py'da bu nesneye erişim sağlanacak.
db = SQLAlchemy() # Buradaki db nesnesini app.py'dan alacağız.


# --- DATABASE MODELS ---

class Word(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(50), nullable=False)
    definition = db.Column(db.String(300), nullable=False)
    author = db.Column(db.String(20), default='Anonymous')
    
    liked_by = db.relationship("UserLike", backref="word_rel", cascade="all, delete-orphan", lazy="dynamic")
    comments = db.relationship("Comment", backref="word_rel", cascade="all, delete-orphan", lazy='dynamic')
    
    status = db.Column(db.String(10), default='pending') 
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    def to_dict(self):
        return {
            'id': self.id,
            'word': self.word,
            'def': self.definition,
            'author': self.author,
            'likes': self.liked_by.count(), 
            'timestamp': self.timestamp.isoformat()
        }

class UserLike(db.Model):
    __tablename__ = 'user_like'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False) 
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    
    __table_args__ = (db.UniqueConstraint('ip_address', 'word_id', name='_user_word_uc'),)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False) 
    author = db.Column(db.String(50), default='Anonim') 
    comment = db.Column(db.String(200), nullable=False) 
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    def to_dict(self):
        return {
            'id': self.id,
            'word_id': self.word_id,
            'author': self.author,
            'comment': self.comment,
            'timestamp': self.timestamp.isoformat() 
        }
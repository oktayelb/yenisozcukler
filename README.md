## Türkçe

### Proje Özeti

**Yeni Sözcükler**, Türkçe kelime sözlüğünün topluluk tarafından oluşturulmasını amaçlayan Flask tabanlı bir web uygulamasıdır. Platform, içerik kalitesini korumak için gönderim ve moderasyon aşamalarından oluşan bir iş akışı kullanır.

**Canlı Adres:** `http://147.185.221.224:2416/`

### Tasarım ve Kullanıcı Arayüzü

Uygulama sade, kağıt benzeri bir görünüm benimser. Başlıklar için el yazısı stilinde (Caveat), gövde metinleri için ise klasik serif (Merriweather) yazı tipleri kullanılır. Soluk renkler ve hafif gölgelerle desteklenen bu yapı, dikkat dağıtmayan, analog bir atmosfer oluşturur.

### Güvenlik ve Moderasyon

Önerilen kelimeler önce ayrı bir kuyrukta (`submissions.txt`) tutulur ve `admin.py` üzerinden yürütülen moderasyon sürecini geçmeden genel sözlüğe (`words.txt`) eklenmez.

Platform bütünlüğünü korumak için mevcut önlemler:

* **Sunucu Taraflı Doğrulama:** Kelime, tanım ve takma ad alanlarının yalnızca izin verilen karakterleri (harfler, boşluklar, noktalar, virgüller) içerdiği doğrulanır. Maksimum uzunluk sınırları uygulanır (Kelime 50, Tanım 300, Takma Ad 20 karakter).
* **Oran Sınırlaması (Rate Limiting):** Gönderimlerin aynı IP adresinden 5 saniyede bir yapılmasına izin verilerek temel düzeyde bir spam koruması sağlanır.

### Dağıtım Notu

Hizmet şu anda genel erişim için **playit.gg** aracılığıyla tünellenmektedir. Bu geçici bir çözümdür; yakın zamanda daha kalıcı ve özel bir barındırma ortamına geçiş planlanmaktadır.

### Gelecek Güvenlik Planları

Yüksek trafik yükü veya saldırı durumlarında hizmetin kesintisiz çalışmasını sağlamak için özel bir DDOS koruma katmanı eklenmesi planlanmaktadır.

---

# Yeni Sözcükler (New Words)

A community-driven platform for suggesting and curating new or niche Turkish words and their definitions.

---

## English

### Project Overview

**Yeni Sözcükler** is a Flask-based web application designed to support the collaborative creation of a Turkish word dictionary. It relies on a submission and moderation workflow to maintain quality and accuracy.

**Live Address:** `http://147.185.221.224:2416/`

### Design and User Interface

The application adopts a simple, paperlike aesthetic. Titles use handwritten-style fonts (Caveat), while body text relies on a classic serif typeface (Merriweather). Muted colors and light shadows help create a calm, analog-style visual atmosphere.

### Security and Moderation

Word suggestions are stored in a separate queue (`submissions.txt`) and must pass a moderator review through the `admin.py` interface before being added to the public dictionary (`words.txt`).

Current safeguards include:

* **Server-Side Validation:** The backend ensures that submitted words, definitions, and nicknames contain only allowed characters (letters, spaces, periods, commas) and enforces length limits (Word 50, Definition 300, Nickname 20 characters).
* **Rate Limiting:** Each client IP is restricted to one submission every 5 seconds to reduce spam.

### Deployment Note

Public access is currently provided through tunneling via **playit.gg**. This setup is temporary, with a planned move to a dedicated, permanent hosting environment.

### Future Security Plans

A dedicated DDOS protection layer is planned to maintain service availability during high traffic or malicious activity.

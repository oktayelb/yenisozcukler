\*\*\*



\## Türkçe



\### Proje Özeti



\*\*Yeni Sözcükler\*\*, Türkçe kelime sözlüğünün topluluk tarafından oluşturulmasını sağlayan Flask tabanlı bir web uygulamasıdır. Platform, içerik kalitesini ve bütünlüğünü korumak için bir gönderim ve moderasyon iş akışı kullanır.



\*\*Canlı Adres:\*\* `http://147.185.221.224:2416/`



\### Tasarım ve Kullanıcı Arayüzü



Uygulama, \*\*sade ve kağıt benzeri bir estetiğe\*\* sahiptir. Tasarım, başlıklar için el yazısı stilindeki yazı tipleri (Caveat) ile gövde metinleri için klasik serif tipografiyi (Merriweather) birleştirir; soluk renkler ve hafif gölgeler kullanılarak dikkat dağıtıcı olmayan, analog bir his yaratılmıştır.



\### Güvenlik ve Moderasyon



Önerilen kelimeler ayrı bir kuyrukta (`submissions.txt`) tutulur ve genel sözlüğe (`words.txt`) eklenmeden önce, `admin.py` uygulaması aracılığıyla moderatör kontrollü bir inceleme sürecinden geçmek zorundadır.



Platform bütünlüğünü korumak için mevcut önlemler şunları içerir:

\* \*\*Sunucu Taraflı Doğrulama:\*\* Arka uç, kelime, tanım ve takma adın yalnızca izin verilen karakterleri (harfler, boşluklar, noktalar, virgüller) içerdiğini kesin olarak doğrular ve maksimum uzunluk sınırlarını uygular (Kelime maks. 50, Tanım maks. 300, Takma Ad maks. 20).

\* \*\*Oran Sınırlaması (Rate Limiting):\*\* Gönderim spam'ine karşı temel bir savunma olarak, her istemci IP adresi için gönderimler 5 saniyede bir ile sınırlandırılmıştır.



\### Dağıtım Notu



Hizmet, şu anda genel erişilebilirlik için \*\*playit.gg\*\* kullanılarak tünellenmektedir. Bu geçici bir kurulumdur ve yakın gelecekte daha kalıcı, özel bir barındırma çözümüne geçiş yapılacaktır.



\### Gelecek Güvenlik Planları



Yüksek hacimli trafik veya kötü niyetli saldırılar altında hizmetin kullanılabilirliğini sağlamak için \*\*özel bir DDOS savunma katmanı\*\* uygulamayı planlıyoruz.



\*\*\*

\*\*\*



\# Yeni Sözcükler (New Words)



A community-driven platform for suggesting and curating new or niche Turkish words and their definitions.



\*\*\*



\## English



\### Project Overview



\*\*Yeni Sözcükler\*\* is a Flask-based web application that facilitates the collaborative creation of a word dictionary. The platform uses a submission and moderation workflow to ensure quality and integrity.



\*\*Live Address:\*\* `http://147.185.221.224:2416/`



\### Design and User Interface



The application features a \*\*simple, paperlike aesthetic\*\*. The design uses muted colors (e.g., `#f4f1ea` background, `#fdfbf7` card), subtle box shadows, and handwritten-style fonts (Caveat) for titles, combined with classic serif typography (Merriweather) for body text. This combination is intended to create a distraction-free, analog feel.



\### Security and Moderation



Submissions are held in a separate queue (`submissions.txt`) and must pass through a moderator-controlled review process via the `admin.py` application before being added to the public dictionary (`words.txt`).



Current measures to maintain platform integrity include:

\* \*\*Server-Side Validation:\*\* The backend strictly verifies that the word, definition, and nickname only contain allowed characters (letters, spaces, periods, commas) and enforces maximum length limits (Word max 50, Definition max 300, Nickname max 20).

\* \*\*Rate Limiting:\*\* A basic defense against submission spam is enforced by limiting each client IP address to one post every 5 seconds.



\### Deployment Note



The service is currently being tunneled using \*\*playit.gg\*\* for public accessibility. This is a temporary setup, and a transition to a more permanent, dedicated hosting solution will be implemented in the near future.



\### Future Security Plans



We are planning to implement a \*\*dedicated DDOS defense layer\*\* to ensure service availability under high-volume traffic or malicious attacks.



\*\*\*




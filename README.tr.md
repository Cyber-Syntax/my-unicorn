[![en](https://img.shields.io/badge/lang-en-green.svg)](https://github.com/Cyber-Syntax/my-unicorn/blob/main/README.md)
[![tr](https://img.shields.io/badge/lang-tr-blue.svg)](https://github.com/Cyber-Syntax/my-unicorn/blob/main/README.tr.md)

---

# **⚠️ Dikkat**

- **Bu proje kalıcı beta aşamasında** olup sınırlı testlerden geçmiştir. Başlangıçta öğrenme amaçlı geliştirilmiş olsa da, benim özel ihtiyaçlarımı etkin bir şekilde karşılamaktadır.
- **Önemli:** Script’i güncellerken **Releases** bölümündeki talimatları takip edin. Güncellemeler yeni özellikler veya değişiklikler içerebilir ve bu değişiklikler farklı adımlar gerektirebilir. Talimatları olabildiğince basit tutmaya çalışacağım.
- **Şu anda desteklenen:** Sadece Linux. macOS'ta çalışabilir, ancak henüz test edilmemiştir.

---

## **🙏 Bu Projeye Destek Olun**

Bu script size yardımcı olduysa:

- **GitHub üzerinde yıldız ⭐** vererek desteğinizi gösterebilirsiniz, böylece kodlama yolculuğumda motive olmamı sağlar!

---

## **🦄 my-unicorn Hakkında**

- GitHub üzerinden API kullanarak en son AppImage dosyasını indirir. Ayrıca dosyayı aşağıdaki hash türleriyle doğrular:

  - 🛠️ **Test Edildi:**
    - [x] sha256
    - [x] sha512

- **Bu script ile hangi uygulamalar test edilmiştir?**
  - 🛠️ **Test Edildi:**
    - [x] super-productivity
    - [x] siyuan-note
    - [x] Joplin

---

## **🛠️ Bağımlılıklar**

- [requests](https://pypi.org/project/requests/)
- [yaml](https://pypi.org/project/PyYAML/)
- [tqdm](https://pypi.org/project/tqdm/)

### İsteğe Bağlı: Sanal ortam oluşturma

1. Repo’yu klonladığınız dizine gidin.
2. Sanal ortam oluşturun:
   - `python3 -m venv .venv`
3. Sanal ortamı aktive edin:
   - `source .venv/bin/activate`
4. Bağımlılıkları pip ile yükleyin:
   - `pip install -r requirements.txt`
   - Eğer bu çalışmazsa, manuel olarak yükleyin:
     - `pip3 install tqdm`

---

## **⚠️ Kullanımdan Önce Bilmeniz Gerekenler**

1. **GitHub URL’si:** Uygulamanın GitHub repo URL’si (örn. `https://github.com/johannesjo/super-productivity`).
2. **Hash türü:** Hash türünü belirtin (örn. super-productivity için sha512).
3. **Hash doğrulama sorunları:** Hash doğrulama başarısız olursa, JSON dosyasına manuel olarak hash ekleyebilirsiniz:
   - GitHub release sayfasında (örn. [super-productivity releases](https://github.com/johannesjo/super-productivity/releases)) en son hash’i bulun.
   - `json_files` klasöründe örnek dosyaları kontrol edin. Tüm JSON dosyaları beklenildiği gibi çalışacaktır.

---

## **💡 Kullanım**

### Örnek adımlar:

1. Terminali açın ve repo’yu klonlayın (git’in yüklü olduğundan emin olun):

   ```bash
   git clone https://github.com/Cyber-Syntax/my-unicorn.git
   ```

2. Proje dizinine gidin:

   ```bash
   cd ~/Downloads/Cyber-Syntax/my-unicorn
   ```

3. Sanal ortamı aktif edin (eğer uygulandıysa):

   ```bash
   source .venv/bin/activate
   ```

4. Script’i başlatın:

   ```bash
   python3 main.py
   ```

5. Ekrandaki talimatları takip edin.

---

## **📥 Yeni AppImage Nasıl Yüklenir (Konfigürasyon Dosyası Oluşturma)**

Bu adımı, eğer script ile daha önce AppImage yüklediyseniz veya konfigürasyon dosyasını (örn. `siyuan.json`) manuel olarak oluşturduysanız atlayabilirsiniz.

```bash
╰─❯ python3 main.py
my-unicorn 🦄’a Hoş Geldiniz!
Aşağıdaki seçeneklerden birini seçin:
===================================
1. Mevcut AppImage’ı güncelle
2. Yeni AppImage indir
3. Json dosyasını güncelle
4. Çıkış
===================================
Seçiminizi yapın: 2
Yeni AppImage indiriliyor
Aşağıdaki seçeneklerden birini seçin:
===================================
1. Eski AppImage’ı yedekle ve yeni AppImage’ı indir
2. Yeni AppImage’ı indir ve eski AppImage’ı üzerine yaz
Seçiminizi yapın: 1
===================================
App GitHub URL’sini girin: https://github.com/laurent22/joplin
AppImage’ı kaydedeceğiniz dizini girin (Varsayılan: '~/Documents/appimages'):
Eski AppImage’ı kaydedeceğiniz dizini girin (Varsayılan: '~/Documents/appimages/backup'):
Hash türünü girin (sha256, sha512): sha512
===================================
URL’den sahip ve repo ayrıştırılıyor...
Joplin indiriliyor... Bir fincan kahve alabilirsiniz :) İnternet hızınıza bağlı olarak biraz zaman alabilir.
Joplin-2.13.12.AppImage: 100%|██████████████████████████████████████████████████| 201M/201M [00:19<00:00, 11.0MiB/s]
```

---

## **🔄 AppImage Nasıl Güncellenir**

```bash
╰─❯ python3 main.py

my-unicorn 🦄’a Hoş Geldiniz!
Aşağıdaki seçeneklerden birini seçin:
====================================
1. Mevcut AppImage’ı güncelle
2. Yeni AppImage indir
3. Json dosyasını güncelle
4. Çıkış
====================================
Seçiminizi yapın: 1

Birden fazla .json dosyası bulundu, lütfen birini seçin:
============================================================
1. siyuan.json
2. super-productivity.json
3. joplin.json
============================================================
Seçiminizi yapın: 3
```

---

## **🤝 Katkı Sağlama**

- Bu proje temelde öğrenme amaçlıdır, ancak geri bildirim veya öneriler için açığım! Katkılar ve fikirler değerlendirilecektir, ancak her katkı veya değişiklik garanti edilmez.
- Detaylı açıklamalar için lütfen [CONTRIBUTING.md](.github/CONTRIBUTING.md) dosyasına başvurun.

---

## **📝 Lisans**

Bu script, [GPL 3.0 Lisansı](https://www.gnu.org/licenses/gpl-3.0.en.html) altında lisanslanmıştır. Lisansın bir kopyasını [LICENSE](https://github.com/Cyber-Syntax/my-unicorn/blob/main/LICENSE) dosyasından veya [www.gnu.org](https://www.gnu.org/licenses/gpl-3.0.en.html) adresinden bulabilirsiniz.

---

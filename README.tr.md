[![en](https://img.shields.io/badge/lang-en-green.svg)](https://github.com/Cyber-Syntax/my-unicorn/blob/main/README.md)
[![tr](https://img.shields.io/badge/lang-tr-blue.svg)](https://github.com/Cyber-Syntax/my-unicorn/blob/main/README.tr.md)


# **⚠️ Dikkat**

- Bu proje sınırlı testlerden dolayı şu anlık **beta aşamasındadır** . Başlangıçta öğrenme amaçlı geliştirilmiş olsa da, benim özel ihtiyaçlarımı etkin bir şekilde karşılamaktadır.
- **Önemli:** Script’i güncellerken **Releases** bölümündeki talimatları takip edin. Güncellemeler yeni özellikler veya değişiklikler içerebilir ve bu değişiklikler farklı adımlar gerektirebilir. Talimatları olabildiğince basit tutmaya çalışacağım.
- **Şu anda desteklenen:** Sadece Linux. macOS'ta çalışabilir, ancak henüz test edilmemiştir.


## **🦄 my-unicorn Hakkında**

- Bu projeyi problemimi çözmek için oluşturdum. Bu betiği, GitHub API'sinden bir AppImage indirir, kullanıcının seçtiği bir dizine kaydeder, AppImage hakkında bilgi kaydetmek ve güncelleme sürecini otomatikleştirmek için bir config dosyası (JSON) oluşturur. Ayrıca bu betik, GitHub repository'sından doğrulama dosyasının SHA256 veya SHA512 hash'i ile gerçek AppImage'nin karşılaştırarak, doğru şekilde indirilip indirilmediğini kontrol edebilir.

- **Bu script ile hangi uygulamalar test edilmiştir?**

  - 🛠️ **Test Edildi:**
    - [x] super-productivity
    - [x] siyuan-note
    - [x] Joplin

- 🛠️ **Test Edildi:**

  - [x] sha256
  - [x] sha512


# **💡 Nasıl Kullanılır**

## **⚙️ Kurulum**

1. Bir terminal açın ve bu depoyu klonlayın (git'in yüklü olduğundan emin olun):

   ```bash
   cd ~/Downloads/
   git clone https://github.com/Cyber-Syntax/my-unicorn.git
   ```

2. Proje dizinine gidin:

   ```bash
   cd ~/Downloads/Cyber-Syntax/my-unicorn
   ```

3. **Opsiyonel: Sanal bir ortam oluşturun (Tavsiye Edilir)**

   - Sanal ortam oluşturun:
     - `python3 -m venv .venv`
   - Sanal ortamı etkinleştirin:
     - `source .venv/bin/activate`
   - `pip` kullanarak bağımlılıkları yükleyin:
     - `pip install -r requirements.txt`
   - Eğer bu yöntem çalışmazsa, bağımlılıkları manuel olarak yükleyin (bazıları zaten yüklü olabilir; hata alırsanız yüklenmeyenleri deneyin).
     - `pip3 install babel certifi idna charset-normalizer PyYAML requests tqdm urllib3`

4. Sanal ortamı etkinleştirin (eğer oluşturulduysa):

   ```bash
   source .venv/bin/activate
   ```

5. Nasıl kulllanılacağını öğrenmek için alttakileri okumaya devam edin.


## **🛠️ Uygulama Kullanımı**

1. `super-productivity.json` veya diğer örnek yapılandırma dosyalarını `config_files_examples/` klasöründen, uygulamanızın appimage dosyalarının bulunduğu dizine kopyalayabilirsiniz (varsayılan: `~/Documents/appimages/config_files/super-productivity.json`). Bu yapılandırma dosyası, super-productivity appimage için bir örnektir.

2. Uygulama ile bir yapılandırma dosyası oluşturabilirsiniz. Ancak bunun için uygulama hakkında bazı bilgilere ihtiyacınız olacak:
   - **GitHub URL:** Uygulamanın GitHub depo adresi (örn. `https://github.com/johannesjo/super-productivity`).
3. Hash türü ve Hash dosya adı otamatik olarak tespit edilir. Eğer uygulamanın uyumluluğu yoksa veya hata oluşursa aşağıdaki bilgileri sağlamanız gerekecek:
   - **Hash türü:** Hash türünü belirtin (örn. super-productivity için sha512).
   - **Hash doğrulama sorunları:** Eğer hash doğrulama başarısız olursa, hash'i manuel olarak JSON dosyasına ekleyebilirsiniz:
     - En son hash bilgisini GitHub sürüm sayfasında bulabilirsiniz (örn. [super-productivity releases](https://github.com/johannesjo/super-productivity/releases)).
     - Örnekler için `json_files` klasörüne bakabilirsiniz. Tüm JSON dosyalarının beklendiği gibi çalışması gerekmektedir.

## **🙏 Bu Projeye Destek Olun**

- **GitHub üzerinde yıldız ⭐** vererek desteğinizi gösterebilirsiniz, böylece kodlama yolculuğumda motive olmamı sağlar!
- **💖 Projeyi Destekle:** Çalışmalarımı desteklemek ve projeler yapmaya devam etmemi sağlamak istersen, bana sponsor olmayı düşünebilirsin:
  - [![Sponsor Ol](https://img.shields.io/badge/Sponsor-💖-brightgreen)](https://github.com/sponsors/Cyber-Syntax)


### **🤝 Katkı Sağlama**

- Bu proje benim için öncelikle bir öğrenme kaynağıdır, ancak geri bildirim veya önerilerden memnuniyet duyarım! Tüm katkıları entegre etmeyi veya sürekli olarak katılım sağlamayı vaat edemem, ancak proje hedeflerine uygun iyileştirmelere ve fikirlere açığım.
- Yine de, daha ayrıntılı bir açıklama için lütfen [CONTRIBUTING.tr.md](.github/CONTRIBUTING.tr.md) dosyasına göz atın.


## **📝 Lisans**

Bu script, [GPL 3.0 Lisansı](https://www.gnu.org/licenses/gpl-3.0.en.html) altında lisanslanmıştır. Lisansın bir kopyasını [LICENSE](https://github.com/Cyber-Syntax/my-unicorn/blob/main/LICENSE) dosyasından veya [www.gnu.org](https://www.gnu.org/licenses/gpl-3.0.en.html) adresinden bulabilirsiniz.


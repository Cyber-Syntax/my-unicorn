# **My Unicorn 🦄 - Linux için AppImage Yöneticisi**

> [!CAUTION]
>
> - Bu proje sınırlı testlerden dolayı şu anlık **alpha aşamasındadır** ancak işlevseldir. Karşılaştığınız sorunları lütfen bildirin.
> - **Önemli:** Script'i güncellerken potansiyel sorunlardan kaçınmak için **Releases bölümündeki** talimatları takip edin.
> - **Desteklenen OS:** Şu anlık sadece Linux destekleniyor ve test ediliyor.

İngilizce: [README.md](README.md)

## 📋 Genel Bakış

> [!NOTE]
>
> My Unicorn, Linux'ta AppImage'ları yönetmek için bir komut satırı aracıdır. Kullanıcıların GitHub depolarından AppImage'ları kolayca yüklemesine, güncellemesine ve yönetmesine olanak tanır. AppImage'ları işleme sürecini basitleştirmek için tasarlanmıştır ve kullanıcıların uygulamalarını güncel tutmasını daha uygun hale getirir.
>
> - Detaylı bilgi: [wiki.md](docs/wiki.md)

- **Desteklenen Uygulamalar:**
    - Super-Productivity, Siyuan, Joplin, Standard-notes, Logseq, QOwnNotes, Tagspaces, Zen-Browser, Zettlr, HeroicGamesLauncher, KDiskMark, AppFlowy, Obsidian, FreeTube
    - Doğrulaması olmayan uygulamalar (geliştirici hash sağlamıyor):
        - WeekToDo
    - Daha fazlası [catalog](src/my_unicorn/catalog) klasöründe bulunabilir.
- **Desteklenen hash türleri:**
    - sha256, sha512

## 🚀 Hızlı Başlangıç Örneği

```bash
my-unicorn install qownnotes
Fetching from API:
GitHub Releases      1/1 Retrieved

Downloading:
QOwnNotes-x86_64   41.5 MiB  10.8 MB/s 00:00 [==============================]   100% ✓

Installing:
(1/2) Verifying qownnotes ✓
(2/2) Installing qownnotes ✓


Installation Summary:
--------------------------------------------------
qownnotes                 ✓ 25.12.7
```

## 💡 Yükleme

## Seçenek 1: uv kullanarak yükleme (Önerilen)

> [!TIP]
>
> Bu yöntem üretim kullanımı için önerilir. my-unicorn'u izole edilmiş bir CLI aracı olarak yükler.

### Ön Koşullar

Henüz yüklemediyseniz `uv`'yi yükleyin:

```bash
# Fedora
sudo dnf install uv

# Arch Linux
sudo pacman -S uv

# Evrensel yükleyici (Linux, macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Üretim Yüklemesi

#### Yöntem 1: install.sh kullanarak (önerilen)**

> [!NOTE]
>
> Bu yöntem bash/zsh kabukları için otomatik tamamlama ayarlar.

```bash
cd ~/Downloads
git clone https://github.com/Cyber-Syntax/my-unicorn.git
cd my-unicorn
./install.sh -i
```

#### Yöntem 2: Doğrudan uv komutu

> [!NOTE]
>
> Bu yöntem otomatik tamamlama ayarlamaz. Gerekirse manuel olarak ayarlayın.

```bash
uv tool install git+https://github.com/Cyber-Syntax/my-unicorn
```

### Güncelleme

my-unicorn'u en son sürüme güncellemek için çalıştırın:

```bash
my-unicorn upgrade
```

### Geliştirme Yüklemesi (katkıda bulunanlar için)

**install.sh kullanarak:**

```bash
cd ~/Downloads/my-unicorn
./install.sh -e
```

**Doğrudan uv komutu:**

```bash
cd ~/Downloads/my-unicorn
uv tool install --editable .
```

Kaynak kodundaki değişiklikler yeniden yüklemeye gerek olmadan hemen yansıtılır.

## Seçenek 2: Geleneksel Yükleme (Eski)

> [!TIP]
>
> Yükleyici script, gerekli bağımlılıkları yüklemek için venv kullanır.

1. Bir terminal açın ve bu depoyu klonlayın (git'in yüklü olduğundan emin olun):

    ```bash
    cd ~/Downloads &
    git clone https://github.com/Cyber-Syntax/my-unicorn.git
    ```

2. `uv`'yi yükleyin (ÖNERİLEN):

    > `uv`, bağımlılıkları venv'e yüklemek için kullanılır, pip'ten daha verimlidir.

    ```bash
    # fedora
    sudo dnf install uv
    # arch
    sudo pacman -S uv
    # veya `uv` astral resmi bağımsız yükleyici
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

3. Paket olarak oluşturun:

    ```bash
    # Proje dizinine gidin
    cd my-unicorn &
    # Yükleyiciyi çalıştırın (mevcut ise UV'yi otomatik kullanır)
    ./install.sh -i
    ```

4. my-unicorn'u kullanmaya başlayın:

    ```bash
    my-unicorn --help # komut seçeneklerini görmek için
    ```

## Uyumsuz uygulamalar için (URL ile yükleme)

> [!IMPORTANT]
>
> Uyumsuz bir uygulamayı yüklemek istiyorsanız, uygulama hakkında bazı bilgilere sahip olmanız gerekecektir.

- **GitHub URL:** Uygulamanın depo URL'si (örn. `https://github.com/johannesjo/super-productivity`).
- Hash türü ve Hash dosya adı otomatik olarak tespit edilir. Uygulama uyumluluğu mevcut değilse veya hata oluşursa aşağıdaki bilgileri sağlamanız gerekecektir:
    - **Hash türü:** Hash türünü belirtin (örn. super-productivity için sha512).
    - **Hash doğrulama sorunları:** Hash doğrulaması başarısız olursa, hash'i manuel olarak JSON dosyasına ekleyebilirsiniz:
        - En son hash bilgisini GitHub sürüm sayfasında arayın (örn. [super-productivity releases](https://github.com/johannesjo/super-productivity/releases)).
        - Örnekler için [catalog](src/my_unicorn/catalog) klasörüne bakın.

## **🙏 Bu Projeye Destek Olun**

- **GitHub'da yıldız ⭐** vererek desteğinizi gösterebilir ve kodlama yolculuğumda motive olmamı sağlayabilirsiniz!
- **Test:** Script'i test eder ve karşılaştığınız sorunlar hakkında geri bildirim sağlarsanız harika olur.
- **💖 Beni Sponsorla:** Çalışmalarımı desteklemek ve öğrenmeye ve projeler yapmaya devam etmemi sağlamak istersen, beni sponsor olmayı düşün:
    - [![Sponsor Ol](https://img.shields.io/badge/Sponsor-💖-brightgreen)](https://github.com/sponsors/Cyber-Syntax)

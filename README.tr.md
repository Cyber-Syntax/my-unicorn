English Description: [README.md](README.md)

> [!CAUTION]
> Bu proje sınırlı testlerden dolayı şu anlık **alpha aşamasındadır**.
>
> **Önemli:** Script’i güncellerken **Releases** bölümündeki talimatları takip edin.
>
> **Desteklenen İşletim Sistemleri:** Şu anlık sadece Linux destekleniyor.

## **🦄 my-unicorn Hakkında**

> [!NOTE]
> Manuel AppImage güncelleme sürecinden yılmıştım, süreci otomatikleştirmek için bu projeyi oluşturdum.
>
> Detaylı bilgi: [wiki.md](docs/wiki.md)

- **Desteklenen Uygulamalar:**
    - Super-Productivity, Siyuan, Joplin, Standard-notes, Logseq, QOwnNotes, Tagspaces, Zen-Browser, weektodo, Zettlr
    - Doğrulaması olmayan uygulamalar (yazılımcıları hash sağlamıyor):
        - FreeTube
            - Bağlantılı sorun: <https://github.com/FreeTubeApp/FreeTube/issues/4720>)
        - AppFlowy
        - Obsidian
    - Daha fazlası [apps](src/my_unicorn/apps) klasöründe bulunabilir.
- **Desteklenen Hash Türleri:**
    - sha256, sha512

# 💡 Yükleme/Kurulum

> [!TIP]
> Installer script, gerekli bağımlılıkları yüklemek için Venv kullanır.

1. Bir terminal açın ve bu depoyu klonlayın (git'in yüklü olduğundan emin olun):

   ```bash
   cd ~/Downloads/
   git clone https://github.com/Cyber-Syntax/my-unicorn.git
   ```

2. Paket olarak oluşturun:

    ```bash
    cd my-unicorn &
    sh setup.sh install
    ```

## Paketi kaldır

> [!TIP]
> Eğer paketi küresel olarak yüklediyseniz, aşağıdaki komutu kullanarak kaldırabilirsiniz:

    ```bash
    pip uninstall my-unicorn
    ```

# Nasıl Kullanılır?

## Paket olarak kullanım

```bash
my-unicorn --help # to see the command options
```

```bash
usage: my-unicorn [-h] {download,install,update,token,migrate} ...

my-unicorn: AppImage management tool

positional arguments:
  {download,install,update,token,migrate}
                        Available commands
    download            Download AppImage from URL
    install             Install app from catalog
    update              Update AppImages
    token               GitHub token management
    migrate             Migrate configuration files

options:
  -h, --help            show this help message and exit

Examples:
my-unicorn # Interactive mode (default)
my-unicorn download https://github.com/johannesjo/super-productivity # Download AppImage from URL
my-unicorn install joplin # Install AppImage from catalog
my-unicorn update --all # Update all AppImages
my-unicorn update --select joplin,super-productivity # Select AppImages to update
my-unicorn token --save # Save GitHub token to keyring
my-unicorn token --remove # Remove GitHub token
my-unicorn token --check # Check GitHub API rate limits
my-unicorn migrate --clean # Migrate configuration files
my-unicorn migrate --force # Migrate configuration without confirmation
```

## Desteklenmeyen uygulamalar için (URL ile kurulum)

> [!IMPORTANT]
> Eğer desteklenmeyen bir uygulamayı kurmak istiyorsanız, uygulama hakkında bazı bilgilere sahip olmanız gerekecektir.

- **GitHub URL:** Uygulamanın GitHub depo adresi (örn. `https://github.com/johannesjo/super-productivity`).
- Hash türü ve Hash dosya adı otamatik olarak tespit edilir. Eğer uygulamanın uyumluluğu yoksa veya hata oluşursa aşağıdaki bilgileri sağlamanız gerekecek:
    - **Hash türü:** Hash türünü belirtin (örn. super-productivity için sha512).
    - **Hash doğrulama sorunları:** Eğer hash doğrulama başarısız olursa, hash'i manuel olarak JSON dosyasına ekleyebilirsiniz:
        - En son hash bilgisini GitHub sürüm sayfasında bulabilirsiniz (örn. [super-productivity releases](https://github.com/johannesjo/super-productivity/releases)).
        - Örnekler için [apps](src/my_unicorn/apps) klasörüne bakabilirsiniz.

# **🙏 Bu Projeye Destek Olun**

- **GitHub üzerinde yıldız ⭐** vererek desteğinizi gösterebilirsiniz, böylece kodlama yolculuğumda motive olmamı sağlar!
- **Test:** Eğer betiği test eder ve karşılaştığınız herhangi bir sorun hakkında geri bildirim sağlayabilirseniz harika olur.
- **💖 Projeyi Destekle:** Çalışmalarımı desteklemek ve projeler yapmaya devam etmemi sağlamak istersen, bana sponsor olmayı düşünebilirsin:
    - [![Sponsor Ol](https://img.shields.io/badge/Sponsor-💖-brightgreen)](https://github.com/sponsors/Cyber-Syntax)

## **🤝 Katkı Sağlama**

- Bu proje benim için öncelikle bir öğrenme kaynağıdır, ancak geri bildirim veya önerilerden memnuniyet duyarım! Tüm katkıları entegre etmeyi veya sürekli olarak katılım sağlamayı vaat edemem, ancak proje hedeflerine uygun iyileştirmelere ve fikirlere açığım.
- Yine de, daha ayrıntılı bir açıklama için lütfen [CONTRIBUTING.tr.md](.github/CONTRIBUTING.tr.md) dosyasına göz atın.

# **📝 Lisans**

Bu script, [GPL 3.0 Lisansı](https://www.gnu.org/licenses/gpl-3.0.en.html) altında lisanslanmıştır. Lisansın bir kopyasını [LICENSE](https://github.com/Cyber-Syntax/my-unicorn/blob/main/LICENSE) dosyasından veya [www.gnu.org](https://www.gnu.org/licenses/gpl-3.0.en.html) adresinden bulabilirsiniz.

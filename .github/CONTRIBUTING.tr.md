# **🤝 Katkı Sağlamayı Düşündüğünüz İçin Teşekkürler!**

Python öğrenmek amacıyla bir script yazmaya başladım, ancak zamanla daha fazla şey yapmayı öğrendikçe bu proje benim sevdiğim bir hale geldi. Başlangıçta bir öğrenme projesiydi, ancak şimdi benim için zaman kazandıran ve problem çözen bir Python projesi haline geldi, bu proje bana çok zaman kazandırdı.

## Yardımcı Olabilecek Şeyler

### **Nasıl Katkı Sağlayabilirsiniz:**

- **İyileştirme önerileri:** Script'i nasıl geliştirebileceğinizle ilgili fikirleriniz varsa, bir issue açarak ya da pull request göndererek katkı sağlayabilirsiniz.
- **Hata bildirimleri:** Herhangi bir sorun veya hata ile karşılaşırsanız, lütfen problemi detaylarıyla birlikte bir issue açarak bildirin.
- **Dokümantasyon:** Dokümantasyonu geliştirmeye yönelik katkılar her zaman kabul edilir.
- **Çeviriler**

### **Ne Bekleyebilirsiniz:**

- Katkıları ve önerileri, zamanım olduğunda inceleyeceğim, ancak bu projenin **kalıcı beta aşamasında** olduğunu ve zamanımın sınırlı olabileceğini unutmayın.
- Bu proje kişisel bir öğrenme projesi olduğundan, her katkının birleştirileceğini veya geniş bir geri bildirim sağlanabileceğini garanti edemem.

Katkı sağlamak isterseniz, lütfen bir pull request açmaktan veya bir tartışma başlatmaktan çekinmeyin. İlginiz için teşekkür ederim!

### **Yayın Mantığı (Release Logic):**

- Sürümler **release/vX.Y.Z-alpha** dallarında (branch) oluşturulacaktır ancak bazı sürümler, yeni bir dal oluşturmadan belirli bir sorun için acil bir düzeltme gerekiyorsa doğrudan **hotfix/** dallarında oluşturulabilir.
- GitHub Actions, depoya yeni bir etiket (tag) gönderildiğinde (push) otomatik olarak yeni bir sürüm oluşturacaktır. Etiket, ön sürüm versiyonları için `vX.Y.Z-alpha` (örneğin `v2.3.0-alpha`) ve kararlı sürümler için `vX.Y.Z` (örneğin `v2.3.0`) formatını takip etmelidir.
- Sürüm yükseltme (version bump) ve değişiklik günlüğü (changelog) güncellemesi şurada gerçekleşmelidir:
    - sürüm etiketinin oluşturulduğu dalda (hotfix/ veya release/)
- Sürümleme, ön sürüm versiyonlarını belirtmek için "alpha" son ekinin eklenmesiyle anlamsal sürümleme (semantic versioning) ilkelerini takip eder. Örneğin:
    - `v2.3.0-alpha`: Hala geliştirme aşamasında olduğunu belirten ön sürüm versiyonu.
    - `v2.3.0-beta`: Özelliklerin tamamlandığını ancak hala hatalar olabileceğini belirten ön sürüm versiyonu.
    - `v2.3.0-rc`: Üretime neredeyse hazır olduğunu ancak hala küçük sorunlar olabileceğini belirten sürüm adayı (release candidate).
    - `v2.3.0`: Üretim kullanımı için hazır olduğunu belirten kararlı sürüm.

### **Dal Mantığı (Branch Logic):**
>
> [!NOTE]
Çoğu PR (Pull Request) main dalına gider, ancak belirli bir sürüm için belirli bir sorunu hızlıca düzeltmek (hotfix) istiyorsanız, en son etiketlenen sürümden bir hotfix dalı oluşturabilir ve düzeltme uygulandıktan sonra bunu tekrar main dalına birleştirebilirsiniz. Ayrıca gerekirse acil düzeltmeler için bir hotfix dalı oluşturabilir ve bu daldan yeni bir etiket yayınlayabilirim.

- **main**:
    - Birincil geliştirme dalı.
    - Tüm yeni özellikler, hata düzeltmeleri ve iyileştirmeler main dalına birleştirilmelidir.
    - Sadece tamamlanmış, çalışan değişiklikler içerir, kısmi uygulamalar veya tamamlanmamış çalışmalar içermez.
    - Pull request'ler için inceleme ve onay gerektirir.
- **docs/**: Dokümantasyon dosyaları. Dokümantasyonu geliştirmeye yönelik katkılar memnuniyetle karşılanır.
- **feat/**: Yeni özellikler veya büyük değişiklikler için özellik dalları. Hazır olduklarında main dalına birleştirilmelidirler.
- **refactor/**: Yeni özellik eklemeyen kod iyileştirmeleri için yeniden yapılandırma (refactor) dalları. Bunlar da hazır olduklarında main dalına birleştirilmelidir.
- **fix/**:
    - main dalından oluşturulur.
    - Hotfix dalı gerektirmeyecek kadar acil olmayan hata düzeltmeleri içindir.
    - Tekrar main dalına birleştirilmelidir.
- **hotfix/**:
    - En son etiketlenen sürümden oluşturulur.
    - Yeni özelliklere izin verilmez.
    - main dalına ve (varsa) release dalına geri birleştirilmelidir.
    - Yalnızca bir sonraki sürüm dalının oluşturulmasını bekleyemeyecek kadar kritik düzeltmeler içindir.
    - GitHub Actions için sürüm oluşturmayı tetiklemek üzere `git tag vX.Y.Z` ve `git push origin vX.Y.Z` komutlarıyla dalda yeni etiket yayınlanır.
- **release/**:
    - main dalından oluşturulur.
    - Yeni özelliklere izin verilmez.
    - Yalnızca hata düzeltmeleri, sürüm yükseltmeleri ve sürüm hazırlığı içindir.
    - Sürümden sonra tekrar main dalına birleştirilmelidir.
    - GitHub Actions için sürüm oluşturmayı tetiklemek üzere `git tag vX.Y.Z-alpha` ve `git push origin vX.Y.Z-alpha` komutlarıyla dalda yeni etiket yayınlanır.

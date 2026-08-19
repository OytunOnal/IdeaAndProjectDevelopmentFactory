# Alternatif öğrenci-taban adayları (araştırma: 2026-08-15)

## SONUÇ — Aşama A koşuldu (15 Ağu, zero_shot_eval.py, 174-satır mühürlü eval)

| Model | P | R | Mod |
|---|---|---|---|
| base Qwen3-8B (Colab çıpası) | **0.24** | 0.67 | yarı evet-makinesi (~83 pozitif) |
| hermes3:8b | 0.15 | 0.13 | **blanket-refuser** (~26 pozitif, 4 kategoride sıfır) |
| selene-mini:8b (hakem-özel!) | 0.17 | 0.90 | evet-makinesi (~159 pozitif) |
| tulu3:8b (muhakeme-RL!) | 0.18 | 0.97 | evet-makinesi (~161 pozitif) |

**Karar: taban Qwen3-8B kalıyor.** Hiçbir aday sıfır-atışta base'i geçemedi; dördü de tek-taraflı moda
çöktü (Faz 3'ün "tek-taraflı politika salınımı" dersinin sıfır-atış hali). Hakem-eğitimli Selene bile
bizim dağılımda evet-makinesi — cevap-kalitesi rubriği ≠ bulgu-gerçekliği yargısı (dağılım uyuşmazlığı
tezi doğrulandı). Ayrım gücünü tek başına görev-SFT'sinin getirmesi bekleniyor → Kaggle eğitimi.
Cevap logları: data/zero_shot/*.jsonl

**Kapsam notu:** Bu yarış SADECE hakem görevini ölçtü. Dar geçişler için taban değişimi masada değil
(Faz 3'te Qwen'e kalibre edilip çözüldü; değişim = 6 geçişi yeniden ölçme bedeli). Extraction
(distilasyon hedefi #2, doğal recall %51) ayrı yarış ister: planted-defect recall metriğiyle, extraction
harness'i kurulunca aynı üçlü (hermes3/selene-mini/tulu3 — hepsi diskte) yeniden koşulacak.

Soru: Qwen3-8B yerine daha güçlü bir küçük taban, aynı train.jsonl ile daha iyi hakem verir mi?
Kısıtlar: 7-9B bandı (T4 QLoRA + lokal 6GB inference) · safetensors açık (GGUF-only eğitilemez)
· **Ollama'da koşabilmeli (üretim zinciri Ollama)** · lisans ticari-uyumlu.

## Kısa liste

| Aday | Taban | Durum | Not |
|---|---|---|---|
| **Selene-1-Mini-8B** (AtlaAI) | Llama-3.1-8B | ÖNCELİKLİ TEST | Hakem-özel eğitilmiş; RewardBench/Judge-arena 8B lideri, GPT-4o-mini'yi geçiyor. Hem sıfır-atış hakem hem adaptör-tabanı adayı. GGUF mevcut. |
| **Qwen3.5-9B** | — (yeni nesil) | BEKLEMEDE | Muhtemelen en güçlü sub-10B (Şub 2026); Unsloth fine-tune destekli AMA **GGUF'u Ollama'da çalışmıyor** (mmproj/vision dosya sorunu) → üretim engeli. Ollama desteği gelince yeniden değerlendir. |
| **Prometheus-2-7B** | Mistral-7B | DÜŞÜK ÖNCELİK | Hakem-özel ama 2024 modeli; Selene ony geçmiş durumda. |
| **DeepSeek-R1-Distill-8B** | Llama/Qwen | UYUMSUZ | Reasoning-tuned = uzun thinking ister; bizim tasarım think=False hızlı-hakem. Çelişiyor. |
| Qwen3-8B (mevcut) | — | BASELINE | Ollama+Unsloth sorunsuz; tüm Faz 3 ölçümleri bu ailede. |

## Genel-muhakeme odaklı topluluk/lab post-train'leri (kullanıcı kriteri: mantık + çok-adım, 15 Ağu)

| Aday | Taban | Ölçülmüş kazanç | Not |
|---|---|---|---|
| **Tulu 3.1 8B** (AllenAI) | Llama-3.1-8B | GSM8K 87.6 (SFT-only 76.2 → RL +11; taban Instruct'ı geçiyor) | EN GÜÇLÜ ADAY: tarif+veri tamamen açık, RLVR (doğrulanabilir ödül) = gerçek çok-adım kazancı, Ollama+Unsloth sorunsuz |
| **Hermes 3 8B** (Nous) | Llama-3.1-8B | Genelci iyileştirme iddiası; bağımsız kıyas karışık | Topluluk klasiği; kazançlar mütevazı, ölçmeden güvenme |
| **Arcee SuperNova-Lite 8B** | Llama-3.1-8B | 405B'den distill; kart-ölçümleri iyi | Distill-tabanı olarak ilginç |
| **OpenThinker / R1-distill ailesi** | Qwen/Llama | Büyük math/reasoning kazançları AMA uzun-thinking YOLUYLA | Bizim think=False tasarımla gerilim; ancak "hakemde thinking'i açmak" ayrı bir deney kolu olabilir (gecikme bedeliyle) |

**Adaptör-only arama sonucu (dürüst bulgu):** HF'te bağımsız LoRA olarak yayınlanan işlerin ezici çoğunluğu
stil/domain/sansür-kaldırma; **genel muhakemeyi kanıtlanmış şekilde yükselten yayın kalitesindeki işler merge
edilmiş tam ağırlık olarak çıkıyor** (Tulu/Hermes gibi) — çünkü LoRA-only çok-adım muhakemeyi nadiren taşıyor
ve adaptör zaten tabana kilitli. Yani "hazır adaptör al" değil "iyi post-train'lenmiş tabanı al, KENDİ
adaptörünü üstüne eğit" doğru hamle.

**Qwen3-8B-abliterated / Josiefied türevleri:** kriter dışı — abliteration ret-kaldırma işlemidir,
muhakeme eklemez; yes-sayer riski notu aynen geçerli.

## Protokol (Colab koşu #2 SONRASI — taban değişikliği 3. koşunun sorusu)

1. **Aşama A (ucuz, bu makine):** Selene-Mini GGUF'unu Ollama'ya çek → 174-satır eval'i sıfır-atış koş
   (lokal runner: eval.jsonl promptlarını Ollama'ya besle, aynı regex parse). Kıyas: base-Qwen3-8B P0.24/R0.67.
2. **Aşama B (1 Colab oturumu):** A'da umut veren taban + aynı train.jsonl → QLoRA → aynı eval.
   Adaptörler yarışır; kazanan sayıyla belli olur.
3. Sıfır-atış iyi çıksa bile kalibrasyon kuralları (kendini-yalanlayan=false vb.) eğitimsiz gelmez —
   gerçekçi en-iyi senaryo "daha güçlü taban", "hazır hakem" değil.

## Linkler

- Tulu 3.1 8B: https://huggingface.co/allenai/Llama-3.1-Tulu-3.1-8B (v3: /allenai/Llama-3.1-Tulu-3-8B)
- Selene-1-Mini: https://huggingface.co/AtlaAI/Selene-1-Mini-Llama-3.1-8B (+ aynı repo adı -GGUF ekiyle)
- Hermes 3 8B: https://huggingface.co/NousResearch/Hermes-3-Llama-3.1-8B (+ -GGUF)
- SuperNova-Lite: https://huggingface.co/arcee-ai/Llama-3.1-SuperNova-Lite
- OpenThinker ailesi: https://huggingface.co/open-thoughts
- Mevcut taban: https://huggingface.co/Qwen/Qwen3-8B (eğitimde: unsloth/Qwen3-8B-unsloth-bnb-4bit)
- Qwen3.5-9B (beklemede): https://huggingface.co/unsloth/Qwen3.5-9B-GGUF

## Uyarılar (DavidAU-tipi topluluk merge'leri için)

- Kart benchmark'ları yayıncının kendi ölçümü; tek-adım seçim testleri (ARC/BoolQ/HSWAG) çok-adım
  üretimi yordamaz (LittleLamb dersi: BoolQ +9.3 iken GSM8K −16.5 mümkün).
- Uncensored/compliance-artırıcı tune'lar hakem için ters kas (yes-sayer riski).
- Merge kontaminasyonu endemik; bağımsız ölçüm yoksa kendi eval'imiz tek hakem.

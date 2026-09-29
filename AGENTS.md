# Útmutató és Szabályzat Fejlesztő AI Ügynökök Számára (AGENTS.md)

Ez a fájl kötelező érvényű irányelveket és szabályokat tartalmaz minden olyan AI kódoló asszisztens (Agent) számára, amely a **slideshowGenerator** kódbázisán dolgozik.

---

> [!CAUTION]
> ### 🚨 KÖTELEZŐ DOKUMENTÁCIÓS KARBANTARTÁS (MANDATORY RULE)
> **Minden AI ügynök köteles a `docs/` mappában található dokumentációt naprakészen tartani!**
> 
> Ha bármilyen módosítást végzel a rendszeren:
> 1. Új funkciót adsz hozzá vagy meglévőt módosítasz,
> 2. Változtatsz a CLI paramétereken, adatmodelleken (`models.py`) vagy a parser viselkedésén,
> 3. Módosítod a stílusmotort (`theme_engine.py`) vagy a renderelőket (`renderers/`),
> 4. Hibát javítasz (bugfix) vagy új formátumot vezetsz be,
> 
> **KÖTELES VAGY AZONNAL FRISSÍTENI:**
> * A [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) fájlt (architektúra, komponensek, adatfolyam), ÉS
> * A [`docs/DECISIONS.md`](docs/DECISIONS.md) fájlt (új ADR vagy döntési bejegyzés formájában indokolva a változtatást).
> 
> **TILOS olyan kódot átadni a felhasználónak, amely eltér a dokumentációtól, vagy elavulttá teszi azt!**

---

## 🏛️ Alapvető Architektúrális Elvek

1. **Három formátum elve (PPTX, HTML, PDF):**
   * Minden módosításnak tiszteletben kell tartania a három egyenrangú célformátumot.
   * Ha új vizuális elemet vezetsz be, azt mind a webes (`html_renderer.py`), mind a PowerPoint (`pptx_renderer.py`), mind a PDF (`pdf_renderer.py`) kimeneten konzisztensen meg kell valósítani.

2. **Standalone Webes Lejátszó (Zero-Dependency):**
   * Az `index.html` önállóan, hálózati kapcsolat nélkül is működőképes kell, hogy maradjon.
   * A hangfájlokat kötelező Base64 adatfolyamként közvetlenül beágyazni a HTML-be, megelőzve a helyi `file:///` biztonsági korlátozásokat és relatív útvonalhibákat.
   * Az `ffmpeg` alapú MP3 transzkódolást és a többszintű fallbacket meg kell őrizni.

3. **Deklaratív JSON Témák:**
   * A prezentációk kinézetét nem szabad a generáló logikába bedrótozni.
   * A stílusokat a `generator/themes/*.json` fájlok és a `schema.json` vezérli.
   * Meg kell őrizni az AI általi stílusgenerálhatóságot (`--ai-theme`).

4. **Azonnali Port-újrahasznosítás:**
   * A webszerver indításakor kötelező a `ReusableTCPServer` használata (`SO_REUSEADDR`, `SO_REUSEPORT`), hogy `Ctrl + C` után a port azonnal újraindítható legyen.

5. **Verziókezelési fegyelem:**
   * A `dist/` almappák generált tartalmak, **soha nem kerülhetnek be a Git repóba** (lásd `.gitignore`).
   * A `slideshow_1` mappa működő referenciapéldaként szolgál, a benne lévő forrásokat (`slides.md`, `slide_title.m4a`) meg kell őrizni.

---

## 🧪 Kötelező Ellenőrzési Lépések Módosítás Után

Mielőtt befejeznéd a feladatodat, futtasd le a következő teszteket:

```bash
# 1. Generálás ellenőrzése
./run.py slideshow_1

# 2. PPTX struktúra és beágyazott média ellenőrzése
.venv/bin/python -c "from pptx import Presentation; prs = Presentation('slideshow_1/dist/presentation.pptx'); assert len(prs.slides) == 4"

# 3. Témák listázásának és egy alternatív téma generálásának ellenőrzése
./run.py --list-themes
./run.py slideshow_1 --theme dark_mode

# 4. Dokumentáció frissítésének ellenőrzése
git status
```

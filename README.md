# Slideshow Generator 🎬🎙️

Professzionális prezentációgeneráló motor, amely Markdown vázlatokból és csatolt hangfájlokból automatikusan előállítja a prezentációt három különböző formátumban:
1. **PowerPoint (.pptx)**: 16:9 arányú prezentáció, beágyazott natív médiaobjektummal (kattintásra induló hangfelvétellel).
2. **Interaktív Webes diavetítő (.html)**: Bármilyen böngészőben futó, reszponzív HTML5 lejátszó modern kártyás elrendezéssel, billentyűzet-vezérléssel és diszkrét lejátszó/szüneteltető hangvezérlővel.
3. **Vektoros PDF (.pdf)**: Pixelpontos, 16:9 képarányú, nyomtatható és prezentálható PDF változat.

---

## 🚀 Gyorsindítás

A generátor önállóan kezeli a virtuális környezetet (`.venv`), így közvetlenül futtatható:

```bash
# Slideshow-1 legenerálása az alapértelmezett (modern_clean) stílussal:
./run.py slideshow_1

# Másik témával történő generálás:
./run.py slideshow_1 --theme dark_mode

# Csak adott formátumok készítése (pl. csak PPTX és PDF):
./run.py slideshow_1 --format pptx,pdf

# Az elkészült prezentáció megtekintése beépített webszerverrel:
./run.py slideshow_1 --serve 8080
```

A generált fájlok a diasor forrásmappáján belüli `dist/` almappába kerülnek:
* `slideshow_1/dist/presentation.pptx`
* `slideshow_1/dist/index.html`
* `slideshow_1/dist/presentation.pdf`
* `slideshow_1/dist/slide_title.m4a` (önálló lejátszáshoz kimásolva)

---

## 📝 A Diasor Formátuma (`slides.md`)

A diák elválasztása `# Title`, `# Slide` vagy `---` sorokkal történik. A hangfájlokat egyszerű HTML megjegyzéssel tudod hozzárendelni az adott diához:

```markdown
# Title
<!-- audio: slide_title.m4a -->
A pisa meres eredmenyenek ertekelese.

Boncz Zoltan

# Slide
A PISA-vizsgálat értelmezésében a matematikai műveltség...

# Slide
A mérés a matematikai ismereteket négy átfogó kategóriába csoportosítja:

- Mennyiség (Quantity): számolás, mértékegységek, arányok...
- Változás és összefüggések (Change and relationships): függvények, modellezés...
```

* **Címdia**: Automatikusan felismeri a címet és az előadót.
* **Definíciós dia**: A hosszabb folyószövegeket elegáns, kiemelt definíciós kártyaként jeleníti meg.
* **Kártyás dia**: A `- Név: Leírás` pontokat modern információs kártyákká és számozott jelvényekké alakítja.

---

## 🎨 Moduláris Stílusok (Themes) és AI Témagenerálás

A prezentációk vizuális világa teljesen független a tartalomtól. A stílusok a `generator/themes/` mappában található egyszerű JSON fájlok.

### Elérhető témák listázása:
```bash
./run.py --list-themes
```

Beépített témák:
- `modern_clean`: Világos, modern kártyás stílus kék hangsúlyokkal (alapértelmezett)
- `dark_mode`: Prémium sötétszürke háttér indigókék akcentussal
- `emerald_growth`: Természetes, tiszta smaragdzöld stílus
- `warm_academic`: Meleg krémszínű és bordó akadémiai dizájn

### Új téma generálása AI-val:
Új stílust közvetlenül parancssorból is generálhatsz egyetlen szöveges leírás megadásával:
```bash
./run.py --ai-theme "Cyberpunk sötét neon stílus lila és ciánkék színekkel"
```
A generátor azonnal létrehozza az új stílust a `generator/themes/` mappában, amit rögtön használhatsz:
```bash
./run.py slideshow_1 --theme cyberpunk_sotet_neon
```

Ha saját magad vagy külső chatben (ChatGPT, Claude) szeretnél témát generáltatni, használd a [`generator/themes/THEME_PROMPT.md`](generator/themes/THEME_PROMPT.md) fájlban található kész promptot!

---

## ⌨️ Webes Diavetítő Billentyűparancsok

A `dist/index.html` megnyitásakor:
* **Következő dia**: `Jobbra nyíl` (`→`), `Szóköz`, vagy `PageDown`
* **Előző dia**: `Balra nyíl` (`←`) vagy `PageUp`
* **Első / Utolsó dia**: `Home` / `End`
* **Teljes képernyő**: `F` billentyű
* **Hanglejátszás**: Kattintás a dia fejlécében található **Narráció** gombra.

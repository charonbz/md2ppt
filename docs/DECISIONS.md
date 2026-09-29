# Lényegesebb Implementációs Döntések (Architecture Decision Records)

Ez a dokumentum rögzíti a Slideshow Generator fejlesztése során meghozott legfontosabb technológiai és architektúrális döntéseket, azok hátterét és indoklását.

---

## ADR-001: Determinisztikus Kódmotor vs. Közvetlen AI Generálás

### Kontextus
Felmerült a kérdés, hogy magát a prezentációt (PPTX, PDF fájlokat) közvetlenül az AI modell állítsa-e elő, vagy egy dedikált programozott kódmotor.

### Döntés
A végleges prezentációs fájlokat egy determinisztikus Python kódmotor állítja elő, míg az AI feladata a kódmotor megtervezése, sablonok és stílusok készítése, valamint opcionálisan a diaszövegek tartalmi strukturálása.

### Indoklás
- A PowerPoint (`.pptx`) egy szigorú OpenXML szabványt követő ZIP archívum bináris médiafájlokkal és XML kapcsolatokkal (`_rels`).
- A PDF szintén egy bináris grafikai adatfolyam.
- Az LLM-ek szöveges interfészen keresztül kommunikálnak, bináris PPTX és PDF fájlokat közvetlenül lebegőpontos byte-okként megbízhatóan nem tudnak kiadni.
- A kódmotor 100%-ban megbízható, tizedmásodpercek alatt fut le, és garantálja a pixelpontos, hibátlan reprodukálhatóságot.

---

## ADR-002: Három Célformátum Együttes Támogatása (PPTX, HTML, PDF)

### Kontextus
A diasorhoz hangfelvétel tartozik, a felhasználó által preferált formátum a PDF volt. Ugyanakkor a modern PDF nézegetők (böngészők, okostelefonok, Linux Evince) biztonsági okokból már nem játsszák le a beágyazott audiót (ez szinte kizárólag az asztali Adobe Acrobat Readerben működik).

### Döntés
A rendszer egyszerre három kimenetet állít elő:
1. **PowerPoint (`presentation.pptx`)**: Natív médiatámogatás asztali és mobil PowerPointban.
2. **Webes HTML (`index.html`)**: Univerzális, bármilyen böngészőben futó interaktív lejátszó.
3. **Vektoros PDF (`presentation.pdf`)**: Szabványos, nyomtatható és kivetíthető statikus diasor.

### Indoklás
Így minden felhasználási forgatókönyv le van fedve: a hangos előadás megbízhatóan működik PowerPointban és weben, a PDF pedig biztosítja a klasszikus dokumentum-megosztást.

---

## ADR-003: Standalone Webes Prezentáció Base64 Audió Beágyazással és MP3 Konverzióval

### Kontextus
Az `index.html` helyi megnyitásakor (`file:///` protokoll) a tesztelés során lejátszási hiba lépett fel. Két probléma merült fel:
1. A Samsung telefonok Voice Recorder alkalmazása `.m4a` kiterjesztéssel, de belső `3gp4` (3GPP) médiakonténerrel menti a hangot, amit sok asztali böngésző nem képes dekódolni.
2. A böngészők szigorú "Local File Restrictions" (sandbox) szabályai `file:///` megnyitás esetén korlátozzák a relatív fájlelérést.

### Döntés
- A generátor a háttérben az `ffmpeg` segítségével automatikusan előállít egy univerzális `.mp3` fájlt is.
- A hangfájlt **Base64 adatfolyamként (`data:audio/mpeg;base64,...`) közvetlenül beágyazza a HTML fájlba**.
- A HTML `<audio>` tag háromszintű tartalékot (fallback) biztosít: Base64 MP3 -> relatív MP3 fájl -> relatív M4A fájl.

### Indoklás
A HTML fájl 100%-ban önállóvá (standalone) vált. Bárhová másolható, pendrive-ról vagy email mellékletként is azonnal megszólal, nulla külső függőséggel.

---

## ADR-004: Deklaratív JSON Témarendszer és AI Témagenerálás

### Kontextus
A diasor vizuális stílusát (színek, kártyák, betűtípusok) el kell különíteni a tartalomtól, és biztosítani kell, hogy a felhasználó vagy az AI könnyedén hozzáadhasson új stílusokat.

### Döntés
- A témák a `generator/themes/*.json` fájlokban találhatók, JSON Schema (`schema.json`) által definiálva.
- Készült egy `theme_generator.py` modul és egy `--ai-theme "leírás"` CLI parancs, amely Gemini API-val vagy kulcsszó-alapú algoritmikus palettaszintézissel képes új stílust generálni.
- A `THEME_PROMPT.md` sablon segítségével bármely külső AI modell (Claude, ChatGPT) azonnal kompatibilis témát tud generálni.

### Indoklás
A fejlesztőknek és felhasználóknak nem kell Python kódot írniuk egy új stílushoz: elég egyetlen JSON fájl vagy egy prompt.

---

## ADR-005: Folytonos Kártyaszámozás Többoldalas Kategóriáknál

### Kontextus
A PISA felmérés 4 főkategóriáját a forrás `slides.md` két külön diára bontotta (2-2 kategória diánként). Korábban mindkét dián `01, 02` jelent meg a kártyák fejlécében.

### Döntés
A `parser.py` belső állapota nyilvántartja a folytonos kártyaszámlálót. Egymást követő kártyás diák esetén az index nem nullázódik le, hanem folytatódik (`01, 02` majd `03, 04`).

### Indoklás
Logikailag és vizuálisan egyértelművé teszi a néző számára, hogy ugyanannak a 4 elemű kategóriarendszernek a folytatásáról van szó.

---

## ADR-006: Reusable TCP Webszerver (`SO_REUSEADDR` & `SO_REUSEPORT`)

### Kontextus
A beépített fejlesztői webszerver leállítása (`Ctrl + C`) után a port percekig foglalt maradt (`[Errno 98] Address already in use`).

### Döntés
A `generator/cli.py`-ban egyedi `ReusableTCPServer` osztály került bevezetésre, amely a socket létrehozásakor beállítja a `SO_REUSEADDR` és `SO_REUSEPORT` kernel flag-eket, és leálláskor expliciten meghívja a `server.server_close()` metódust.

### Indoklás
Megszünteti a Linux TCP `TIME_WAIT` várakozási idejét, így a szerver azonnal és hibamentesen újraindítható ugyanazon a porton.

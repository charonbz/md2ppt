# AI Téma-generáló Útmutató (AI Theme Generator Prompt)

Ha új prezentációs stílust szeretnél készíteni bármilyen AI-val (pl. Antigravity chatben, Claude-ban vagy ChatGPT-ben), másold be az alábbi prompt sablont, és egészítsd ki a saját stílusigényeiddel:

---

```markdown
Készíts egy új témát a slideshowGenerator rendszerhez az alábbi JSON formátumban!
Téma elképzelés: [Írd ide a kívánt hangulatot, pl.: "Skandináv minimalizmus, fagyos kék és pala-szürke színekkel" vagy "Futurisztikus neon cyberpunk sötét háttérrel"].

A válaszban KIZÁRÓLAG egy érvényes JSON blokkot adj meg az alábbi séma szerint:

{
  "id": "egyedi_azonosito_kisbetuvel_aláhúzással",
  "name": "Emberileg olvasható név",
  "description": "Rövid leírás a stílusról",
  "colors": {
    "background": "#HEX háttérszín",
    "card_bg": "#HEX kártya háttér",
    "card_border": "#HEX kártya szegély",
    "primary_text": "#HEX fő szövegszín (erős kontraszt a card_bg-hez)",
    "secondary_text": "#HEX másodlagos szövegszín",
    "accent": "#HEX kiemelő szín (gombok, címkék, ikonok)",
    "accent_light": "#HEX nagyon világos / áttetsző akcentusszín",
    "badge_bg": "#HEX kategória jelvény háttérszín",
    "badge_text": "#HEX kategória jelvény szövegszín",
    "audio_btn_bg": "#HEX audio lejátszó gomb háttérszín",
    "audio_btn_text": "#HEX audio lejátszó gomb szöveg/ikonszín"
  },
  "fonts": {
    "title_font": "Betűtípus a címekhez (pl. system-ui, Georgia, Montserrat, stb.)",
    "body_font": "Betűtípus a folyószöveghez (pl. system-ui, Roboto, Open Sans)"
  },
  "styles": {
    "card_radius_px": 16,
    "card_shadow": "0 10px 25px -5px rgba(0, 0, 0, 0.08)",
    "title_align": "left",
    "border_width_px": 1
  }
}
```

A kapott JSON fájlt mentsd el a `generator/themes/<id>.json` néven, és a generátor azonnal használni tudja a `--theme <id>` paraméterrel!

# Design reference

`modernist-reference.css` is the token/component sheet extracted from the owner-supplied
"Poly Redesign" mockup (Archivo, editorial layout, zero radius, hairline rules). The live
implementation is `frontend/src/app/globals.css`, which derives every color from the brand
variables (Settings → Brand) instead of the mockup's red/ink palette.

## Rendered output (shorts, carousels, cards)

The screen design and the exported design are one system. `backend/poly/services/design.py`
holds the tokens and primitives; `render_scene.py` composes a scene from them.

**Type.** `backend/poly/assets/fonts/Archivo-*.ttf` are static instances cut from the same
variable font the interface loads, so an exported slide and the app are set in one typeface.
Pillow has no letter-spacing, so `draw_tracked` steps glyph by glyph for the small-caps labels.

**Color.** Everything derives from the brand tokens (Settings → Brand): `ink`, `paper`,
`accent`, `highlight`, `slate`. `ink_for()` resolves foregrounds against whatever surface a
scene lands on and swaps out any mark that would be invisible against it — which is why a teal
slide doesn't draw teal bars.

**Surfaces.** No flat fills: every surface is a gradient with a soft radial light and a whisper
of grain. Flat digital color is what makes a slide look unfinished.

**Roles.** Each scene gets a role — `cover`, `point`, `stat`, `chart`, `contrast`, `quote`,
`list`, `timeline`, `image`, `question`, `closer` — which sets the composition: type scale,
alignment, anchor, decoration, and where the data visual goes. The surface follows the role
and a deck-wide rhythm, so consecutive slides never look identical. A surface a person picks
in the editor sets `surface_locked` and wins over the rhythm.

**Two layers.** `compose_base` draws the plate (surface, furniture, visual); `compose_text`
draws headline and body into an RGBA layer. Stills composite them; video overlays the text
layer with its own motion over a slow drift on the plate. So the typography in the export is
the typography the editor showed — the old renderer restyled the text as subtitles and the two
never matched. Counters keep an ASS pass, since a number counting up has to be drawn per frame.

**Copy hygiene.** `clean_headline` repairs the mangled casing models produce ("THE APOLogy"),
`sanitize` drops glyphs the font can't draw (arrows are drawn as shapes instead of tofu), and
`fit` refuses any size at which a word would have to be split — the wrapping bug that used to
run text off both edges of the frame.

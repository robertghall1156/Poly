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

## Pictures

`services/imagery.py` resolves a scene's visual intent into an actual picture, in a fixed
order: a picture already chosen → the existing library → an openly-licensed photograph →
a locally-generated editorial illustration → a symbolic mark. Two rules are not settings:

1. **Only republishable licenses are downloaded.** `providers/image_search/` returns nothing
   without a license and an author — public domain, CC0, CC BY and CC BY-SA only. NC and ND
   are rejected, since a slide crops and tints what it shows. The license and photographer
   are stored with the file and printed on the slide.
2. **Generated pictures of real people are cartoons, and say so.** `illustration_prompt`
   strips the photoreal vocabulary rather than balancing against it, the negative prompt
   pushes the other way, and the renderer prints "AI-generated illustration" on any scene
   built from one. A labelled photoreal fake still travels as evidence once it leaves the app,
   so Poly does not make one.

### Which picture

The subject of a picture is taken from the **story**, not from the slide (`services/subjects.py`).
A headline like "WHY DOES TRUMP'S FOCUS MATTER?" is an abstraction, and searching those words
returns whatever a picture archive's full-text index associates with them — which is how a deck
about a president got illustrated with a historian who writes about him, and a line about
Congress got a church in Toronto.

So `extract()` ranks the named people, places and buildings across the story's reporting by how
much of the coverage carries them (document frequency, not repetition), `for_scene()` picks the
one a given scene names — falling back to the deck's lead for abstract slides and resolving
"his arch" to the lead person — and `thing_in()` adds the concrete object, so the search is
"Trump arch", never "TRUMP FOCUS MATTER".

Then `score_candidate()` **rejects** anything whose title does not contain every significant word
of the subject's name. Sharing one word is not depicting: "St. Andrews Church, Toronto, Ontario"
does not illustrate Lake Ontario. A wrong picture is worse than no picture, because the reader
believes it — so a scene with no good candidate falls back to a symbol or stays as type.

A picture Poly chose is marked `auto` and is replaced on the next run if the subject changed;
a picture attached by hand in the editor is never touched.

`services/symbols.py` draws the concept when no honest photograph exists: `rename` (old name
struck through, new one stamped over it), `stamp`, `plaque`, `seal`, `scale`, `signature`.
These need no network and carry no licensing risk, and for an act — a renaming, a signing, a
name placed on something — they state the point more precisely than a photo of a man at a desk.
`infer_symbol` proposes one from words already in the copy; it never invents a name or a figure.

Pictures are placed by `treatment`: `full_bleed` (the picture becomes the frame, duotoned into
the palette under a scrim, type set low over it — the cover treatment), `band` (inside the
layout), `portrait`.

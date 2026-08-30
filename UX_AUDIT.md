# Poly — UX Audit & Redesign (2026-08-30)

Reviewed as a product designer would review a new prosumer app. The verdict on v1: the engine is
strong, but the UI is an *admin panel for the database* rather than a tool organised around what the
owner is trying to do. Every finding below is paired with the change made in this pass.

## Problems found

1. **Navigation models the schema, not the job.** 12 equal sidebar items (Home, Today, Stories,
   Think, Principles, Research, Content, Videos, Book, Calendar, Analytics, Settings). Users must
   already know that "a Story becomes a Brief becomes a Content Item" to move around.
2. **Internal vocabulary in the UI.** "Position Brief", "Principle", "ContentItem status
   POSITION_DEVELOPED", "dashboard_action", "fact_check_status: overridden" appear verbatim.
3. **Creation starts from objects, not formats.** To make anything you navigate to a story/brief and
   open a dialog with 6 fields (format, story, brief, principles, title, instructions). No visual
   format picker; no way to start from "I want a Short".
4. **Too many clicks.** Home → new content draft was 6–8 clicks; story → content 5–6.
5. **Duplicated surfaces.** Today ≈ Home§Today; Research page is three unrelated admin tables;
   content generation exists in four variants.
6. **No universal entry point.** Nothing like "+ Create" available everywhere.
7. **Configuration before value.** The generate dialog asks for principles and instructions before
   producing anything; AI should infer and the user should edit afterwards.
8. **Review is scattered.** Fact check, status change, script, caption and export live in different
   panels of a long detail page; there is no single "is this good? approve → export" screen.
9. **Prominence ≠ frequency.** Analytics/Book/Research get the same visual weight as Home.
10. **No brand system.** Colors hard-coded in Tailwind classes; two hex fields hidden in Settings.

## Changes implemented in this pass

1. **Navigation reduced to six primary areas + two secondary:**

   | Before (12 equal) | After |
   |---|---|
   | Home, Today, Stories, Think, Principles, Research, Content, Videos, Book, Calendar, Analytics, Settings | **Home · Discover · Think · Create · Library · Calendar** — with Settings & Analytics in a quiet secondary group |

   - **Discover** = Today's stories + full story list + research notes/sources/feeds (tabs).
   - **Think** = My ideas (sessions), My positions (briefs), My beliefs (principles → "What I believe").
   - **Create** = format-first studio: Short / Faceless Video / Meme / Carousel / Post / YouTube /
     Podcast / Article, plus the faceless editor and review screens.
   - **Library** = past content, videos, images, book, documents.
   Old routes redirect so bookmarks keep working.
2. **Plain language everywhere.** "Position Brief" → "My position", "Principles" → "What I believe",
   "Content item" → "Draft", statuses shown as "Drafting / Editing / Ready / Published",
   "fact-check overridden" → "Approved with a note". Internal names remain in the API/database.
3. **Universal "+ Create" launcher** in the top bar on every page: Make a Short, Make a Meme, Make a
   Faceless Video, Make a Social Post, Make a Carousel, Make a YouTube Video, Make a Podcast,
   Upload a Video, Think Through an Issue, Research Something.
4. **"Create From This" on every important object** (story, position, belief, research note, video,
   document) opening the same format picker with the source pre-attached.
5. **Create → good first draft → edit.** The faceless flow is source → style → length → Generate
   (length defaults to 30s, style defaults by source). Everything else — hook, structure, pacing,
   caption, hashtags, visuals — is inferred and editable afterwards. Home → faceless Short draft is
   **3 clicks** (+ Create → Make a Short → Generate).
6. **One unified editor** for faceless videos/carousels: scenes left, live preview centre,
   properties right; regenerate/add/delete/reorder scenes; advanced controls collapsed.
7. **One review screen** per draft: preview, title, caption, sources, fact check → Edit / Approve /
   Export. Nothing publishes automatically.
8. **One-click variations** (Shorter, More direct, More curious, More educational, More humorous,
   More serious, Simpler, Stronger hook, Change visual style) on any draft.
9. **Home = command centre** answering exactly four questions — What happened? What should I think
   about? What can I create? What am I working on? — plus one "Get today's news" action. Counts,
   ingest internals and feed errors moved off Home.
10. **Brand tokens centralised** (`brand` settings key → CSS variables + renderer palette): deep
    navy `#102A43`, teal `#0F766E`, slate `#52667A`, warm off-white `#F8F9FA`, muted gold `#C89B3C`.
    Editable in Settings → Brand; no hard-coded colors in new components or renderers.

## Click-count results (after)

| Flow | Before | After |
|---|---|---|
| Home → faceless Short draft | n/a (didn't exist) | 3 clicks (+ Create → Make a Short → Generate) |
| Story → content draft | 5–6 | 2–3 (Create From This → format → Generate) |
| Position → meme concepts | n/a | 3 (Create From This → Meme → Generate) |
| Draft → reviewed & exported | scattered | 3 on one screen (Review → Approve → Export) |

## 30-second comprehension test

A first-time user on Home now sees, in order: what Poly is (one-line masthead), what happened today
(stories), what to think about, what to create (one click each), and what they're working on — with
a single global "+ Create" button. Terminology test: no internal object names appear on Home,
Discover, or the Create flow.

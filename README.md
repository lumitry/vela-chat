# VelaChat

![VelaChat Logo](https://raw.githubusercontent.com/lumitry/vela-chat/refs/heads/main/static/static/favicon-96x96.png)

VelaChat is an opinionated fork of Open WebUI 0.6.5 designed to provide a more performant and user-friendly experience.

Note: Do not use this fork with an Sqlite database! It will probably break things! Postgres is simple to set up and very fast. The migration isn't particularly difficult in my experience. See [MIGRATE_SQLITE_TO_PSQL.md](utils/sqlite_to_postgres/MIGRATE_SQLITE_TO_PSQL.md) for more details.

> **⚠️ WARNING**
>
> **Before installing or upgrading VelaChat, please back up your Postgres database and your `backend/data` directory (or Docker volume) first!**
>
> Some of the migrations in VelaChat have a risk of data loss or database changes that cannot be easily reversed. Always keep backups of your database and any important data before proceeding with installation or updates!

## Deployment Recommendations

- Docker Compose
- Use Postgres for the database
- ChromaDB is fine for single-user deployments
- Use a reverse proxy like Nginx or Caddy to serve the app. Nginx has worked great for me.
- Tailscale.
- Seriously. Please use Tailscale, it's awesome.
- `tailscale cert` to get a certificate -> reverse proxy -> SSL -> HTTPS -> HTTP/2 -> faster loading times! Also access to more browser APIs like clipboard, notifications, etc.
- There are also many other ways to get HTTPS, but Tailscale has lots of other advantages so I really like it.
- I use LiteLLM to proxy external models with a custom patch to pass through cost usage info, but this is mostly unnecessary now that we've got metrics supported natively in VelaChat. I only keep it around because it's nice to have a log of requests and responses to debug issues.

Dev environment:

- VSCode remote ssh to my server (which means I can experience actual latency/perf issues firsthand)
- The database is a Postgres-migrated version of my actual production database (the 2GB Sqlite database I mention in several places) with 15k messages. In other words, it is a real-world scenario with a lot of actual data and edge cases.
- I bounce back and forth between firefox and chrome. Both have devtools with varying degrees of oddity. Chrome doesn't tell you the HTTP method in the overview by default and doesn't let you search response/request JSON for single requests. Firefox has a worse waterfall that's never the right size. No need to pick your poison - ¿por que no los dos?
- I mostly use external models for testing, lately Gemini 2.5 Flash Lite Preview because when I'm testing, I don't want to break flow waiting for a 10 tps free model or an Ollama cold start. 300+ TPS for cheap prices is pretty nice.

## Performance

_(TODO: add gifs/videos showcasing perf and UI improvements! And screenshots of new UI features!)_

The original goal of VelaChat was to make the app more performant without sacrificing features. Notably, the same chat that used to take me 30 seconds to load now takes around a second to load. The journey to get there is documented below...

Current performance wins include:

- Defer loading of the sidebar until after the chat has loaded, improving effective load times (since the sidebar is rarely the first thing a user interacts with).
- Improved speed of `/api/v1/folders/` endpoint by streamlining the database query to avoid an N+1 query problem.
  - I measured 7084ms for the old query (running via Docker with Postgres DB; it took 11.75 seconds for an equivalent Sqlite DB) vs 135ms (running via `npm run dev` with Postgres DB) for the new query with 30 folders in my personal database, which is a 50x improvement.
  - In the real world, this gave me a ~2x improvement in page load time for a chat I've been using for testing, from 30 seconds to 14 seconds.
  - The next bottleneck for page load times is the `/api/models` endpoint, which takes 10 seconds to load and blocks the UI. Fix is ~~WIP~~ DONE!
- Improve performance of the `/api/models` endpoint (no `/v1/` in the slug, that's a different endpoint) by optimizing for large model counts (without caching!).
  - I managed to reduce the time it takes to load the models from around 11 seconds to under a second, but this isn't necessarily a like-for-like comparison so take it with a grain of salt. What I can say is that it now takes ~4 or 5 seconds to load the same page that used to take 30, and then 14 (after the `/api/v1/folders` change above).
- (perf) Serve images via URL, not base64, to reduce payload size, database size, and improve general performance. (See [#2](https://github.com/lumitry/vela-chat/issues/2) and its sub-issues.)
  - Existing databases will automatically be migrated! In case it wasn't obvious, you should DEFINITELY back up your database before upgrading!
- (perf) Defer loading of model images. ([#23](https://github.com/lumitry/vela-chat/issues/23))
- (perf) Defer loading of models list
- (perf) Normalized the database schema to store chat messages in a normalized manner, rather than as a single JSON blob nested inside the chat object. This should massively improve performance and reduce database size. See [#71](https://github.com/lumitry/vela-chat/pull/71) for more details.
- (perf) Cache the messages in IndexedDB to improve performance when navigating between chats.
- (perf) Don't bother loading in-chat images until after the chat itself has loaded. ([#26](https://github.com/lumitry/vela-chat/issues/26))
- (perf) Lazy-load or allow disabling of TTS features; I personally don't use them, and Kokoro TTS is 2MB of JS that doesn't need to be loaded. (I'm also not sure if Transformers.JS is being used for anything else; that's another 800KB.)
- (perf) Make evaluations leaderboard page load much quicker by removing full chat snapshots from the feedback table.
- (perf) Chat search feature now uses full-text search on the chat messages table, which is vastly faster than the previous implementation. It used to take me 9 seconds for my 15k messages database, and now it takes 50ms. Casual 225x performance improvement, only possible because of the normalization of the chat messages table!
- Model editor loads much faster due to optimized knowledge base lookups.
- Loading workspace pages has been greatly optimized by only getting the necessary metadata.
- Chat prefetching has been removed because it was slower due to hammering the DB (note: now that we've got IndexedDB caching implemented, it might be worth it in the long run to do this! But only for the initial load of messages into the IDB table.)
- RAG metadata storage has been greatly deduplicated, turning a RAG-heavy chat from 18.13MB of JSON to ~2MB (all before GZIP and not factoring in that the messages themselves are now cached).
- We no longer send the full text content of each message in the current branch twice. We send text content, RAG `sources`, and user-attached `files` only in the `history.messages` objects, NOT in the `messages` array. The frontend just performs a simple join operation.
- Further optimized the models endpoint to fetch ollama models and openai models in parallel with one another.
- Parallelized web search to a greater degree, making it ~twice as fast or so.

For any maintainers or contributors to other chat apps, I would personally recommend the base64 -> URL image change the most, since it is a massive performance win with very few downsides (less portability), especially if you cache the images. Normalizing the chat messages table is far more complex and involved, and if implemented poorly can actually be _slower_ since the previous implementation was dead-simple - the database just had to find the JSON object and send it to the client. Now, the queries involve more work. I've managed to implement it in a way that is notably faster, but it isn't a silver bullet.

**Current State of Performance:**

- Chat that was previously 64MB of JSON due to having many images and loaded in 15 seconds back in October in a 'prod' build running in a Docker container can now load in with less than 1MB transferred data and finish page load in 2 seconds... in a dev build lacking many build-time optimizations and lacking GZIP compression. (Note that this is only after the chat messages and images get cached!)
- Chat that was previously 18.13MB of JSON (before gzip) due to having lots of RAG sources now fits into 1.56MB of JSON. I am not referring to the cached data transfer here, I am referring to the first-time chat load. In terms of latency, this means that same chat now takes less than 2 seconds (dev build) when it used to take 7 (prod w/ GZIP squeezing those 18.13MB into 4MB).
- The home page now loads ~2x faster due to deferring certain fetches.
- (not necessarily performance but) My 15k msgs database is now a 67MB backup w/ pg_dump, not a 570mb backup

## Bug Fixes

- (feat/bug) Added in-chat search functionality that allows you to search the current chat for messages containing given text. This includes searching between branches! All without crashing the browser—though it _can_ get pretty slow for large (multi-megabyte) conversations.
  - This is access via `CMD+F` or `CTRL+F`, and replaces the browser's built-in search. There may be unintended accessibility issues with this, so please LMK if you find any (open an issue).
  - See the later note about the "Go to message" function; this is a similar situation.
- (bug) Only send the first few hundred characters of each message to the Overview feature, since only the first few words can be seen at once anyway, and Overview currently can crash the browser with large (multi-megabyte) conversations. (see [issue #7](https://github.com/lumitry/vela-chat/issues/7)).

## Features

Current features and enhancements include:

- Removed the floating buttons when text is selected, as they were not useful (cf. "opinionated fork").
- Made the "New Chat" button work with CMD+click and CTRL+click to open in a new tab without changing the current tab.
- Typing on a chat page now automatically focuses the chat input.
- Made formatting shortcuts (CTRL/CMD+I for italics, CTRL/CMD+B for bold, CTRL/CMD+E for code) work in the non-rich text chat input.
- When the response contains hex codes, they are rendered with color swatches next to them. (Note: This does not occur in code blocks.) (Toggleable under Interface settings!) (Clicking on the swatch copies to clipboard.)
- (feat) Added the ability to link to a specific message (automatically navigates to the correct 'branch' in the conversation and scrolls to the message). Just press the "Copy Link" button underneath the message.
  - Note: Sometimes this can be buggy and not take you to the correct message, but it _should_ get the branch correct, at the very least. It piggybacks off an existing "Go to message" function, which may need some work in the future. better than nothing IMO, at least for now. See [issue #6](https://github.com/lumitry/vela-chat/issues/6).
- (enh) Tokens per second estimation added to usage data (just hover over the `(I)` icon at the bottom of a response message). Note that this is just an _estimation_! It isn't necessarily accurate.
- (enh) Made the popover when hovering on the model name in chat messages show the model's ID; it formerly showed the model's name, which was redundant, since you were hovering over that already.
- (enh) (**_OPPINIONATED_**) Changed `reasoning_effort` to be nested (`reasoning.effort`) in line with [OpenRouter's documentation](https://openrouter.ai/docs/use-cases/reasoning-tokens#reasoning-effort-level), since that's what I use.
  - Please open an issue if you use [OpenAI](https://platform.openai.com/docs/api-reference/chat/create#chat-create-reasoning_effort) or [Grok](https://docs.x.ai/docs/guides/reasoning) directly and this breaks your workflow. I may be able to change the advanced parameter entry for it to support "Default", "Custom (OpenAI)", and "Custom (OpenRouter)" modes.
- (enh) (**_OPPINIONATED_**) Added support for OpenRouter-specific routing parameters (the `provider` object).
  - [ ] TODO: Make it clearer in the UI that these are ORT-specific!
- (enh/UI) Added the current chat's title and folder (if applicable) to the top of the chat page. This is clickable! If you click on it, you'll get scrolled to the right folder in the sidebar. It'll be expanded if it wasn't already. (It's also reactive to title and folder change!)
- (enh) Support pasting formatted text into the plain text chat input ([#46](https://github.com/lumitry/vela-chat/issues/46)) (Can be toggled in user settings > "Interface" page)
- (enh/UI) Added support for arbitrary custom color schemes! In the General page of user settings, you can select any color you want from a color picker (or use the randomizer button!) then click "Apply" and it will be applied to the UI. This even works with image backgrounds!
- (enh) (**_WIP_** as of 2025-07-29) Added a "Thinking" button to the chat input that, when clicked, modifies the request such that it uses chain-of-thought when generating the response. This is only available for models that have been configured to support reasoning behavior. See [issue #19](https://github.com/lumitry/vela-chat/issues/19) for details.
  - Reasoning models with reasoning effort support can now have their reasoning effort toggled via a dropdown in chat when set up properly on the model editor page.
- (UI) Hidden models are now shown greyed out in the admin model reorder modal, and there are now buttons to move models to the top or bottom of the list (useful if you have tons).
- (enh/UX) Added copy table to clipboard button next to export to CSV button (in chat)
- Added estimated tokens per second, TTFT, generation time, and cost to the `usage` viewer (hover over the `(I)` icon) and at the bottom of each message (will probably be toggle-able in the future)
- ~~Added a dropdown to chat for GPT-5's new "verbosity" parameter. Requires enabling the "Verbosity" capability on the model editor page.~~ (Never mind, I'm getting API errors now. Verbosity [should be supported in the chat completions API](https://platform.openai.com/docs/api-reference/chat/create#chat_create-verbosity), but OpenRouter is giving me errors referncing the Responses API. Oh well. The button still shows up if you enable the capability, but it doesn't do anything for now.)
- Added "Move To..." option in chat ellipsis menu to move chats between folders and "New Folder" option in folder ellipsis menu to create new folders directly inside an existing one.
- Added sort options for chats list: sort by "Last Updated" (default), "Date Created", or "Title". (Stored in localStorage so it persists across sessions.)
- (enh) Renaming chats via modal instead of inline? Inline feels clunky to me.
- (enh) Allow moving chats between folders via a button in the dropdown menu in addition to drag-and-drop.
- (bug) Always create new tags, not just in the chat elipsis/dropdown menu (i.e. so tags are created in the feedback form and model creation page as well) ([#22](https://github.com/lumitry/vela-chat/issues/22))
- (enh) Disable regeneration on CTRL/CMD+R since sometimes you just want to refresh the page.
- Added a metrics dashboard to the workspaces pages, including all sorts of useful metrics about model usage. Metrics are calculated incrementally as messages get sent, meaning the page is super fast (~100ms for each API call, and the API calls run in parallel, and the first few get prefetched when you hover over the Metrics page button making the page load even faster). There is also a UMAP embeddings visualizer.
- The default admin settings page is now the Settings page, not the Users page.
- Links for admin settings pages (e.g. `/admin/settings#models`), meaning browser navigation now works!
- There is now a command palette! CMD+P is the default keybind. Supports changing most of the settings from the "Interface" page of user settings, plus creating new chats, searching chats, toggling the sidebar, and navigating to various pages within VelaChat.
  - If you're in a chat, you get even more commands: Rename current, move to folder, toggle pinned, clone current, change model, export current, copy link to current...
- Web search embeddings model can now be different than the regular embeddings model. I've lately realized that external embedding models are far slower than local ones (except for cold starts), so this might be a nice to have if you use external embedding models for general RAG (where latency matters less because it's happening in the background).

## Planned Enhancements

- (enh) typing in a single/double quote, parenthesis, or bracket while selecting text should automatically enclose that text instead of replacing it, similar to how it works in VSCode and other editors. ideally it would also close the marker automatically if you just type one without having anything selected, so typing in `(` would automatically add `)` after it, but IDK how to make it so that typing in the `)` yourself doesn't double it up. if that makes any sense

## Future Investigations

Future investigations include:

- (perf/optim) Removing the `knowledge` UUID list from the `models` endpoint since it is not needed for the vast majority of operations (would this break anything?)
- (feat) A "Branch Explorer" to visualize the conversation tree that, unlike the current "Overview" feature, allows you to **search branches** and even type in a branch series (e.g. `1-1-3-2-1` for the first branch of the first user message, the first branch of the first assistant message, the third branch of the second user message, and the second branch of the first assistant message) to navigate to a specific branch.
- (enh) Can we make the sidebar chat search feature show context for search results (e.g. showing the surrounding message text) and also take you to the specific branch of the conversation where the search result was found (see also: link to message feature)?
- (enh) LiteLLM/OpenRouter as first-class citizens (we already support tokens per second and cost usage info, but lots of other OpenRouter-specific features are not yet supported, e.g. dynamically adding :online or :exacto, rich provider filtering, etc.)
- (enh) Can we add Perplexity support in a way that still shows sources? (you can use it with response streaming disabled right now, but it doesn't show sources - note that this may very well be a LiteLLM issue similar to usage.cost not getting passed through properly)
- (feat) Maybe an "image library" for models? Would help for people who use official images (e.g. the OpenAI blossom, Gemini star, etc.) and don't want to have to locate the image on their computer every time (this would also help with deduplication/caching)
- How to fix that one issue where if you upload images multiple times in the same chat without refreshing in between, it sometimes makes the page bug out and not show the response coming in?
- (feat) Can we make it so that you can send a message and close the chat/tab/device (e.g. by streaming the response to the backend then forwarding it to the frontend while storing the response in memory then committing to DB when done)? this would be awesome for mobile users
  - This actually already exists! There's an environment variable called [`ENABLE_REALTIME_CHAT_SAVE`](https://docs.openwebui.com/getting-started/env-configuration/#enable_realtime_chat_save). I haven't tested this but it _should_ work. That said, perhaps the feature here would be automatically toggling this on when the user is on a mobile device?
- (feat) Could there be a "Scratchpad" sidebar where you can just dump a ton of text that will get chunked and vectorized for RAG without having to create a knowledge base, upload files, or use really long context length? Would be nice for adding reference information that isn't important enough to need to stay in context the full time, especially when using local models where quality degrades heavily after ~16k tokens.

I chose Open-WebUI 0.6.5 because it is the last version that's been stable for me, and it's the last version before the contributor license agreement was introduced.

## Notes

I'd personally recommend Postgres to anyone starting fresh since it will be more performant in the long run (currently, trying to export all chats from my Sqlite-backed "production" instance crashes the docker container entirely) and is fairly simple to set up (just use the Postgres docker image and set the `DATABASE_URL` environment variable to `postgresql://postgres:password@localhost:5432/open-webui` or whatever your Postgres instance is).

If you'd like to migrate your Sqlite installation to Postgres, you can see my notes on how to do this in [MIGRATE_SQLITE_TO_PSQL.md](utils/sqlite_to_postgres/MIGRATE_SQLITE_TO_PSQL.md) and the `migrate.sh` script in [utils/sqlite_to_postgres](utils/sqlite_to_postgres).

If you get issues loading chats containing code blocks, you should check to make sure you're using `npm` and not `pnpm`. PNPM has issues with codemirror in this repo. See [issue #1](https://github.com/lumitry/vela-chat/issues/1) for more details.

---

This project is a derivative work based on Open WebUI v0.6.5 (or earlier),
which was released under the BSD-3-Clause License.
This fork maintains the BSD-3-Clause License for its core components.

Original Copyright (c) 2023-2025 Timothy Jaeryang Baek (Open WebUI)

VelaChat is an independent project and is not affiliated with, endorsed by,
or maintained by the Open WebUI team.

---

Open WebUI's original README is available in [docs/ORIGINAL_README.md](docs/ORIGINAL_README.md).

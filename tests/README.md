# VelaChat E2E Tests

This directory contains the end-to-end tests for VelaChat.

## Running the tests

To run the tests, use the following command:

```bash
npm run test:e2e
```

or:

```bash
npx playwright test
```

## Writing tests

We use Playwright for our E2E tests. The tests themselves are in the `tests/e2e` directory, and the page objects are in the `tests/pages` directory. Page objects are used to represent the various pages and components in the application, and are used to interact with the application. (We use the page object model pattern for this.)

## TODOs

- [ ] STYLE GUIDE FOR TESTS/PAGE OBJECTS!
  - page object names must end in `Page` or `Tab`, e.g. `AdminUsersPage`, `AdminSettingsGeneralTab`.
  - component objects must end in their component type, e.g. since `AddUserModal` is a modal, it should end in `Modal`.
  - page object methods should be named after the verb/action they perform, e.g. `clickAddUserButton`, `clickSaveButton`, etc.
  - page object methods should be async and return void.
  - location of fields should be above the constructor (i don't follow this one yet i don't think, so i should also fix that!)
- [ ] DIRECTORY STRUCTURE EXPLANATION
- [ ] TEST/CLASS NAMING CONVENTIONS
- [ ] actually write a bunch of tests!
- [ ] add to mini-mediator (streaming support, etc.) (could also mock the API in Playwright maybe, but I'd prefer to use real backend API connections!)
- [ ] Write a script to automate the initial database setup (create pre-existing user `dev@example.com`, add model connections, etc.)
- [ ] Figure out how the tests will run on other people's machines (e.g. CI/CD, etc.)
- [ ] how will the user pool work?
- [ ] how will the precedence of test cases work? i.e. how will we specify the order they run in, if necessary?

## Things That Will Not Be Tested

- SQlite
- LDAP?
- Vector DBs other than Chroma and Qdrant
- Most of the actual external stuff (e.g. using Brave Search or Google PSE)
- OpenTelemetry integration
- OAuth
- Redis (and multi-node / cluster / whatever else the base project has along those lines)
- Storage (S3, Azure Blob Storage, etc.)
- Changing UVICORN_WORKERS

## Tests To Write

- [ ] Login Test
- [ ] Setup Test
  - [ ] Import Test Users
  - [ ] Create Test User via form (as opposed to CSV import)
  - [ ] Add OpenAI connection
  - [ ] Add Ollama connection
  - [ ] Set default user role to admin
  - [ ] Enable new signups
  - [ ] Set default embedding model to Mini-Mediator
  - [ ] Set internal and external task models to a Mini-Mediator task model (which would recognize all the various test cases and have deterministic outputs for each of them, e.g. it would know when we're testing a knowledge base and it would return the correct title and tags)
- [ ] Model CRUD Test - Parameterized for OpenAI & Ollama
  - [ ] Modify a model by changing its...
    - [ ] name
    - [ ] image
    - [ ] description
    - [ ] tags
  - [ ] Hide a model
  - [ ] Disable a model
  - [ ] Verify visibility settings are respected
- [ ] Workspace Model CRUD Test - Parameterized for OpenAI & Ollama
  - [ ] Create a new model
  - [ ] Edit a model
    - [ ] verify each field is editable and saved correctly
  - [ ] Delete a model
  - [ ] Clone a model
  - [ ] Hide a model
  - [ ] Disable a model
  - [ ] Verify visibility settings are respected
- [ ] Tools Test - Parameterized for OpenAI & Ollama
  - [ ] Create a new tool
  - [ ] Edit a tool
  - [ ] Delete a tool
  - [ ] Clone a tool
  - [ ] Disable a tool
  - [ ] Attach to model and see if it works (Mini-Mediator probably)
- [ ] Filters Test - not sure what to do here, i don't use functions that much
- [ ] Actions Test - not sure what to do here, i don't use functions that much
- [ ] Knowledge Base Test
  - [ ] Create a new knowledge base
  - [ ] Edit a knowledge base
  - [ ] Delete a knowledge base
  - [ ] Upload files to knowledge base and see if they show up - parameterized for multiple file types!!
    - Note: Embedding model should probably be set to Mini-Mediator. Meaning we need to make a Mini-Mediator embedding model too...
  - [ ] Batch upload files? Upload directory? How does this work w/ Playwright?
  - [ ] Attach to model and see if it works (Mini-Mediator probably)
  - [ ] Attach entire knowledge base to chat and see if it works
  - [ ] Attach individual files to chat and see if it works
  - [ ] Manually add text to knowledge base and see if it works
  - [ ] Verify visibility settings are respected
- [ ] Model Advanced Params Test - Parameterized for OpenAI & Ollama; also for Workspace and normal models
  - [ ] Modify a model's advanced params
    - [ ] system prompt
    - [ ] temperature
    - [ ] top_p
    - [ ] frequency_penalty
    - [ ] presence_penalty
    - [ ] max_tokens
    - [ ] n
    - [ ] stop
    - [ ] etc.
  - [ ] Verify advanced params are saved correctly and applied to model (by chatting with Mini-Mediator)
- [ ] User Advanced Params Test - Parameterized for OpenAI & Ollama (since chat completions get handled by different code paths for OpenAI vs Ollama I think)
  - [ ] Modify a user's advanced params
  - [ ] Verify advanced params are saved correctly and applied to user (by chatting with Mini-Mediator)
- [ ] User System Prompt Test
  - [ ] Modify a user's system prompt
  - [ ] Verify system prompt is saved correctly and applied to user (by chatting with Mini-Mediator)
- [ ] Chat Advanced Params Test - Parameterized for OpenAI & Ollama (same reason as above)
  - [ ] Modify a chat's advanced params
  - [ ] Verify advanced params are saved correctly and applied to chat (by chatting with Mini-Mediator)
  - [ ] Change to a different chat then back to the original chat and verify advanced params are still applied
- [ ] Chat System Prompt Test
  - [ ] Modify a chat's system prompt
  - [ ] Verify system prompt is saved correctly and applied to chat (by chatting with Mini-Mediator)
  - [ ] Change to a different chat then back to the original chat and verify system prompt is still applied
- [ ] Workspace Prompts Test
  - [ ] Create a new workspace prompt
  - [ ] See if it appears in the prompts in the chat
  - [ ] Edit a workspace prompt, see if it updates
  - [ ] Delete a workspace prompt, see if it disappears
  - [ ] Verify visibility settings are respected
- [ ] Model prompt suggestions test - Parameterized for workspace and normal models
  - [ ] Create a new prompt suggestion, see if it appears
  - [ ] Edit a prompt suggestion, see if it updates
  - [ ] Delete a prompt suggestion, see if it disappears
  - [ ] Verify visibility settings are respected
- [ ] Metrics Test
- [ ] Arena Models Test
- [ ] Evaluation/Leaderboard/Feedback Test (we really need to unify these names lol)
- [ ] User Settings Test Suite (note: this includes a lot of stuff, much of which will be handled by other tests)
  - [ ] Interface Settings Test
    - [ ] Landing Page Mode
    - [ ] Chat Bubble
    - [ ] Widescreen Mode
    - [ ] ... et cetera ...
    - HANDLED BY OTHER TESTS:
      - Command Palette Shortcut
      - rich text input
      - large text as file
  - [ ] Changing user profile image
  - [ ] Changing user name
  - I think the audio settings would get handled by other tests, but we should definitely make sure they DO get tested somewhere!
- [ ] Tool Servers Test
- [ ] Web Search Test
  - [ ] Both normal and overridden embedding models
  - [ ] Both with and without bypassing embedding and retrieval
  - [ ] Does disabling it properly disable the feature? Even in the command palette and navigating directly to the new chat page with query params?
  - Probably mock SearxNG since it lets you specify whatever URL you want for that engine. More mini-mediator scope creep...
  - [ ] Multiple web loader engines?
- [ ] Hybrid Search Test (using Mini-Mediator)
- [ ] Image Generation Test (using Mini-Mediator I guess... the scope creep is insane lol)
- [ ] Code Execution Test (Mini-Mediator would obv need a new 'model' for this that can hand back deterministic code blocks)
  - What's the difference between code execution and code interpreter? both support pyodide and jupyter fwiw
- Tasks Test Suite (see note way above about Mini-Mediator task model determinism)
  - [ ] Title Generation Test
  - [ ] Tags Generation Test
  - [ ] Image Prompt Generation Test (this might be handled by the image generation test above)
  - [ ] Query Generation Test (retrieval and web search queries)
  - [-] ~~Autocomplete Generation Test~~ (will be handled by the rich text editor test)
  - [ ] Emoji Generation Test (can we do this with Playwright?)
  - [ ] Function Calling Test
  - [ ] Test that all of these work with both the default prompt and a custom prompt, and both internal and external task models
- [ ] UI Banners Test (`/admin/settings#interface`)
- [ ] Default Prompt Suggestions Test (`/admin/settings#interface`)
- [ ] TTS Test (`/admin/settings#audio`) (how does this get tested by Playwright? do we mock the TTS API? or use it on deterministic text and verify the audio is correct? can playwright do that?)
- [ ] STT Test (`/admin/settings#audio`) (how does this get tested by Playwright? pre-made audio clips?)
- [ ] Multi-Model Response Test ('split view' functionality)
  - [ ] Tons of edge cases to worry about here!
  - [ ] MOA merge response test (as standard, mini-mediator's task models would need to recognize this and return a deterministic merge response)
- [ ] Rich Text Chat Input Test
  - [ ] Test that autocomplete works and that Mini-Mediator recognizes it properly (probably should always try to autocomplete the same text, so if the user types "9+10=", the autocomplete should always return "THIS IS A TEST OF MINI-MEDIATOR'S AUTOCOMPLETE SYSTEM.")
  - [ ] Test pasting HTML
  - [ ] Test pasting markdown? is this meant to be handled by the rich text editor?
  - [ ] Test hotkeys for bold, italic, and code.
  - [ ] Test pasting large text as file
- [ ] Plain Text Chat Input Test
  - [ ] Test pasting HTML
  - [ ] Test pasting markdown
  - [ ] Test hotkeys for bold, italic, and code.
  - [ ] Test pasting large text as file
- [ ] Document Extraction Test - Parameterized for multiple document extraction engines (Tika, Docling, Document Intelligence, Mistral OCR?)
  - [ ] Test extracting text from a PDF
  - [ ] other file types
  - [ ] PDF extract images? how to test this? not sure how the feature works
  - [ ] both character and tiktoken chunking
  - [ ] max file size should work
  - [ ] max upload count should work
  - [ ] embedding batch size should work
  - [ ] onedrive and google drive integration should work? not a priority for now, would be very hard to test
- [ ] Direct Connections Test - Users should be able to connect to their own OpenAI compatible API endpoints
  - [ ] also direct tool server connections
- [ ] Chat Archive Test (via sidebar button and command palette)
- [ ] Chat Export Test (JSON, PDF, plain text) (all should be deterministic) (via sidebar button and command palette)
- [ ] Chat Import Test (via sidebar button and command palette)
- [ ] Share Chat Test (via sidebar button and command palette)
- [ ] Clone Chat Test (via sidebar button and command palette)
  - [ ] Verify how it affects metrics
  - [ ] Verify the messages are copied correctly (i.e. correct timestamps, correct order, correct sibling relationships, etc.)
  - [ ] Deleting the original should not delete images/files/web search citations attached to the clone
  - [ ] Sharing the original, then making a clone, should not make the clone be shared
- [ ] Rename Chat Test (via sidebar and command palette)
- [ ] Move Chat to Folder Test (via sidebar button, drag-and-drop, and command palette)
- [ ] Delete Chat Test (via sidebar button and command palette)
- [ ] Command Palette Test
  - [ ] Test all commands not tested elsewhere (for example, most user settings > interface commands would be tested elsewhere since we already are going to test those settings)
  - [ ] Test changing the shortcut
  - [ ] Test commands that only appear when a chat is open (i.e. that they don't appear when no chat is open, and that they apply correctly, and how they work when viewing a shared chat, or an archived chat, etc.)
- [ ] Memory Test? IDK if this feature even works, or how it works.
- [ ] Chat Overview Test
- [ ] Chat Artifacts Test
- [ ] Chat Valves Test (Functions and Tools)
- [ ] Chat Info Modal Test (correct model names, message counts, cost tracking, branch/leaf count, attachment count, etc.)
  - [ ] make sure this works for split view chats too (shouldn't double-count messages or forget to count models in the non-selected branches)
- [ ] Navbar Chat Info Test (correct chat name and folder, even in edge cases of moving it before title generation or before the first generation is completed)
- [ ] Chat Full-Text Search Test (verify that it works and that the results are correct - this is why it's important that everything is deterministic! the simplest option is to just make a chat specifically for this test with a message that contains a word that appears nowhere else in the database, but I'd also prefer it if we had more results than just one chat... ideally multiple _pages_ of results!)
  - [ ] Fuzzy matching, diacritics/accent marks, case sensitivity, etc.
  - [ ] Searching for the title of a chat should also work
  - [ ] (should also work in the command palette)
- [ ] In-Chat Search Test
  - [ ] This one sounds very difficult to automate lol. and there are known bugs with this feature anyway, esp. for split view chats.
- [ ] Chat Message Links Test - copying a message link (then navigating away) then navigating to that link should take you to the correct message
  - [ ] Edge cases: shared chat, archived chat, deleted chat, split view chat

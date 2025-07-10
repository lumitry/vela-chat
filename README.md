# VelaChat

![VelaChat Logo](https://raw.githubusercontent.com/lumitry/vela-chat/refs/heads/main/static/static/favicon-96x96.png)

VelaChat is an opinionated fork of Open-WebUI 0.6.5 designed to provide a more performant and user-friendly experience.

Current enhancements include:
- Defer loading of the sidebar until after the chat has loaded, improving effective load times (since the sidebar is rarely the first thing a user interacts with).
- Removed the floating buttons when text is selected, as they were not useful (cf. "opinionated fork").
- Made the "New Chat" button work with CMD+click and CTRL+click to open in a new tab without changing the current tab.
- Typing on a chat page now automatically focuses the chat input.
- Made formatting shortcuts (CTRL/CMD+I for italics, CTRL/CMD+B for bold, CTRL/CMD+E for code) work in the non-rich text chat input.
- When the response contains hex codes, they are rendered with color swatches next to them. (Note: This does not occur in code blocks.)
- Improved speed of `/api/v1/folders/` endpoint by streamlining the database query to avoid an N+1 query problem.
  - I measured 7084ms for the old query (running via Docker with Postgres DB; it took 11.75 seconds for an equivalent Sqlite DB) vs 135ms (running via `npm run dev` with Postgres DB) for the new query with 30 folders in my personal database, which is a 50x improvement.
  - In the real world, this gave me a ~2x improvement in page load time for a chat I've been using for testing, from 30 seconds to 14 seconds.
  - The next bottleneck for page load times is the `/api/models` endpoint, which takes 10 seconds to load and blocks the UI. Fix is ~~WIP~~ DONE!
- Improve performance of the `/api/models` endpoint (no `/v1/` in the slug, that's a different endpoint) by optimizing for large model counts.
  - I managed to reduce the time it takes to load the models from around 11 seconds to under a second, but this isn't necessarily a like-for-like comparison so take it with a grain of salt. What I can say is that it now takes ~4 or 5 seconds to load the same page that used to take 30, and then 14 (after the `/api/v1/folders` change above).
- (feat) Added the ability to link to a specific message (automatically navigates to the correct 'branch' in the conversation and scrolls to the message). Just press the "Copy Link" button underneath the message.
  - Note: Sometimes this can be buggy and not take you to the correct message, but it *should* get the branch correct, at the very least. It piggybacks off an existing "Go to message" function, which may need some work in the future. better than nothing IMO, at least for now. See [issue #6](https://github.com/lumitry/vela-chat/issues/6).
- (feat) Added in-chat search functionality that allows you to search the current chat for messages containing given text. This includes searching between branches! All without crashing the browser—though it *can* get pretty slow for large (multi-megabyte) conversations.
  - This is access via `CMD+F` or `CTRL+F`, and replaces the browser's built-in search. There may be unintended accessibility issues with this, so please LMK if you find any (open an issue).
  - See above note about the "Go to message" function; this is a similar situation.
- (bug) Only send the first few hundred characters of each message to the Overview feature, since only the first few words can be seen at once anyway, and Overview currently can crash the browser with large (multi-megabyte) conversations. (see [issue #7](https://github.com/lumitry/vela-chat/issues/7)).

Planned enhancements include:
- (enh) typing in a single/double quote, parenthesis, or bracket while selecting text should automatically enclose that text instead of replacing it, similar to how it works in VSCode and other editors. ideally it would also close the marker automatically if you just type one without having anything selected, so typing in `(` would automatically add `)` after it, but IDK how to make it so that typing in the `)` yourself doesn't double it up. if that makes any sense
- (perf) Serve images via URL, not base64, to reduce payload size, database size, and improve general performance. (See [#2](https://github.com/lumitry/vela-chat/issues/2) and its sub-issues.)
- (perf) Don't bother loading in-chat images until after the chat itself has loaded. ([#26](https://github.com/lumitry/vela-chat/issues/26))
- (perf) Defer loading of model images. ([#23](https://github.com/lumitry/vela-chat/issues/23))
- (perf) Defer loading of models list?
- (feat) Add a "Think" button to the chat input that, when clicked, modifies the request such that it uses chain-of-thought when generating the response. See [issue #19](https://github.com/lumitry/vela-chat/issues/19) for more details.
- (enh) Renaming chats via modal instead of inline? Inline feels clunky to me.
- (enh) Make chat moving be a button in the dropdown menu instead of drag-and-drop since drag-and-drop is laggy at the moment.
  - UPDATE: Most of my qualms with drag-and-drop were fixed by making the folders endpoint faster, so this might not be necessary anymore.
- (bug) Always create new tags, not just in the chat elipsis/dropdown menu (i.e. so tags are created in the feedback form and model creation page as well) ([#22](https://github.com/lumitry/vela-chat/issues/22))
- (enh) Allow disabling of regeneration on CTRL/CMD+R since sometimes you just want to refresh the page.
- (enh) Lazy-load or allow disabling of TTS features; I personally don't use them, and Kokoro TTS is 2MB of JS that doesn't need to be loaded. (I'm also not sure if Transformers.JS is being used for anything else; that's another 800KB.)

Future investigations include:
- (perf) Enforcing Postgres?
- (perf/optim) Removing the `knowledge` UUID list from the `models` endpoint since it is not needed for the vast majority of operations (would this break anything?)
- (feat) A "Branch Explorer" to visualize the conversation tree that, unlike the current "Overview" feature, allows you to **search branches** and even type in a branch series (e.g. `1-1-3-2-1` for the first branch of the first user message, the first branch of the first assistant message, the third branch of the second user message, and the second branch of the first assistant message) to navigate to a specific branch.
- (enh) Can we make the chat search feature show context for search results (e.g. showing the surrounding message text) and also take you to the specific branch of the conversation where the search result was found (see also: link to message feature)?
- (enh) LiteLLM/OpenRouter as first-class citizens (tokens per second support, etc.) (maybe also basic usage stats with price info? a bit too complex for now though)
- (enh) Can we add Perplexity support in a way that still shows sources? (you can use it with response streaming disabled right now, but it doesn't show sources)
- (perf) How can we make the evaluations page load quicker? Does it require removing snapshots from the evaluations table? currently evaluations include the entire conversation, which can be hundreds of kilobytes in size (or more), which is probably unnecessary. this might end up being a breaking change involving making messages their own table and linking them to both chats and evaluations (if that's still performant) but it may be worth it.
- (feat) Maybe an "image library" for models? Would help for people who use official images (e.g. the OpenAI blossom, Gemini star, etc.) and don't want to have to locate the image on their computer every time (this would also help with deduplication/caching)
- How to fix that one issue where if you upload images multiple times in the same chat without refreshing in between, it sometimes makes the page bug out and not show the response coming in?
- (feat) Can we make it so that you can send a message and close the chat/tab/device (e.g. by streaming the response to the backend then forwarding it to the frontend while storing the response in memory then committing to DB when done)? this would be awesome for mobile users
  - This actually already exists! There's an environment variable called [`ENABLE_REALTIME_CHAT_SAVE`](https://docs.openwebui.com/getting-started/env-configuration/#enable_realtime_chat_save). I haven't tested this but it *should* work. That said, perhaps the feature here would be automatically toggling this on when the user is on a mobile device?
- (feat) Could there be a "Scratchpad" sidebar where you can just dump a ton of text that will get chunked and vectorized for RAG without having to create a knowledge base, upload files, or use really long context length? Would be nice for adding reference information that isn't important enough to need to stay in context the full time, especially when using local models where quality degrades heavily after ~16k tokens.
- (bug) Why does my personal database cause the evaluations page to fail with a `TypeError: Cannot read properties of null (reading 'toString') at Leaderboard.svelte:121:33` error? I tried removing an evaluation present with weird data (empty strings instead of `null`) in DataGrip but that didn't help. This occurs both in Postgres and Sqlite on my "production" instance running 0.6.5 main branch, so it's a legitimate bug, but IDK when it appeared or what the issue is.

I chose Open-WebUI 0.6.5 because it is the last version that's been stable for me, and it's the last version before the contributor license agreement was introduced.

## Notes
I'd personally recommend Postgres to anyone starting fresh since it will be more performant in the long run (currently, trying to export all chats from my Sqlite-backed "production" instance crashes the docker container entirely) and is fairly simple to set up (just use the Postgres docker image and set the `DATABASE_URL` environment variable to `postgresql://postgres:password@localhost:5432/open-webui` or whatever your Postgres instance is).

If you'd like to migrate your Sqlite installation to Postgres, you can see my notes on how to do this in [MIGRATE_SQLITE_TO_PSQL.md](MIGRATE_SQLITE_TO_PSQL.md) and the `migrate.sh` script in the root of the repository (will probably add these to a more permanent location later).

If you get issues loading chats containing code blocks, you should check to make sure you're using `npm` and not `pnpm`. PNPM has issues with codemirror in this repo. See [issue #1](https://github.com/lumitry/vela-chat/issues/1) for more details.

---

This project is a derivative work based on Open WebUI v0.6.5 (or earlier),
which was released under the BSD-3-Clause License.
This fork maintains the BSD-3-Clause License for its core components.

Original Copyright (c) 2023-2025 Timothy Jaeryang Baek (Open WebUI)

VelaChat is an independent project and is not affiliated with, endorsed by,
or maintained by the Open WebUI team.

# Original README

![GitHub stars](https://img.shields.io/github/stars/open-webui/open-webui?style=social)
![GitHub forks](https://img.shields.io/github/forks/open-webui/open-webui?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/open-webui/open-webui?style=social)
![GitHub repo size](https://img.shields.io/github/repo-size/open-webui/open-webui)
![GitHub language count](https://img.shields.io/github/languages/count/open-webui/open-webui)
![GitHub top language](https://img.shields.io/github/languages/top/open-webui/open-webui)
![GitHub last commit](https://img.shields.io/github/last-commit/open-webui/open-webui?color=red)
![Hits](https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Fgithub.com%2Follama-webui%2Follama-wbui&count_bg=%2379C83D&title_bg=%23555555&icon=&icon_color=%23E7E7E7&title=hits&edge_flat=false)
[![Discord](https://img.shields.io/badge/Discord-Open_WebUI-blue?logo=discord&logoColor=white)](https://discord.gg/5rJgQTnV4s)
[![](https://img.shields.io/static/v1?label=Sponsor&message=%E2%9D%A4&logo=GitHub&color=%23fe8e86)](https://github.com/sponsors/tjbck)

**Open WebUI is an [extensible](https://docs.openwebui.com/features/plugin/), feature-rich, and user-friendly self-hosted AI platform designed to operate entirely offline.** It supports various LLM runners like **Ollama** and **OpenAI-compatible APIs**, with **built-in inference engine** for RAG, making it a **powerful AI deployment solution**.

![Open WebUI Demo](./demo.gif)

> [!TIP]  
> **Looking for an [Enterprise Plan](https://docs.openwebui.com/enterprise)?** – **[Speak with Our Sales Team Today!](mailto:sales@openwebui.com)**
>
> Get **enhanced capabilities**, including **custom theming and branding**, **Service Level Agreement (SLA) support**, **Long-Term Support (LTS) versions**, and **more!**

For more information, be sure to check out our [Open WebUI Documentation](https://docs.openwebui.com/).

## Key Features of Open WebUI ⭐

- 🚀 **Effortless Setup**: Install seamlessly using Docker or Kubernetes (kubectl, kustomize or helm) for a hassle-free experience with support for both `:ollama` and `:cuda` tagged images.

- 🤝 **Ollama/OpenAI API Integration**: Effortlessly integrate OpenAI-compatible APIs for versatile conversations alongside Ollama models. Customize the OpenAI API URL to link with **LMStudio, GroqCloud, Mistral, OpenRouter, and more**.

- 🛡️ **Granular Permissions and User Groups**: By allowing administrators to create detailed user roles and permissions, we ensure a secure user environment. This granularity not only enhances security but also allows for customized user experiences, fostering a sense of ownership and responsibility amongst users.

- 📱 **Responsive Design**: Enjoy a seamless experience across Desktop PC, Laptop, and Mobile devices.

- 📱 **Progressive Web App (PWA) for Mobile**: Enjoy a native app-like experience on your mobile device with our PWA, providing offline access on localhost and a seamless user interface.

- ✒️🔢 **Full Markdown and LaTeX Support**: Elevate your LLM experience with comprehensive Markdown and LaTeX capabilities for enriched interaction.

- 🎤📹 **Hands-Free Voice/Video Call**: Experience seamless communication with integrated hands-free voice and video call features, allowing for a more dynamic and interactive chat environment.

- 🛠️ **Model Builder**: Easily create Ollama models via the Web UI. Create and add custom characters/agents, customize chat elements, and import models effortlessly through [Open WebUI Community](https://openwebui.com/) integration.

- 🐍 **Native Python Function Calling Tool**: Enhance your LLMs with built-in code editor support in the tools workspace. Bring Your Own Function (BYOF) by simply adding your pure Python functions, enabling seamless integration with LLMs.

- 📚 **Local RAG Integration**: Dive into the future of chat interactions with groundbreaking Retrieval Augmented Generation (RAG) support. This feature seamlessly integrates document interactions into your chat experience. You can load documents directly into the chat or add files to your document library, effortlessly accessing them using the `#` command before a query.

- 🔍 **Web Search for RAG**: Perform web searches using providers like `SearXNG`, `Google PSE`, `Brave Search`, `serpstack`, `serper`, `Serply`, `DuckDuckGo`, `TavilySearch`, `SearchApi` and `Bing` and inject the results directly into your chat experience.

- 🌐 **Web Browsing Capability**: Seamlessly integrate websites into your chat experience using the `#` command followed by a URL. This feature allows you to incorporate web content directly into your conversations, enhancing the richness and depth of your interactions.

- 🎨 **Image Generation Integration**: Seamlessly incorporate image generation capabilities using options such as AUTOMATIC1111 API or ComfyUI (local), and OpenAI's DALL-E (external), enriching your chat experience with dynamic visual content.

- ⚙️ **Many Models Conversations**: Effortlessly engage with various models simultaneously, harnessing their unique strengths for optimal responses. Enhance your experience by leveraging a diverse set of models in parallel.

- 🔐 **Role-Based Access Control (RBAC)**: Ensure secure access with restricted permissions; only authorized individuals can access your Ollama, and exclusive model creation/pulling rights are reserved for administrators.

- 🌐🌍 **Multilingual Support**: Experience Open WebUI in your preferred language with our internationalization (i18n) support. Join us in expanding our supported languages! We're actively seeking contributors!

- 🧩 **Pipelines, Open WebUI Plugin Support**: Seamlessly integrate custom logic and Python libraries into Open WebUI using [Pipelines Plugin Framework](https://github.com/open-webui/pipelines). Launch your Pipelines instance, set the OpenAI URL to the Pipelines URL, and explore endless possibilities. [Examples](https://github.com/open-webui/pipelines/tree/main/examples) include **Function Calling**, User **Rate Limiting** to control access, **Usage Monitoring** with tools like Langfuse, **Live Translation with LibreTranslate** for multilingual support, **Toxic Message Filtering** and much more.

- 🌟 **Continuous Updates**: We are committed to improving Open WebUI with regular updates, fixes, and new features.

Want to learn more about Open WebUI's features? Check out our [Open WebUI documentation](https://docs.openwebui.com/features) for a comprehensive overview!

## 🔗 Also Check Out Open WebUI Community!

Don't forget to explore our sibling project, [Open WebUI Community](https://openwebui.com/), where you can discover, download, and explore customized Modelfiles. Open WebUI Community offers a wide range of exciting possibilities for enhancing your chat interactions with Open WebUI! 🚀

## How to Install 🚀

### Installation via Python pip 🐍

Open WebUI can be installed using pip, the Python package installer. Before proceeding, ensure you're using **Python 3.11** to avoid compatibility issues.

1. **Install Open WebUI**:
   Open your terminal and run the following command to install Open WebUI:

   ```bash
   pip install open-webui
   ```

2. **Running Open WebUI**:
   After installation, you can start Open WebUI by executing:

   ```bash
   open-webui serve
   ```

This will start the Open WebUI server, which you can access at [http://localhost:8080](http://localhost:8080)

### Quick Start with Docker 🐳

> [!NOTE]  
> Please note that for certain Docker environments, additional configurations might be needed. If you encounter any connection issues, our detailed guide on [Open WebUI Documentation](https://docs.openwebui.com/) is ready to assist you.

> [!WARNING]
> When using Docker to install Open WebUI, make sure to include the `-v open-webui:/app/backend/data` in your Docker command. This step is crucial as it ensures your database is properly mounted and prevents any loss of data.

> [!TIP]  
> If you wish to utilize Open WebUI with Ollama included or CUDA acceleration, we recommend utilizing our official images tagged with either `:cuda` or `:ollama`. To enable CUDA, you must install the [Nvidia CUDA container toolkit](https://docs.nvidia.com/dgx/nvidia-container-runtime-upgrade/) on your Linux/WSL system.

### Installation with Default Configuration

- **If Ollama is on your computer**, use this command:

  ```bash
  docker run -d -p 3000:8080 --add-host=host.docker.internal:host-gateway -v open-webui:/app/backend/data --name open-webui --restart always ghcr.io/open-webui/open-webui:main
  ```

- **If Ollama is on a Different Server**, use this command:

  To connect to Ollama on another server, change the `OLLAMA_BASE_URL` to the server's URL:

  ```bash
  docker run -d -p 3000:8080 -e OLLAMA_BASE_URL=https://example.com -v open-webui:/app/backend/data --name open-webui --restart always ghcr.io/open-webui/open-webui:main
  ```

- **To run Open WebUI with Nvidia GPU support**, use this command:

  ```bash
  docker run -d -p 3000:8080 --gpus all --add-host=host.docker.internal:host-gateway -v open-webui:/app/backend/data --name open-webui --restart always ghcr.io/open-webui/open-webui:cuda
  ```

### Installation for OpenAI API Usage Only

- **If you're only using OpenAI API**, use this command:

  ```bash
  docker run -d -p 3000:8080 -e OPENAI_API_KEY=your_secret_key -v open-webui:/app/backend/data --name open-webui --restart always ghcr.io/open-webui/open-webui:main
  ```

### Installing Open WebUI with Bundled Ollama Support

This installation method uses a single container image that bundles Open WebUI with Ollama, allowing for a streamlined setup via a single command. Choose the appropriate command based on your hardware setup:

- **With GPU Support**:
  Utilize GPU resources by running the following command:

  ```bash
  docker run -d -p 3000:8080 --gpus=all -v ollama:/root/.ollama -v open-webui:/app/backend/data --name open-webui --restart always ghcr.io/open-webui/open-webui:ollama
  ```

- **For CPU Only**:
  If you're not using a GPU, use this command instead:

  ```bash
  docker run -d -p 3000:8080 -v ollama:/root/.ollama -v open-webui:/app/backend/data --name open-webui --restart always ghcr.io/open-webui/open-webui:ollama
  ```

Both commands facilitate a built-in, hassle-free installation of both Open WebUI and Ollama, ensuring that you can get everything up and running swiftly.

After installation, you can access Open WebUI at [http://localhost:3000](http://localhost:3000). Enjoy! 😄

### Other Installation Methods

We offer various installation alternatives, including non-Docker native installation methods, Docker Compose, Kustomize, and Helm. Visit our [Open WebUI Documentation](https://docs.openwebui.com/getting-started/) or join our [Discord community](https://discord.gg/5rJgQTnV4s) for comprehensive guidance.

### Troubleshooting

Encountering connection issues? Our [Open WebUI Documentation](https://docs.openwebui.com/troubleshooting/) has got you covered. For further assistance and to join our vibrant community, visit the [Open WebUI Discord](https://discord.gg/5rJgQTnV4s).

#### Open WebUI: Server Connection Error

If you're experiencing connection issues, it’s often due to the WebUI docker container not being able to reach the Ollama server at 127.0.0.1:11434 (host.docker.internal:11434) inside the container . Use the `--network=host` flag in your docker command to resolve this. Note that the port changes from 3000 to 8080, resulting in the link: `http://localhost:8080`.

**Example Docker Command**:

```bash
docker run -d --network=host -v open-webui:/app/backend/data -e OLLAMA_BASE_URL=http://127.0.0.1:11434 --name open-webui --restart always ghcr.io/open-webui/open-webui:main
```

### Keeping Your Docker Installation Up-to-Date

In case you want to update your local Docker installation to the latest version, you can do it with [Watchtower](https://containrrr.dev/watchtower/):

```bash
docker run --rm --volume /var/run/docker.sock:/var/run/docker.sock containrrr/watchtower --run-once open-webui
```

In the last part of the command, replace `open-webui` with your container name if it is different.

Check our Updating Guide available in our [Open WebUI Documentation](https://docs.openwebui.com/getting-started/updating).

### Using the Dev Branch 🌙

> [!WARNING]
> The `:dev` branch contains the latest unstable features and changes. Use it at your own risk as it may have bugs or incomplete features.

If you want to try out the latest bleeding-edge features and are okay with occasional instability, you can use the `:dev` tag like this:

```bash
docker run -d -p 3000:8080 -v open-webui:/app/backend/data --name open-webui --add-host=host.docker.internal:host-gateway --restart always ghcr.io/open-webui/open-webui:dev
```

### Offline Mode

If you are running Open WebUI in an offline environment, you can set the `HF_HUB_OFFLINE` environment variable to `1` to prevent attempts to download models from the internet.

```bash
export HF_HUB_OFFLINE=1
```

## What's Next? 🌟

Discover upcoming features on our roadmap in the [Open WebUI Documentation](https://docs.openwebui.com/roadmap/).

## License 📜

This project is licensed under the [BSD-3-Clause License](LICENSE) - see the [LICENSE](LICENSE) file for details. 📄

## Support 💬

If you have any questions, suggestions, or need assistance, please open an issue or join our
[Open WebUI Discord community](https://discord.gg/5rJgQTnV4s) to connect with us! 🤝

## Star History

<a href="https://star-history.com/#open-webui/open-webui&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=open-webui/open-webui&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=open-webui/open-webui&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=open-webui/open-webui&type=Date" />
  </picture>
</a>

---

Created by [Timothy Jaeryang Baek](https://github.com/tjbck) - Let's make Open WebUI even more amazing together! 💪

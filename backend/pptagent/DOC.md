# Documentation 📝

This documentation provides an overview of the project structure, setup instructions, usage guidelines, and steps for reproducing experiments.

<p align="center">
  <img src="resource/PPTAgent-workflow.jpg" alt="PPTAgent Workflow">
  <b>Figure: Workflow Illustration of PPTAgent:v0.0.1</b>
</p>

Table of Contents
=================
- [Documentation 📝](#documentation-)
- [Table of Contents](#table-of-contents)
  - [Recommendations and Requirements 🔬](#recommendations-and-requirements-)
  - [Quick Start 🚀](#quick-start-)
    - [MCP Server 🤖](#mcp-server-)
    - [Docker 🐳](#docker-)
    - [Running Locally 💻](#running-locally-)
      - [Installation Guide](#installation-guide)
      - [Usage](#usage)
        - [Generate Via WebUI](#generate-via-webui)
        - [Generate Via Code](#generate-via-code)
  - [Project Structure 📂](#project-structure-)
  - [Further Step ☝️](#further-step-️)
    - [Best Practice 💪](#best-practice-)
    - [Contributing 💛](#contributing-)
    - [Experimental Reproduction 🧪](#experimental-reproduction-)

## Recommendations and Requirements 🔬

<table>
  <thead>
    <tr>
      <th>Category</th>
      <th>Details</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="2"><b>LLM Recommendations</b></td>
      <td>Language Model: 70B+ parameters (eg. gpt-4.1, with support for structured output)</td>
    </tr>
    <tr>
      <td>Vision Model: 7B+ parameters (Qwen2.5-VL-7B-Instruct)</td>
    </tr>
    <tr>
      <td rowspan="3"><b>System Requirements</b></td>
      <td>Tested on Linux and macOS, <b>Windows is not supported</b>.</td>
    </tr>
    <tr>
      <td>Minimum 8GB RAM, recommended with CUDA or MPS support for faster presentation analysis.</td>
    </tr>
    <tr>
      <td><b>Required dependencies:</b> Python 3.11+, LibreOffice, Chrome, poppler-utils (conda: poppler), NodeJS, and other system dependencies listed in our <a href="https://github.com/icip-cas/PPTAgent/blob/docker/pptagent.dockerfile">dockerfile</a>.</td>
    </tr>
  </tbody>
</table>
To parse your uploaded PDF files, please follow [MinerU](https://opendatalab.github.io/MinerU/usage/quick_usage/#advanced-usage-via-api-webui-sglang-clientserver) and set the `MINERU_API` environment variable to `http://localhost:8000/file_parse`.

Some recommended templates are available in the [templates](pptagent/templates/) directory, and you can also refer to [Best Practice](BESTPRACTICE.md) for more details.

## Quick Start 🚀

For a quick test, use the example in `runs/pdf(pptx)/*/source.pdf(pptx)` to save preprocessing time.

### MCP Server 🤖

We now support MCP server, you can use it to generate presentations via MCP server.
```bash
uv pip install pptagent
export PPTAGENT_MODEL=openai/gpt-4.1
export PPTAGENT_API_BASE=http://localhost:8000/v1
export PPTAGENT_API_KEY=your_key
uv run pptagent-mcp
```

Use it in Claude or Cursor:
```json
{
  "mcpServers": {
    "pptagent": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "pptagent",
        "pptagent-mcp"
      ],
      "env": {
        "PPTAGENT_MODEL": "openai/gpt-4.1",
        "PPTAGENT_API_BASE": "http://localhost:8000/v1",
        "PPTAGENT_API_KEY": "your_key"
      }
    }
  }
}
```

Available tools:

| Tool Name | Description |
|-----------|-------------|
| `list_templates` | List all available PowerPoint templates |
| `set_template` | Select a PowerPoint template by name |
| `create_slide` | Create a slide with a given layout |
| `write_slide` | Write the slide elements for generating a PowerPoint slide |
| `generate_slide` | Generate a slide after setting layout and content |
| `save_generated_slides` | Save generated slides to a PowerPoint file |

### Docker 🐳

> [!NOTE]
> When using a remote server, ensure both ports `8088` and `9297` are forwarded.

```bash
# use docker proxy if you are in China
# docker pull dockerproxy.net/forceless/pptagent:latest
docker pull forceless/pptagent:latest

# mapping home directory to /root to allow caching of models
docker run -dt --gpus all --ipc=host --name pptagent \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e MINERU_API=$MINERU_API \
  -p 9297:9297 \
  -p 8088:8088 \
  -v $HOME:/root \
  forceless/pptagent

# set -e PULL=True to pull latest changes from the repository
# append /bin/fish to override the default command
```

It should automatically running [launch.sh](docker/launch.sh) to start the backend server.

See docker log for more running details:
```bash
docker logs -f pptagent
```

### Running Locally 💻

#### Installation Guide

```bash
pip install "pptagent[full]"
# or install locally
pip install -e ".[full]"
```

#### Usage

##### Generate Via WebUI

1. **Initialize Models**

   Set the environment variables:

   ```bash
   export OPENAI_API_KEY="your_key"
   export API_BASE="http://your_service_provider/v1"
   export LANGUAGE_MODEL="openai/gpt-4.1"
   export VISION_MODEL="openai/gpt-4.1"
   export MINERU_API="http://localhost:8000/file_parse"
   ```

2. **Run Backend**

   ```python
   python pptagent_ui/backend.py
   ```

3. **Launch Frontend**

   > Note: The backend API endpoint is configured at `pptagent_ui/vue.config.js`

   ```bash
   cd pptagent_ui
   npm install
   npm run serve
   ```

##### Generate Via Code

For detailed information on programmatic generation, please refer to the `pptagent_ui/backend.py:ppt_gen` and `test/test_pptgen.py`.

## Project Structure 📂

```
PPTAgent/
├── presentation/                   # Parse PowerPoint files
├── document/                       # Organize markdown document
├── pptagent/
│   ├── apis.py                     # API and CodeExecutor
│   ├── agent.py                    # Defines the `Agent` class
│   ├── llms.py                     # Defines the `LLM` and `AsyncLLM`
│   ├── induct.py                   # Presentation analysis (Stage Ⅰ)
│   ├── pptgen.py                   # Presentation generation (Stage Ⅱ)
├── pptagent_ui/                    # UI for PPTAgent
|   ├── src/                        # Frontend source code
│   ├── backend.py                  # Backend server
├── roles/                          # Role definitions in PPTAgent
├── prompts/                        # Project prompts
```

## Further Step ☝️

### Best Practice 💪

See [BESTPRACTICE.md](BESTPRACTICE.md) for more details.

### Contributing 💛

So you want to contribute? Yay!

This project is actively maintained! We welcome:
- Issues: Bug reports, feature requests, and questions
- Pull Requests: Code improvements, documentation updates, and fixes
- Discussions: Share your ideas and experiences

### Experimental Reproduction 🧪

See [experiment](https://github.com/icip-cas/PPTAgent/tree/experiment) branch for reproducing experiments and evaluation results.

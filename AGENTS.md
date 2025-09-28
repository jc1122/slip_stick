# Repository Guidelines

## Project Structure & Module Organization
The workspace lives in `/workspaces/slip_stick`, with core documentation in `memory-bank/`. Each Markdown file holds a specific layer of context: `projectbrief.md` (scope), `productContext.md` (purpose), `systemPatterns.md` (architecture), `techContext.md` (stack), `activeContext.md` (current focus), and `progress.md` (status). Keep auxiliary notes alongside the Memory Bank or in clearly named subfolders if they are long-lived; temporary scratchpads belong outside the repo. Review `.clinerules` whenever unsure about hierarchy or update cadence.

## Build, Test, and Development Commands
This project is documentation-first, so there is no compile step. Use `ls memory-bank/` to confirm required files before editing and `git diff` to review changes. If you have markdownlint installed locally, run `markdownlint "memory-bank/*.md" AGENTS.md` to catch formatting drift. Agents working in VS Code should enable the Markdown preview (`Ctrl+Shift+V`) to verify layout before committing.

## Coding Style & Naming Conventions
Write in clear, concise Markdown using sentence case headings and bullets sparingly. Keep files in ASCII, wrap prose near 100 characters, and favor short paragraphs. Use fenced code blocks for command examples, e.g., ``bash``. File names stay lowercase with hyphens (`memory-bank/techContext.md` already intentionally camel-cases the second word—follow the established names). Mirror the Memory Bank ordering when linking between documents.

## Testing Guidelines
Treat reviews as quality gates: read diffs aloud, check that new sections stay within 200–400 words when specified, and confirm internal links resolve. When adding processes, include a runnable example command. For major edits, have another agent preview the Markdown or run markdownlint to catch heading-level jumps and trailing spaces.

## Commit & Pull Request Guidelines
Craft commits that group related doc updates and start messages with a descriptive prefix (e.g., `docs: update active context for sprint`). Reference relevant tasks or discussions in the body. Pull requests should summarize the documentation impact, list affected files, and note any follow-up actions. Include screenshots only if visual output changed; otherwise, link to rendered previews. Always run `git status` before requesting review to ensure no stray files are staged.

## Agent Workflow Tips
Before tackling a task, skim the Memory Bank in dependency order to rebuild context. Update `activeContext.md` and `progress.md` immediately after significant decisions so future sessions inherit accurate state. When uncertain, document assumptions inline and flag them for follow-up in `progress.md`.

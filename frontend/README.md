# Shion AI frontend

React and TypeScript workspace built with Vite, Tailwind CSS, and Axios. It
supports authentication, assistants, document uploads and processing status,
saved conversations, answer-mode selection, and source downloads.

Start with the [root README](../README.md#run-locally) to run both the API and the
frontend. The backend runs in Docker; this frontend runs separately through Vite.

## Code map

| File or directory | Responsibility |
| --- | --- |
| `src/main.tsx` | Mount React and load shared styles |
| `src/App.tsx` | Session bootstrap, assistant selection, onboarding |
| `src/components/AuthScreen.tsx` | Sign-in and registration forms |
| `src/components/CreateAssistant.tsx` | Assistant creation dialog |
| `src/components/Workspace.tsx` | Document polling, conversation navigation, responsive panels |
| `src/components/ChatPanel.tsx` | Messages, answer-mode selection, source labels and citations |
| `src/components/DocumentsPanel.tsx` | Upload, retry, download, and removal |
| `src/api/` | Typed API calls, cookie authentication, shared refresh handling |
| `src/index.css` | Tailwind import, theme, shared component and responsive styles |
| `tests/workspace.spec.ts` | Playwright user-flow tests with simulated API responses |

## Development notes

The [environment example](.env.example) documents optional API settings. Default
development requests use Vite's same-origin proxy. Keep API keys and backend
secrets out of frontend environment variables.

The color palette is teal `#35B8A4`, off-white `#F7F8F2`, and charcoal `#21332F`,
with mixtures/transparency and no gradients. Narrow layouts separate chat and
documents into panels.

The frontend uses HTTP-only authentication cookies and does not store tokens in
localStorage. Source labels are read from saved message metadata; changing the
current answer mode does not rewrite historical labels.

See [architecture](../docs/ARCHITECTURE.md#frontend-boundary) for API behavior and
[testing](../docs/TESTING.md#frontend-commands) for build, lint, and browser commands.
The production bundle is written to `frontend/dist`.

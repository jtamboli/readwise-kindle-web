# Readwise Reader Private State Sync API

Analysis of the internal API used by the official Readwise Reader iOS app
(v7.36.1) for syncing reading position and document state. Captured via
HAR traffic inspection on 2026-02-21.

The public Readwise API (`/api/v3/update/{id}/`) does **not** support
writing `reading_progress` or `lastOpenedAt` — it silently ignores these
fields. The official apps use this private state sync API instead.

## Endpoints

### `GET /reader/api/state`

Polls for state changes. Supports incremental sync.

**Query parameters:**

| Parameter | Example | Description |
|-----------|---------|-------------|
| `schemaVersion` | `10` | API schema version |
| `isChunkingSupported` | `true` | Client supports chunked responses |
| `filter[updated_at][gt]` | `1771638800864` | Unix epoch ms — only return state updated after this timestamp |

**Response:** Large JSON object (~33KB) containing user settings, RSS
feeds, filtered views, jobs, integrations, and a `documents` dict with
any documents changed since the filter timestamp. Each document in the
response includes `readingPosition` and `currentScrollPosition` fields.

### `POST /reader/api/state/update`

Pushes state changes to the server.

**Response:** Always `{}` with HTTP 200.

## Authentication

Uses session-based auth, not API tokens:

| Header | Value |
|--------|-------|
| `mobilesession` | `<session-token>` |
| `Cookie` | `uniqueCookie=<id>` |
| `User-Agent` | `readermobile/1 CFNetwork/... Darwin/...` |

## Request Envelope

```json
{
  "events": [ ... ],
  "schemaVersion": 10,
  "isChunkingSupported": true
}
```

## Event Structure

Each event in the `events` array:

```json
{
  "id": "<ULID>",
  "correlationId": "<ULID>",
  "name": "<event-type>",
  "timestamp": 1771639100263,
  "userInteraction": { "name": "scroll" | "unknown" },
  "environment": {
    "agent": { "category": "mobile-app", "version": "7.36.1" },
    "app": {
      "category": "mobile-app",
      "commitId": "unknown",
      "version": "7.36.1",
      "sessions": {
        "focusSessionId": "...",
        "instanceSessionId": "...",
        "pageSessionId": "...",
        "windowSessionId": "..."
      }
    },
    "channel": "production",
    "os": { "name": "ios", "version": "..." },
    "device": { "model": "iPhone", "type": "Handset", "vendor": "Apple" }
  },
  "dataUpdates": {
    "forwardPatch": [ /* JSON Patch (RFC 6902) operations */ ],
    "reversePatch": [ /* inverse operations for undo */ ],
    "itemsUpdated": [{ "id": "<doc-id>", "type": "documents" }]
  }
}
```

Patches use JSON Patch (RFC 6902) `replace` operations on paths relative
to the state tree (e.g. `/documents/<id>/currentScrollPosition/scrollDepth`).

The `reversePatch` contains the inverse operation for each forward patch,
enabling undo and conflict resolution.

## Event Types

### `document-scroll-position-updated`

Fires on scroll. Updates the current viewport position (can move forward
or backward).

**userInteraction:** `scroll`

**Patched fields** (all under `/documents/<id>/currentScrollPosition/`):

| Field | Type | Description |
|-------|------|-------------|
| `scrollDepth` | float 0–1 | Percentage of document scrolled |
| `serializedPosition` | string | Element-based position, e.g. `"48:0"` |
| `mobileSerializedPositionElementVerticalOffset` | int | Pixel offset within the element |

Not all fields are present in every event. Throttled intermediate updates
may only include `scrollDepth`, while full updates include all three.

### `document-progress-position-updated`

Fires on scroll. Updates the reading progress **high-water mark** — only
moves forward, never backward.

**userInteraction:** `scroll`

**Patched fields** (all under `/documents/<id>/readingPosition/`):

Same fields as scroll position, but with a guard: the `forwardPatch`
includes a `test` operation with a less-than comparison to ensure
progress only advances:

```json
{ "op": "test", "path": ".../readingPosition/scrollDepth", "value": "<0.166" }
```

This is distinct from `currentScrollPosition` — `readingPosition` is the
furthest point the user has reached, while `currentScrollPosition` is
where they're currently looking.

### `document-opened`

Fires when a document is opened or re-opened.

**userInteraction:** `unknown`

**Patched fields:**

| Field | Type | Description |
|-------|------|-------------|
| `/documents/<id>/lastOpenedAt` | int | Unix epoch milliseconds |

## Key Observations

- The API distinguishes between **current scroll position** (where you
  are now) and **reading progress** (furthest point reached). The public
  API's `reading_progress` field corresponds to the latter.

- Events are sent frequently during scrolling (~1 per second in the
  capture), each in its own POST request.

- The `document-progress-position-updated` event uses a conditional
  `test` operation to enforce forward-only progress, preventing scroll-
  backs from reducing the reading progress watermark.

- Multiple events can be batched in a single POST request (observed:
  `document-scroll-position-updated` + `document-progress-position-updated`
  in one request).

- The `serializedPosition` format (`"N:0"`) appears to be an element
  index within the document's DOM, providing a viewport-independent
  position that survives font size changes.

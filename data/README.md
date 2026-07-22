# Question Data Pipeline

This folder enables phase-wise ingestion of large Q&A datasets without changing UI layout/theme.

## Files

- `questions-manifest.json`: controls load order and initial chunk preload.
- `questions-chunk-XXX.json`: each chunk contains:

```json
{
  "questions": [
    {
      "id": 10001,
      "question": "...",
      "answer": "...",
      "answerFull": "...",
      "askedBy": "...",
      "constituency": "...",
      "party": "...",
      "house": "Lok Sabha",
      "session": "Budget Session 2025",
      "sessionType": "Budget",
      "date": "2025-02-01",
      "questionType": "Unstarred",
      "questionNumber": "U.Q.No. 123",
      "ministry": "...",
      "answeredBy": "...",
      "answeredByRole": "...",
      "tags": ["..."],
      "source": "official.host/path"
    }
  ]
}
```

## Phase-wise rollout

1. Add a new chunk file (example: `questions-chunk-002.json`).
2. Append it to `chunks` array in `questions-manifest.json`.
3. Optionally raise `initialChunkCount` to preload more chunks at startup.

The app deduplicates by `id`, so existing site questions remain untouched.

# PrepNest — UX Design

## Design philosophy
The user is a stressed 17-year-old at 9pm. Every flow optimizes for "help me with THIS, now": minimal taps, no browsing, no configuration. The parent surface is deliberately separate and read-only — parents see progress, never lesson content.

## Critical flows
1. **Stuck → booked** — camera opens on the FAB, student snaps the problem, picks one of 3 offered slots. Three taps total; median time-to-booking under 40 seconds.
2. **Session join** — push reminder at T-5min deep-links straight into the room; audio-only toggle is first-class for bad connections.
3. **Session safety** — a persistent, unobtrusive report button in the room; tapping it flags the recording and ends the session with a neutral message.
4. **Post-session recap** — tutor leaves a 3-line summary + suggested practice set; parent gets a weekly digest.

## Key screens
- **Home** — single FAB ("I'm stuck"), today's booked session card, streak of practiced topics
- **Mastery map** — per-topic traffic-light grid mirroring the official exam syllabus order
- **Parent view** — weekly digest web page: sessions used, topics practiced, mastery deltas. No chat, no content.

## Interaction notes
- Free-plan users hitting the question-bank daily cap see the Plus upsell exactly once per day, dismissible
- Empty states teach: the mastery map starts as the real syllabus with everything grey, so day one shows the mountain honestly
- All tutor-facing screens keep the reporting/escalation path one tap away, mirroring the safeguarding policy

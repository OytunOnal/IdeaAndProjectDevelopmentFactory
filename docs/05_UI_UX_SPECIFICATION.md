# ProjectFactory - UI/UX Specification

> Version: 1.0 | Last Updated: 2026-05-11

---

## 1. Design Principles

1. **Artifact-first, not chat-first** - The generated documents are the hero, chat is the input method
2. **Progressive disclosure** - Show summaries first, details on demand
3. **Real-time feedback** - Users always know what's happening (streaming, progress, status)
4. **Collaborative feel** - Agents feel like team members, not tools
5. **Minimal friction** - Getting started should take under 60 seconds

---

## 2. Page Structure

### 2.1 Pages

| Page | Route | Description |
|------|-------|-------------|
| Landing | `/` | Marketing page + sign up |
| Dashboard | `/dashboard` | All projects overview |
| Project Workspace | `/project/:id` | The main IDE view |
| Settings | `/settings` | API keys, preferences, autonomy |
| New Project | `/project/new` | Start a new project |

### 2.2 Main Layout (Project Workspace)

This is where 90% of usage happens. Three-panel layout:

```
┌──────────────────────────────────────────────────────────────────────┐
│  HEADER BAR                                                          │
│  [Logo] [ProjectName ▼] [Pipeline|Editor|Quality] [Settings] [User] │
├────────────┬─────────────────────────────────────┬───────────────────┤
│            │                                     │                   │
│  LEFT      │        CENTER                       │   RIGHT           │
│  PANEL     │        PANEL                        │   PANEL           │
│            │                                     │                   │
│  File      │  (Switches based on top tab)        │   Chat +          │
│  Explorer  │                                     │   Decisions       │
│            │  Pipeline: Agent graph view          │                   │
│  240px     │  Editor:   Document view/edit        │   380px           │
│  min       │  Quality:  Score dashboard           │   min             │
│            │                                     │                   │
│  Resize ↔  │                                     │   Resize ↔        │
│            │                                     │                   │
├────────────┴─────────────────────────────────────┴───────────────────┤
│  STATUS BAR                                                          │
│  [Phase: Discovery] [Agent: MarketResearcher ●] [Cost: $1.23] [Stop]│
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Specifications

### 3.1 Header Bar

```
┌──────────────────────────────────────────────────────────────────┐
│ 🏭 ProjectFactory   Boat Marketplace ▼   │Pipeline│Editor│Quality│   ⚙ OY │
└──────────────────────────────────────────────────────────────────┘
```

- **Logo**: Links to dashboard
- **Project Selector**: Dropdown to switch between projects
- **View Tabs**: Toggle center panel content
  - `Pipeline` - Agent graph visualization (default when pipeline is running)
  - `Editor` - Document viewer/editor (default when pipeline is paused/done)
  - `Quality` - Quality score dashboard
- **Settings**: Open settings page
- **User Avatar**: Profile menu, sign out

### 3.2 Left Panel - File Explorer

```
┌─────────────────────┐
│ 📁 FILES             │
│                      │
│ 📄 INDEX.md      ✅  │
│ 📄 QUALITY.md    ⏳  │
│ 📄 ROADMAP.md    ○   │
│                      │
│ ▼ 📁 01_STRATEGY     │
│   📄 vision.md   ✅  │
│   📄 competitors ✅  │
│   📄 business.md 🔄  │
│   📄 risks.md    ○   │
│                      │
│ ▶ 📁 02_PRODUCT      │
│ ▶ 📁 03_DESIGN       │
│ ▶ 📁 04_TECH         │
│ ▶ 📁 05_PLANNING     │
│                      │
│ ─────────────────    │
│ 📊 Quality: 82/100   │
│ 📁 Files: 12/16      │
│ ⏱  Started: 14m ago  │
└──────────────────────┘
```

**Status Icons:**
- ✅ Complete and reviewed
- 🔄 Currently being written/modified by an agent
- ⏳ Queued (will be generated)
- ○ Not started yet
- ⚠️ Has issues (from quality review)

**Behavior:**
- Click file → opens in center panel (Editor view)
- Folders collapse/expand
- Files appear as they're generated (new files animate in)
- Bottom section: project stats summary

### 3.3 Center Panel - Pipeline View

```
┌──────────────────────────────────────────────────────┐
│                    PIPELINE VIEW                      │
│                                                       │
│  ┌─────────┐                                         │
│  │  IDEA   │ ✅ Complete                              │
│  │ ANALYST │ "Boat marketplace for Turkey"            │
│  └────┬────┘                                         │
│       │                                               │
│  ┌────▼────────────────────────────────────┐         │
│  │         RESEARCH  (Parallel)             │         │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │         │
│  │  │ MARKET   │ │COMPETITOR│ │  TECH    │ │         │
│  │  │ RESEARCH │ │ ANALYSIS │ │FEASIBLTY │ │         │
│  │  │ ████░ 78%│ │ ████░ 65%│ │ ██░░ 40% │ │         │
│  │  │  ● live  │ │  ● live  │ │  ● live  │ │         │
│  │  └──────────┘ └──────────┘ └──────────┘ │         │
│  └────────────────────┬────────────────────┘         │
│                       │                               │
│  ┌────────────────────▼────────────────────┐         │
│  │         USER CHECKPOINT                  │         │
│  │  "Review research findings before        │         │
│  │   proceeding to specification"           │         │
│  │              ○ Waiting                   │         │
│  └──────────────────────────────────────────┘         │
│                       │                               │
│  ┌────────────────────▼────────────────────┐         │
│  │         SPECIFICATION                    │         │
│  │  SpecWriter → Architect → UX             │         │
│  │              ○ Not started               │         │
│  └──────────────────────────────────────────┘         │
│                       │                               │
│  ┌────────────────────▼────────────────────┐         │
│  │         QUALITY + PACKAGING              │         │
│  │              ○ Not started               │         │
│  └──────────────────────────────────────────┘         │
│                                                       │
└──────────────────────────────────────────────────────┘
```

**Implementation:** React Flow with custom nodes
- Each agent = a node with status, progress bar, and click-to-expand
- Edges show data flow direction
- Active nodes have a pulsing indicator
- Completed nodes turn green with checkmark
- Parallel nodes shown side-by-side in a group
- User checkpoint nodes have a distinct style (orange, pause icon)
- Click a node → shows that agent's output in a side drawer

### 3.4 Center Panel - Editor View

```
┌──────────────────────────────────────────────────────┐
│  01_STRATEGY / vision.md               [Preview|Raw] │
│  Generated by: spec_writer  │  v2  │  Status: ✅     │
├──────────────────────────────────────────────────────┤
│                                                       │
│  # Vision                                             │
│                                                       │
│  ## Problem Statement                                 │
│                                                       │
│  Turkey's marine market lacks a dedicated digital     │
│  platform for buying and selling boats and marine     │
│  equipment. Current solutions like Sahibinden.com     │
│  offer boat listings as a subcategory with poor UX,   │
│  no specialized features, and no ecosystem support.   │
│                                                       │
│  ## Target Market                                     │
│                                                       │
│  - **TAM:** $1.2B (Turkish marine market)             │
│  - **SAM:** $340M (online marine transactions)        │
│  - **SOM:** $12M (Year 1 target, 3.5% capture)       │
│                                                       │
│  ## Value Proposition                                 │
│                                                       │
│  "The Sahibinden of the sea" - a dedicated            │
│  marketplace where boat owners, service providers,    │
│  and marine enthusiasts connect with specialized      │
│  tools built for their needs.                         │
│                                                       │
│  ┌─ Agent Edit ──────────────────────────────────┐   │
│  │ spec_writer updated this section:              │   │
│  │ - Added TAM/SAM/SOM from market research      │   │
│  │ - Changed "platform" to "marketplace"          │   │
│  │ [Accept All] [Review Changes] [Reject]         │   │
│  └────────────────────────────────────────────────┘   │
│                                                       │
└──────────────────────────────────────────────────────┘
```

**Modes:**
- **Preview**: Rendered markdown (default, read-only feel)
- **Raw**: Monaco Editor with markdown syntax highlighting (editable)
- **Diff**: When agent modifies a file, show before/after diff
- **Wireframe**: For `.tsx` wireframe files - renders the React component in a sandboxed iframe with device frame (desktop/tablet/mobile toggle)

**Features:**
- Top bar shows: file path, generating agent, version number, status
- Agent edit notifications inline (accept/reject changes)
- Auto-save on edit
- Scroll sync between preview and raw modes

### 3.5 Center Panel - Quality View

```
┌──────────────────────────────────────────────────────┐
│                 QUALITY DASHBOARD                      │
│                                                       │
│            ┌──────────────────┐                       │
│            │       82        │                        │
│            │     /100        │                        │
│            │    Grade: B     │                        │
│            └──────────────────┘                       │
│                                                       │
│  Strategy     ████████████████████░░░░░  20/25        │
│  Product      ██████████████████████████░ 26/30       │
│  Design       █████████████████░░░░░░░░  14/20        │
│  Technical    ██████████████████████░░░  22/25         │
│                                                       │
│  ─────────────────────────────────────                │
│                                                       │
│  ⚠️  GAPS IDENTIFIED (3)                              │
│                                                       │
│  🔴 Critical: Wireframe descriptions missing          │
│     File: 03_DESIGN/wireframes.md                     │
│     Action: UX Strategist needs to add screen descs   │
│                                                       │
│  🟡 Major: API rate limiting not specified             │
│     File: 04_TECH/api.md                              │
│     Action: Add rate limiting section                  │
│                                                       │
│  🟢 Minor: Budget breakdown lacks hosting costs       │
│     File: 05_PLANNING/budget.md                       │
│     Action: Add hosting cost estimates                 │
│                                                       │
│  ─────────────────────────────────────                │
│                                                       │
│  😈 DEVIL'S ADVOCATE REPORT                           │
│                                                       │
│  Risk Level: MEDIUM                                   │
│                                                       │
│  Top Challenges:                                      │
│  1. Sahibinden could launch a dedicated marine        │
│     section, eliminating your differentiation          │
│  2. Seasonality means 5 months of low traffic         │
│  3. Turkey's economic volatility affects luxury        │
│     purchases like boats                              │
│                                                       │
│  [View Full Report →]                                 │
│                                                       │
└──────────────────────────────────────────────────────┘
```

### 3.6 Right Panel - Chat & Decisions

```
┌────────────────────────────────┐
│ 💬 CHAT                        │
│                                │
│ ┌────────────────────────────┐ │
│ │ 🤖 Idea Analyst            │ │
│ │ "I've structured your idea │ │
│ │  into a brief. Here's what │ │
│ │  I understood:              │ │
│ │                             │ │
│ │  Problem: No dedicated     │ │
│ │  boat marketplace in TR    │ │
│ │                             │ │
│ │  Target: Boat owners +     │ │
│ │  marine service providers  │ │
│ │                             │ │
│ │  Does this look right?"    │ │
│ └────────────────────────────┘ │
│                                │
│ ┌────────────────────────────┐ │
│ │ 👤 You                     │ │
│ │ "Yes, but also add marine  │ │
│ │  equipment and spare parts"│ │
│ └────────────────────────────┘ │
│                                │
│ ┌────────────────────────────┐ │
│ │ 🤖 Idea Analyst            │ │
│ │ "Updated. Starting         │ │
│ │  research now..."          │ │
│ └────────────────────────────┘ │
│                                │
│ ┌─ DECISION ─────────────────┐ │
│ │ 🔍 Competitor Analyst       │ │
│ │                             │ │
│ │ "I found that boat24.com   │ │
│ │  uses a listing fee model  │ │
│ │  while Sahibinden uses     │ │
│ │  commission. Which model   │ │
│ │  should we base ours on?"  │ │
│ │                             │ │
│ │ My recommendation:          │ │
│ │ Commission (users are used │ │
│ │ to Sahibinden's model)     │ │
│ │                             │ │
│ │ ┌──────────────────┐       │ │
│ │ │ A) Listing Fee   │       │ │
│ │ │ B) Commission ★  │       │ │
│ │ │ C) Subscription  │       │ │
│ │ │ D) You decide     │       │ │
│ │ │ E) Tell me more   │       │ │
│ │ └──────────────────┘       │ │
│ │                             │ │
│ │ Or type your own answer... │ │
│ └────────────────────────────┘ │
│                                │
│ ┌────────────────────────────┐ │
│ │ 📊 Agent Status             │ │
│ │ ✅ Idea Analyst     2.3s   │ │
│ │ 🔄 Market Rsrch    1:23   │ │
│ │ 🔄 Competitor      0:58   │ │
│ │ 🔄 Tech Feas       0:34   │ │
│ │ ○  Spec Writer      -     │ │
│ │ ○  Architect         -     │ │
│ └────────────────────────────┘ │
│                                │
│ ┌────────────────────────────┐ │
│ │ Type a message...      📎 ↵ │ │
│ └────────────────────────────┘ │
└────────────────────────────────┘
```

**Chat Features:**
- Agent messages show agent avatar + name + role color
- User messages are right-aligned
- Decision cards are inline, interactive UI elements (not just text)
- Agent status section collapsible at bottom
- Streaming text appears character-by-character
- When pipeline is waiting for user, chat shows clear prompt
- Message input supports markdown
- Attach button (📎) for uploading reference documents

**Decision Card UX:**
- Clearly distinguished from regular chat messages (border, background)
- Agent recommendation marked with ★
- Click an option → immediate response, pipeline resumes
- "You decide" → agent uses its recommendation
- "Tell me more" → agent provides deeper analysis
- Free-form text input below options
- Decision cards become read-only after resolution (show what was chosen)

### 3.7 Status Bar

```
┌──────────────────────────────────────────────────────────────────┐
│ Phase: Discovery (2/4) │ 🔄 CompetitorAnalyst │ $1.23 │ 3:42 │ ⏸ ■ │
└──────────────────────────────────────────────────────────────────┘
```

- **Phase indicator**: Current phase with step count
- **Active agent**: Currently running agent with spinner
- **Cost**: Running total estimated cost
- **Time**: Elapsed time since pipeline started
- **Controls**: Pause (⏸) and Stop (■) buttons

---

## 4. Dashboard Page

```
┌──────────────────────────────────────────────────────────────────┐
│  🏭 ProjectFactory                               ⚙ Settings  OY │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Your Projects                              [+ New Project]       │
│                                                                   │
│  ┌─────────────────────┐  ┌─────────────────────┐               │
│  │ 🚤 Boat Marketplace │  │ 📚 Exam Cards       │               │
│  │                      │  │                      │               │
│  │ Phase: Specification │  │ Phase: Completed ✅  │               │
│  │ ████████░░ 65%       │  │ ██████████ 100%      │               │
│  │ Quality: --          │  │ Quality: 95/100 A    │               │
│  │ Last: 2 hours ago    │  │ Last: 3 days ago     │               │
│  │                      │  │                      │               │
│  │ [Continue →]         │  │ [View] [Export ↓]    │               │
│  └─────────────────────┘  └─────────────────────┘               │
│                                                                   │
│  ┌─────────────────────┐                                         │
│  │ ➕                    │                                         │
│  │                      │                                         │
│  │  Start a new project │                                         │
│  │                      │                                         │
│  └─────────────────────┘                                         │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. Settings Page

```
┌──────────────────────────────────────────────────────────────────┐
│  ⚙ Settings                                                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  API Keys                                                        │
│  ─────────                                                       │
│  Anthropic (Claude)  [sk-ant-•••••••••hf4]  ✅ Valid  [Change]   │
│  OpenAI              [Not configured]                 [Add Key]  │
│  Google (Gemini)     [Not configured]                 [Add Key]  │
│                                                                   │
│  Model Preferences                                               │
│  ─────────────────                                               │
│  Tier 1 (Reasoning): [Claude Opus 4.6      ▼]                   │
│  Tier 2 (Capable):   [Claude Sonnet 4.6    ▼]                   │
│  Tier 3 (Fast):      [Claude Haiku 4.5     ▼]                   │
│                                                                   │
│  Autonomy Levels                                                 │
│  ───────────────                                                 │
│  Strategic decisions:  ◉ Ask me  ○ Suggest  ○ Auto-decide        │
│  Technical decisions:  ○ Ask me  ◉ Suggest  ○ Auto-decide        │
│  Content decisions:    ○ Ask me  ○ Suggest  ◉ Auto-decide        │
│  Quality decisions:    ◉ Ask me  ○ Suggest  ○ Auto-decide        │
│                                                                   │
│  ℹ️  Ask me: Agent always asks before deciding                    │
│  ℹ️  Suggest: Agent shows recommendation, you approve/override    │
│  ℹ️  Auto-decide: Agent decides, you can review later             │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. New Project Flow

```
Step 1: Onboarding (if first time)
┌──────────────────────────────────────────┐
│                                           │
│  Welcome to ProjectFactory! 👋            │
│                                           │
│  Before we start, set up your AI:         │
│                                           │
│  1. Enter your API key:                   │
│     [Anthropic (Claude) ▼]                │
│     [sk-ant-_________________________]    │
│     [Validate & Save]                     │
│                                           │
│  Don't have one? [How to get an API key]  │
│                                           │
└──────────────────────────────────────────┘

Step 2: Start conversation
┌──────────────────────────────────────────┐
│                                           │
│  🤖 "Tell me about your project idea.    │
│      Describe it however feels natural    │
│      - I'll ask follow-up questions."     │
│                                           │
│  ┌────────────────────────────────────┐   │
│  │ I want to build a marketplace for  │   │
│  │ boats and marine equipment in      │   │
│  │ Turkey, like Sahibinden but        │   │
│  │ specifically for the marine sector │   │
│  └────────────────────────────────────┘   │
│                                           │
│               [Start Project →]           │
│                                           │
└──────────────────────────────────────────┘

Step 3: Redirects to Project Workspace with chat open
```

---

## 7. Responsive Design

| Breakpoint | Layout |
|-----------|--------|
| Desktop (> 1280px) | Full 3-panel layout |
| Tablet (768-1280px) | 2-panel: File explorer hidden, toggle button. Center + Chat |
| Mobile (< 768px) | Single panel with bottom nav tabs. Not optimized for MVP |

---

## 8. Design Tokens

### Colors
```
Primary:        #2563EB (Blue 600)
Secondary:      #7C3AED (Violet 600)
Success:        #16A34A (Green 600)
Warning:        #D97706 (Amber 600)
Error:          #DC2626 (Red 600)

Agent Colors:
  Orchestrator:   #6366F1 (Indigo)
  Idea Analyst:   #8B5CF6 (Violet)
  Market Rsrch:   #06B6D4 (Cyan)
  Competitor:     #F59E0B (Amber)
  Tech Feas:      #10B981 (Emerald)
  Spec Writer:    #3B82F6 (Blue)
  Architect:      #6366F1 (Indigo)
  UX Strategist:  #EC4899 (Pink)
  Quality Rev:    #EF4444 (Red)
  Devil's Adv:    #F97316 (Orange)
  Consistency:    #14B8A6 (Teal)
  Doc Formatter:  #8B5CF6 (Violet)
  Planning:       #22C55E (Green)

Background:     #0F172A (Slate 900) -- dark mode default
Surface:        #1E293B (Slate 800)
Border:         #334155 (Slate 700)
Text Primary:   #F8FAFC (Slate 50)
Text Secondary: #94A3B8 (Slate 400)
```

### Typography
```
Font Family:    Inter (UI), JetBrains Mono (code/editor)
Headings:       Inter, semibold
Body:           Inter, regular, 14px
Code:           JetBrains Mono, regular, 13px
```

### Component Library
- **Shadcn/UI** as base (Tailwind-based, customizable)
- Dark mode by default (developer audience)
- Light mode available as toggle

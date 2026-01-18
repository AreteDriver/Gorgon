# Lessons Learned - Gorgon Frontend Build
**Date:** 2026-01-18

## What We Built

Completed the Gorgon frontend dashboard - a React/TypeScript application for multi-agent orchestration.

### Pages Implemented
- **Dashboard** - System overview with stats and recent activity
- **Workflows** - Workflow list and management
- **Executions** - Execution history and monitoring
- **Budget** - Cost tracking and budget management
- **Connectors** - MCP server integration (GitHub, Slack, Notion, etc.)
- **Agents** - Agent configuration (9 agent types with provider/model settings)
- **Settings** - User preferences, API keys, notifications

### Key Features
- Dark mode with system preference detection
- Persistent user preferences via localStorage
- Mock data for demo/development
- Responsive design

---

## Technical Patterns That Worked Well

### 1. Zustand for State Management
```typescript
// Separate stores for different concerns
useUIStore        // Transient UI state (sidebar, filters)
usePreferencesStore  // Persisted preferences (theme, notifications)
```
- Simple API, minimal boilerplate
- Built-in `persist` middleware for localStorage
- No provider wrapper needed

### 2. Dark Mode with CSS Variables
```css
:root { --background: 0 0% 100%; }
.dark { --background: 222.2 84% 4.9%; }
```
- Tailwind's `darkMode: ["class"]` config
- Single class toggle on `<html>` element
- HSL values for easy color manipulation

### 3. shadcn/ui Component Patterns
- Copy-paste components, not npm packages
- Full control over styling
- Consistent design language
- Radix primitives for accessibility

### 4. React Query for Server State
```typescript
const { data, isLoading, refetch } = useMCPServers();
const mutation = useCreateMCPServer();
```
- Automatic caching and refetching
- Loading/error states built-in
- Optimistic updates possible

### 5. Conventional Commits
```
feat: add dark mode with theme toggle
fix: correct API endpoint path
docs: update README with setup instructions
```
- Clear commit history
- Easy changelog generation
- Semantic versioning support

---

## Patterns to Remember

### Component Organization
```
src/
  components/
    ui/          # Base shadcn components
    mcp/         # Feature-specific components
    ThemeToggle.tsx
  pages/         # Route-level components
  hooks/         # Custom React hooks
  stores/        # Zustand stores
  types/         # TypeScript interfaces
  api/           # API client
```

### Feature Implementation Flow
1. Define types in `types/`
2. Add API methods in `api/client.ts`
3. Create React Query hooks in `hooks/`
4. Build UI components
5. Add route in `App.tsx`
6. Update navigation

### Toggle/Switch Pattern
```tsx
<label className="relative inline-flex items-center cursor-pointer">
  <input type="checkbox" className="sr-only peer" />
  <div className="w-11 h-6 bg-muted rounded-full peer
                  peer-checked:after:translate-x-full
                  peer-checked:bg-primary
                  after:content-[''] after:absolute
                  after:top-[2px] after:left-[2px]
                  after:bg-background after:rounded-full
                  after:h-5 after:w-5 after:transition-all">
  </div>
</label>
```

---

## Things That Tripped Us Up

### 1. Port Conflicts
- Backend defaulted to 8000 (occupied)
- Solution: Run on 8001, update `.env.local` with `VITE_API_URL`

### 2. Git Rebase with Unstaged Changes
- `tsconfig.tsbuildinfo` is a build artifact
- Solution: `git stash && git pull --rebase && git stash pop`
- Consider adding to `.gitignore`

### 3. CSS File Location
- Glob pattern `frontend/src/**/*.css` returned nothing
- File was at `frontend/src/index.css`
- Solution: Use `find` as fallback

---

## Architecture Decisions

### Why Mock Data?
- Frontend can be developed independently of backend
- Demo mode works without API
- Easy to test edge cases (empty states, errors)
- Pattern: `const data = apiData || mockData;`

### Why Zustand over Redux?
- Simpler mental model
- Less boilerplate
- Built-in persistence
- Good enough for this scale

### Why CSS Variables for Theming?
- Single source of truth
- Works with Tailwind
- Easy dark mode toggle
- No runtime JS for color calculations

---

## What's Next

### Immediate Options
1. Wire frontend to real backend APIs
2. Add WebSocket for real-time execution updates
3. Build visual workflow editor
4. Add authentication flow

### Technical Debt
- Bundle size warning (>500KB) - consider code splitting
- No frontend tests yet
- API error handling could be more robust
- Loading skeletons would improve UX

---

## Commands Reference

```bash
# Development
cd frontend && npm run dev

# Build
npm run build

# Backend
cd .. && source .venv/bin/activate
uvicorn src.test_ai.api:app --port 8001 --reload

# Git workflow
git add -A && git commit -m "feat: description"
git push
```

---

## Session Stats
- ~10 files created
- ~2000 lines of TypeScript/React
- 5 commits pushed
- All 7 pages functional

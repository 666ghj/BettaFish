# Sprint [NUMBER] - [DATE RANGE]

**Sprint Goal:** [One sentence describing the main objective]
**Sprint Duration:** [Start Date] - [End Date] (2 weeks)
**Team Capacity:** [Total person-days available]

---

## Sprint Overview

### Phase: [Phase Name from Implementation Plan]

**Phase Goals:**
- [ ] Goal 1
- [ ] Goal 2
- [ ] Goal 3

**Success Criteria:**
- [ ] Criteria 1
- [ ] Criteria 2

---

## Sprint Backlog

### High Priority (Must Complete)

| ID | Task | Owner | Estimate | Status | Notes |
|----|------|-------|----------|--------|-------|
| 2.1 | Research Twitter API v2 capabilities | Backend Dev 1 | 1 day | ⏳ In Progress | API docs reviewed |
| 2.2 | Set up tweepy/Twitter SDK | Backend Dev 1 | 1 day | 📋 To Do | Waiting on API key |
| 2.3 | Implement tweet search by keyword | Backend Dev 1 | 2 days | 📋 To Do | |

**Legend:** 📋 To Do | ⏳ In Progress | ✅ Done | 🚫 Blocked

### Medium Priority (Should Complete)

| ID | Task | Owner | Estimate | Status | Notes |
|----|------|-------|----------|--------|-------|
| 2.9 | Unit tests (80%+ coverage) | Backend Dev 1 | 1 day | 📋 To Do | |
| 2.10 | Integration testing with live API | QA Engineer | 1 day | 📋 To Do | |

### Low Priority (Nice to Have)

| ID | Task | Owner | Estimate | Status | Notes |
|----|------|-------|----------|--------|-------|
| - | Code refactoring | Tech Lead | 2 hours | 📋 To Do | If time permits |

---

## Team Assignments

### Backend Dev 1: [Name]
**Focus:** Twitter crawler implementation
- [ ] Task 2.1: Research Twitter API (1 day)
- [ ] Task 2.2: Setup tweepy (1 day)
- [ ] Task 2.3: Implement search (2 days)
- [ ] Task 2.4: Tweet metadata (1 day)
- [ ] Task 2.5: Reply extraction (2 days)

**Estimated Load:** 7 days / 10 available = 70%

### Backend Dev 2: [Name]
**Focus:** Database schema updates
- [ ] Task 1.1: Design USA platform data models (2 days)
- [ ] Task 1.2: Create migration scripts (1 day)
- [ ] Task 1.3: Implement Twitter model (1 day)

**Estimated Load:** 4 days / 10 available = 40%

### ML Engineer: [Name]
**Focus:** Sentiment model evaluation
- [ ] Task 4.1: Evaluate multilingual model (1 day)
- [ ] Task 4.2: Create test dataset (2 days)

**Estimated Load:** 3 days / 10 available = 30%

### Frontend Dev: [Name]
**Focus:** UI mockups and planning
- [ ] Design new report template mockup (2 days)
- [ ] Review Chart.js for data viz (1 day)

**Estimated Load:** 3 days / 10 available = 30%

### QA Engineer: [Name]
**Focus:** Test infrastructure setup
- [ ] Set up integration test framework (2 days)
- [ ] Create mock API servers (2 days)
- [ ] Write first crawler tests (1 day)

**Estimated Load:** 5 days / 10 available = 50%

---

## Daily Standup Notes

### Monday, [Date]
**Backend Dev 1:**
- Yesterday: Set up development environment
- Today: Start Task 2.1 (Twitter API research)
- Blockers: None

**Backend Dev 2:**
- Yesterday: Reviewed existing DB schema
- Today: Begin Task 1.1 (design USA models)
- Blockers: None

**[Continue for all team members]**

---

### Tuesday, [Date]
**Backend Dev 1:**
- Yesterday: Completed Twitter API research
- Today: Setting up tweepy SDK
- Blockers: Waiting on API credentials

**Backend Dev 2:**
- Yesterday: Started ERD for USA platforms
- Today: Complete ERD, review with team
- Blockers: None

---

### Wednesday, [Date]
[Update daily]

---

### Thursday, [Date]
[Update daily]

---

### Friday, [Date]
[Update daily - also prepare for sprint demo]

---

## Risks & Blockers

| Risk/Blocker | Impact | Owner | Mitigation | Status |
|--------------|--------|-------|------------|--------|
| Twitter API credentials delayed | HIGH | Backend Dev 1 | Use mock API for development | 🟡 Active |
| Uncertainty about schema design | MEDIUM | Backend Dev 2 | Schedule review with Tech Lead | 🟢 Resolved |

---

## Sprint Review (End of Sprint)

### Completed Work

**✅ What We Shipped:**
1. [Feature/Task 1] - [Brief description]
2. [Feature/Task 2] - [Brief description]
3. [Feature/Task 3] - [Brief description]

**📊 Metrics:**
- Story points completed: [X] / [Y] planned
- Velocity: [X] points
- Bugs found: [X]
- Bugs fixed: [X]
- Test coverage: [X]%

### Demo Notes

**Demonstrated Features:**
1. [Feature 1]: [What was shown, feedback received]
2. [Feature 2]: [What was shown, feedback received]

**Stakeholder Feedback:**
- [Feedback item 1]
- [Feedback item 2]

### Incomplete Work

**🚧 Carried Over to Next Sprint:**
1. [Task 1] - [Reason not completed]
2. [Task 2] - [Reason not completed]

---

## Sprint Retrospective

### What Went Well 🎉
- [Positive item 1]
- [Positive item 2]
- [Positive item 3]

### What Needs Improvement 🔧
- [Improvement item 1]
- [Improvement item 2]

### Action Items for Next Sprint 🎯
- [ ] [Action 1] - Owner: [Name]
- [ ] [Action 2] - Owner: [Name]
- [ ] [Action 3] - Owner: [Name]

---

## Metrics & Analytics

### Burndown Chart
```
[Visual representation or link to burndown chart]

Story Points Remaining:
Day 1:  [X]
Day 2:  [X]
Day 3:  [X]
...
Day 10: [X]
```

### Code Quality Metrics
- **Test Coverage:** [X]% (Target: 80%)
- **Code Review Turnaround:** [X] hours average (Target: <24h)
- **Build Success Rate:** [X]% (Target: 95%+)
- **Critical Bugs:** [X] (Target: 0)

### Team Velocity Tracking
```
Sprint 1: [X] points
Sprint 2: [X] points
Sprint 3: [X] points
Average: [X] points
```

---

## Definition of Done

Before marking any task as ✅ Done, ensure:

**Code Quality:**
- [ ] Code follows style guide (black, flake8)
- [ ] Type hints added (mypy passing)
- [ ] No new linting errors
- [ ] Code reviewed and approved

**Testing:**
- [ ] Unit tests written (80%+ coverage for new code)
- [ ] Integration tests passing
- [ ] Manual testing completed
- [ ] No regression in existing tests

**Documentation:**
- [ ] Code comments added for complex logic
- [ ] API documentation updated (if applicable)
- [ ] README updated (if applicable)
- [ ] CHANGELOG.md updated

**Integration:**
- [ ] Merged to develop branch
- [ ] CI/CD pipeline passing
- [ ] Deployed to staging environment
- [ ] Smoke tests passing on staging

---

## Next Sprint Planning

### Proposed Goals for Sprint [N+1]:
1. [Goal 1]
2. [Goal 2]
3. [Goal 3]

### Backlog Priorities:
1. [High priority task from backlog]
2. [High priority task from backlog]

### Team Capacity Changes:
- [Any team member availability changes]
- [Any new team members joining]
- [Any planned time off]

---

## Notes & Decisions

**Technical Decisions:**
- [Date]: Decision to use [Technology X] because [Reason]
- [Date]: Decided to prioritize [Feature Y] over [Feature Z]

**Meeting Notes:**
- [Date]: Sprint planning meeting - Key discussion points
- [Date]: Tech sync - Architectural decisions

**Important Links:**
- Sprint board: [Jira/Trello link]
- GitHub milestone: [Link]
- Design docs: [Link]

---

## Template Usage Instructions

**How to Use This Template:**

1. **Copy this template** at the start of each sprint
2. **Rename** to `SPRINT_[NUMBER]_[START_DATE].md`
3. **Fill in** sprint goals and tasks from Implementation Plan
4. **Update daily** with standup notes
5. **Complete** sprint review and retrospective at end
6. **Archive** in `sprints/` folder for historical tracking

**Example Sprint Files:**
```
sprints/
├── SPRINT_01_2025-11-10.md
├── SPRINT_02_2025-11-24.md
├── SPRINT_03_2025-12-08.md
└── ...
```

---

*Sprint template version 1.0 - Last updated: 2025-11-09*

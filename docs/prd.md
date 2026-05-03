## Problem Statement

The company needs an internal recognition portal where employees can quickly
recognize each other for help received or excellent work, while also supporting
manager-controlled points that can later be redeemed for gift cards. The
current prototype does not match the desired product shape: it lacks real
authentication, a durable employee directory, a usable approval model, reward
ledgering, redemption workflows, and maintainable boundaries between product
policies and UI behavior.

The product must optimize for low-friction adoption. Non-monetary recognition
should feel immediate and social. Points-based recognition should feel
controlled but not bureaucratic. The system is intended to be a lightweight
culture tool with reward features, not a formal compliance-grade rewards
platform.

## Solution

Build a responsive web application for one company directory with company-email
magic-link login, employee and manager directory management, immediate
non-monetary recognition, manager-approved points-based recognition using fixed
point presets, a public internal feed for approved/public recognitions, a
personal points ledger, region-based gift card redemption, and lightweight
admin tooling for budgets, fulfillment, moderation, and reporting.

The product should separate the appreciation loop from the reward loop:

- Non-monetary recognition publishes immediately and notifies the recipient and
  the recipient's manager.
- Points-based recognition is submitted by an employee, reviewed by the
  sender's manager, and only published after approval.
- Approved points accumulate in a balance that employees redeem later through a
  regional gift card catalog.

## User Stories

1. As an employee, I want to log in with a magic link sent to my company email,
   so that I can access the portal without managing another password.
2. As an employee, I want access limited to active employees, so that the
   portal stays internal to the company.
3. As an employee who is not yet fully configured in the employee directory, I
   want to be blocked from acting until admin approval, so that the system can
   maintain an accurate org structure.
4. As an employee, I want to recognize a coworker for great work, so that I
   can express appreciation quickly.
5. As an employee, I want to send non-monetary recognition in under 30 seconds,
   so that the act of appreciation becomes habitual.
6. As an employee, I want to choose one or more recipients in a recognition, so
   that I can thank a small group when appropriate.
7. As an employee, I want self-recognition blocked, so that the system remains
   credible.
8. As an employee, I want duplicate recognition to the same person blocked for
   a short period, so that the system discourages spam and gaming.
9. As an employee, I want a required recognition category, so that the company
   can report on themes like teamwork or ownership.
10. As an employee, I want an optional company-value tag, so that recognition
    can reinforce culture without adding too much friction.
11. As an employee, I want a simple text-only message field, so that I can
    submit appreciation without dealing with uploads or attachments.
12. As an employee, I want message length rules, so that messages are neither
    empty nor unmanageably long.
13. As an employee, I want non-monetary recognition to appear immediately in
    the company feed, so that appreciation feels timely.
14. As an employee, I want points-based recognition to stay private until
    approved, so that recipients do not see uncertain rewards.
15. As an employee, I want to request points-based recognition using fixed
    presets, so that reward requests stay simple and policy-aligned.
16. As an employee, I want points presets to be limited to 10, 25, and 50, so
    that the system avoids fake precision and budget drift.
17. As an employee, I want points in a shared recognition to be per recipient,
    so that total budget impact is explicit and understandable.
18. As an employee, I want to know when my points-based recognition is pending,
    approved, approved with changes, or rejected, so that I know where it
    stands.
19. As an employee, I want to edit, cancel, or delete a points-based request
    before it is approved or rejected, so that I can fix mistakes without
    needing admin help.
20. As an employee, I want any pending-request edit to trigger a fresh review,
    so that the manager never approves stale content.
21. As an employee, I want a rejected points request to be easy to resubmit
    from a prefilled draft, so that I do not have to recreate it from scratch.
22. As an employee, I want recipients of points-based recognition to be
    notified only after final approval, so that expectations stay clear.
23. As an employee, I want to receive a notification when someone recognizes
    me, so that appreciation reaches me directly.
24. As an employee, I want to see a company-wide recognition feed, so that the
    portal creates visible culture rather than private transactions.
25. As an employee, I want the feed to be ordered by recency, so that the
    behavior is easy to understand.
26. As an employee, I want no comments or reactions in v1, so that the product
    stays focused on recognition instead of social chatter.
27. As an employee, I want to see my sent recognitions, so that I can remember
    what I have acknowledged.
28. As an employee, I want to see my received recognitions, so that I can track
    appreciation I have earned.
29. As an employee, I want to see my current points balance, so that I know
    what I can redeem.
30. As an employee, I want a full personal points ledger with earned and spent
    entries, so that my balance feels trustworthy.
31. As an employee, I want to redeem points for a gift card, so that rewards
    become tangible.
32. As an employee, I want redemption to be based on a catalog available in my
    assigned region, so that I only see rewards the company can actually
    fulfill for me.
33. As an employee, I want redemption to fail safely with point restoration if
    fulfillment cannot happen, so that I do not lose points unfairly.
34. As an employee, I want to browse the system easily on my phone, so that I
    can use it as a responsive web app without needing a native app.
35. As a manager, I want a monthly point budget, so that I can control reward
    spend for my team.
36. As a manager, I want unused budget not to roll over, so that monthly spend
    is simple and predictable.
37. As a manager, I want to approve points requests from my direct reports, so
    that budget ownership matches the sender side of the workflow.
38. As a manager, I want to see total budget impact on a multi-recipient points
    request, so that I understand the actual spend before approving it.
39. As a manager, I want to be prevented from approving more than my remaining
    budget, so that the system enforces the monthly limit.
40. As a manager, I want to choose manually which requests to approve when
    demand exceeds remaining budget, so that I keep judgment over tradeoffs.
41. As a manager, I want to remove some recipients from a pending request, so
    that I can narrow the approval scope without rejecting the whole request.
42. As a manager, I want to reduce points on a pending request, so that I can
    keep the recognition while right-sizing the spend.
43. As a manager, I want to be blocked from adding recipients or increasing
    points, so that I do not author recognitions on behalf of employees.
44. As a manager, I want a required explanation when I change recipients or
    points, so that the sender understands what changed.
45. As a manager, I want rejection reasons to be required, so that employees
    get clear closure.
46. As a manager, I want approval reminders before SLA breach, so that pending
    requests do not quietly stall.
47. As a manager, I want approvals escalated if I am unavailable, so that team
    recognition does not dead-end.
48. As a manager who is also a sender, I want my own manager to approve my
    points-based request, so that I cannot self-approve spend.
49. As a recipient's manager, I want to know when my team member receives
    non-monetary recognition, so that I get timely visibility into their
    contribution.
50. As a sender's manager, I want visibility into points requests requiring my
    action, so that I can keep recognition flowing.
51. As a moderator-capable manager, I want to hide or remove inappropriate
    recognition, so that I can protect employees from abuse.
52. As a moderator-capable manager, I want moderation to remove visibility for
    normal users, so that harmful content does not linger.
53. As an admin, I want to import employees from CSV, so that launch does not
    depend on a live HR integration.
54. As an admin, I want to edit employee records after import, so that org data
    can keep up with a changing startup.
55. As an admin, I want to assign each employee one manager and one region, so
    that approvals and catalogs behave deterministically.
56. As an admin, I want to approve access requests from users not fully present
    in the directory, so that the system can stay flexible without losing
    control.
57. As an admin, I want to manage monthly manager budgets, so that reward spend
    can be configured centrally.
58. As an admin, I want to manage region-specific reward catalogs, so that gift
    card options match local availability.
59. As an admin, I want employees to initiate their own redemption requests, so
    that reward usage remains employee-driven.
60. As an admin, I want to fulfill redemptions operationally, so that gift-card
    issuance stays controlled.
61. As an admin, I want the ability to cancel a redemption and restore points,
    so that failures or vendor issues can be handled cleanly.
62. As an admin, I want moderation authority over all recognitions, so that
    escalated issues can be resolved centrally.
63. As an admin, I want a hidden event trail for sensitive changes, so that the
    lightweight system still preserves some operational truth.
64. As an admin, I want reports on recognition volume, points granted, budgets,
    balances, redemptions, and moderation, so that I can operate the program.
65. As an admin, I want CSV export, so that I can analyze the data outside the
    app when needed.
66. As an executive, I want to send recognition like any other employee, so
    that leadership can participate in the culture loop.
67. As an executive, I want to be restricted to non-monetary recognition as a
    recipient, so that special-role reward concerns stay controlled.
68. As the company, I want the portal to support adoption before complexity, so
    that the first release proves behavior change rather than feature breadth.

## Implementation Decisions

- The current single-file prototype should be treated as a throwaway baseline
  rather than the long-term architecture.
- The product should be rebuilt as a proper web application with clear
  separation between domain logic, authentication, notification delivery, admin
  operations, and UI.
- Core deep modules should include:
  - an employee directory and org-structure module
  - a recognition workflow module
  - a manager budget and approval module
  - a points ledger module
  - a redemption and catalog module
  - a moderation and admin operations module
  - a notification event module
- Authentication should use magic-link login tied to company email identity.
- Employee participation should require active status in the directory, even if
  an unconfigured user is allowed to complete the login step before approval.
- Recognition should have two product types:
  - non-monetary
  - points-based
- Category is required on every recognition.
- Company value is optional and single-select.
- Messages are plain text only with a 20 to 500 character range.
- Multi-recipient recognition is allowed.
- Points presets are fixed at 10, 25, and 50.
- Points are interpreted per recipient, not per submission total.
- Sender's manager is the default approver for points-based recognition.
- If the sender is also the approver, approval escalates to the sender's
  manager.
- If the escalation chain breaks because no manager exists, fallback goes to
  admin.
- Managers may reduce points or remove recipients, but may not add recipients,
  increase points, or rewrite the recognition message.
- Any edit to a pending points request resets the approval review.
- Rejected requests remain closed; resubmission creates a new request linked to
  the earlier one.
- Manager budgets are monthly, non-rollover, and consumed only when a request
  is approved.
- Company feed is company-wide and recency-ordered.
- Non-monetary recognitions publish immediately.
- Points-based recognitions publish only after approval.
- Executives may receive non-monetary recognition but not points-based
  recognition.
- Reward catalogs are region-specific, and region is an admin-owned employee
  attribute.
- Employees initiate redemption.
- Redemptions use a simple status model that supports fulfillment and
  restoration without substitution workflow.
- Employee personal point history should be represented as a real ledger, not
  just a derived balance field.
- Search in v1 is limited to employee lookup rather than full-text message
  search.
- Email notifications are required.
- In-app notifications are optional and the first feature cut if scope slips.
- The product is explicitly a lightweight culture tool with reward features,
  which means trust and audit concerns should be addressed pragmatically rather
  than by building a full compliance-grade system.

## Testing Decisions

- Good tests should validate external behavior and workflow outcomes, not
  implementation details or private helper structure.
- The most important tests are end-to-end workflow tests over the domain
  modules:
  - non-monetary recognition publication
  - points-based submission and approval
  - manager modification of pending requests
  - rejection and prefilled resubmission
  - budget enforcement
  - duplicate/spam blocking
  - executive restrictions
  - redemption submission, fulfillment, and point restoration
  - moderation visibility outcomes
- Authentication should be tested through behavior such as token issuance,
  expiry, and consumed-token rejection.
- The employee directory module should be tested for CSV import, manager
  mapping, region assignment, and activation gating.
- The points ledger should be tested as a source of truth for balances rather
  than only through summary views.
- Notification behavior should be tested at the event level first, with
  delivery adapters mocked or stubbed.
- Route or controller tests should focus on role permissions and major state
  transitions.
- The existing repo has no meaningful prior-art test suite; the current
  `test_email.py` script should not be treated as a real test pattern and
  should be replaced with actual automated tests around notification behavior.

## Out of Scope

- Native mobile applications
- Teams bot behavior in v1
- Comments and reactions
- Attachments
- Full-text search over recognition messages
- Leaderboards
- Multi-company or multi-subsidiary recognition scope
- Payroll cash conversion
- Rich substitution workflows during redemption
- Strong end-user-facing immutable audit UX
- AI-based message quality scoring

## Further Notes

- The primary success metric is the percentage of active employees who send or
  receive at least one recognition in the first 60 days.
- The primary product risk to optimize against is adoption friction, not
  maximum policy sophistication.
- The current repository does not define an issue tracker or triage-label
  vocabulary, so this PRD is currently stored locally rather than published into
  a tracker with a `needs-triage` label.
- If this needs to be published to GitHub Issues, the next required setup is a
  concrete issue target plus authenticated issue-creation access from this
  environment.

"""Dummy data for the POC. Everything here is illustrative, as the wireframe states."""
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (Challenge, CommunityMember, Experiment, Horizon, Idea, ImpactMetric,
                        InnovationType, LearningModule, LearningPath, LibraryItem,
                        PortfolioStat, Stage, User, UserPathProgress)

HORIZONS = [
    ("Core", "Protect and optimise today's business.", "Protect and optimise today"),
    ("Adjacent", "Expand into new growth spaces.", "Expand into new growth spaces"),
    ("Transformational", "Create future growth engines.", "Create future growth engines"),
]

TYPES = [
    ("Profit Model", "How we make money"),
    ("Network", "How we connect with others"),
    ("Structure", "How we organise and align talent"),
    ("Process", "How we do our work"),
    ("Product Performance", "Features and function of our offering"),
    ("Product System", "How offerings connect and complement"),
    ("Service", "How we support and enhance value"),
    ("Channel", "How we reach customers"),
    ("Brand", "How we represent and build trust"),
    ("Customer Engagement", "How we interact and build relationships"),
]

STAGES = [
    ("Source", "Capture opportunities from clients, colleagues, partners and market signals."),
    ("Assess", "Evaluate strategic fit, customer value, feasibility, risk and potential impact."),
    ("Test", "Run proportionate experiments to validate assumptions."),
    ("Scale / Adapt / Stop", "Fund what works, adapt what shows promise and stop what does not."),
]

USERS = [
    ("Alex Mwangi", "AM"), ("Wanjiku Otieno", "WO"), ("Brian Kamau", "BK"), ("Faith Njeri", "FN"),
    ("Peter Mutua", "PM"), ("Amina Hassan", "AH"), ("Daniel Ochieng", "DO"),
    ("Grace Wairimu", "GW"), ("Samuel Kiptoo", "SK"), ("Linet Achieng", "LA"),
]

# name -> (completed learning paths, submitted ideas, drafts, duplicates)
COLLEAGUES = {
    "Wanjiku Otieno": (6, 6, 0, 0), "Brian Kamau": (5, 7, 1, 0), "Faith Njeri": (4, 5, 0, 1),
    "Peter Mutua": (3, 4, 0, 0), "Amina Hassan": (3, 3, 1, 0), "Daniel Ochieng": (2, 4, 0, 0),
    "Grace Wairimu": (2, 3, 0, 1), "Samuel Kiptoo": (1, 2, 0, 0), "Linet Achieng": (0, 1, 1, 0),
}

CHALLENGES = [
    dict(title="Improve claims experience", source="Client insights", horizon="Core",
         types=["Service", "Process"], sponsor="Operations", featured=True,
         hmw="How might we reduce friction across the claims journey while improving trust and service visibility?",
         background="Clients often do not know where a claim sits or what happens next, and service teams spend time answering status requests. This is illustrative context for the proof of concept.",
         success="Clients can see claim progress and next steps without chasing, and service teams spend less time on repeat status requests."),
    dict(title="Smarter distribution", source="Partners", horizon="Adjacent",
         types=["Channel", "Network"], sponsor="Distribution", featured=False,
         hmw="How might we equip intermediaries and partners to reach underserved segments with more relevant offers and support?",
         background="Partners and intermediaries reach segments that direct channels do not, but onboarding and support vary widely. This is illustrative context for the proof of concept.",
         success="Partners can onboard quickly, offer relevant products to underserved segments and get support when they need it."),
    dict(title="Digital risk intelligence", source="Market signals", horizon="Transformational",
         types=["Product System", "Profit Model"], sponsor="Risk & Advisory", featured=False,
         hmw="How might we turn available risk data into more proactive client advice, better risk selection and new advisory revenue streams?",
         background="Risk data from several sources is rarely combined into advice that clients can act on. This is illustrative context for the proof of concept.",
         success="Clients receive timely, data-backed risk advice, and the firm tests a new advisory revenue stream with evidence."),
    dict(title="Improve operational efficiency", source="Employee ideas", horizon="Core",
         types=["Process"], sponsor="Operations", featured=False,
         hmw="How might we reduce repeat work and hand-offs across service teams while keeping quality high and turnaround times predictable?",
         background="Colleagues report repeated data entry and unclear hand-offs between service teams. This is illustrative context for the proof of concept.",
         success="Fewer hand-offs and repeat tasks, with turnaround times that clients and colleagues can predict."),
    dict(title="Develop new advisory services", source="Employee ideas", horizon="Adjacent",
         types=["Service", "Network"], sponsor="Advisory", featured=False,
         hmw="How might we build practical advisory services that help clients navigate risk, recovery and long-term resilience?",
         background="Colleagues see client needs that sit beside core broking, such as recovery planning and resilience. This is illustrative context for the proof of concept.",
         success="One or two practical advisory services tested with real clients, with clear evidence of value."),
]

STUB_TITLES = [
    "Shared claims document checklist", "Renewal reminder timeline", "Client risk survey template",
    "Broker onboarding video series", "Policy summary in plain language", "Claims photo upload guide",
    "Quarterly client resilience review", "Partner referral tracker", "Faster quote comparison view",
    "Standard meeting notes format", "Self-service certificate requests", "Claims triage questions",
    "Client health check calendar", "Intermediary FAQ library", "Simple endorsement request form",
    "Risk survey photo guide", "Cross-team hand-off checklist", "Plain-language renewal letters",
    "Client feedback after claim closure", "Weekly service team huddle", "Document naming standard",
    "Intermediary training snippets", "Regional claims contact map", "Policy change notification email",
    "Colleague skills directory", "Client portal tour", "Quick-start guide for new clients",
    "Claims status SMS", "Shared inbox ownership rules", "Annual client resilience report",
    "Cover comparison one-pager", "Partner support hotline script", "Automated reminder for missing documents",
    "Claims cost insight dashboard", "Onboarding buddy programme", "Standard client brief template",
    "Underwriter question library", "Lessons library tagging", "Client newsletter on risk trends",
    "Small business starter pack",
]

PATHS = [
    dict(title="Understand customer needs and opportunities", section="recommended", badge="40%",
         description="Use customer insight to improve the claims experience.",
         recommended_for="Improve claims experience: Core • Service / Process",
         footer="Illustrative", cta=None, action="Continue customer-needs learning",
         modules=[("Why customer needs come first", "Start from the client problem, not the solution.", 8),
                  ("Interviewing clients and colleagues", "Ask open questions and listen for friction.", 12),
                  ("Mapping the claims journey", "Draw the journey and mark where clients wait or worry.", 15),
                  ("Finding friction and opportunity", "Group what you heard into themes worth acting on.", 10),
                  ("Turning insight into a testable idea", "Write a specific idea you can check with a small test.", 12)]),
    dict(title="Discover the ten types of innovation", section="recommended", badge="10 TYPES",
         description="Explore different ways to innovate, including Service and Process.",
         footer="Doblin model • 10 types", cta="Explore types", modules="TYPES"),
    dict(title="Develop propositions and solutions", section="recommended", badge="PATH",
         description="Shape the next version of your digital claims status prototype.",
         footer="Linked to your claims test", cta=None, experiment=1,
         modules=[("Shaping a proposition", "Say who it is for and why it matters.", 10),
                  ("Sketching a solution", "Show the idea on one page.", 12),
                  ("Prototyping a status view", "Build the smallest version a client could react to.", 15),
                  ("Preparing for feedback", "Plan how to hear what works and what does not.", 8)]),
    dict(title="Experiment and validate assumptions", section="next",
         description="Plan proportionate tests before your claims review on 18 Nov.",
         footer="Linked to your claims test", cta=None,
         modules=[("Naming the riskiest assumption", "Decide what must be true for the idea to work.", 10),
                  ("Designing a proportionate test", "Keep the test small, quick and safe.", 14),
                  ("Choosing evidence and measures", "Agree what you will collect before you start.", 12),
                  ("Deciding what happens next", "Adapt, stop or seek a scale decision.", 10)]),
    dict(title="Build partnerships and explore business models", section="next",
         description="Relevant to your Adjacent customer onboarding opportunity: Channel / Network.",
         footer="Linked to your onboarding idea", cta=None,
         modules=[("Why partners matter", "Where partners reach clients we cannot.", 8),
                  ("Mapping partner value", "What each side gives and gets.", 12),
                  ("Exploring business models", "Compare ways of earning and sharing value.", 14),
                  ("Starting a partner conversation", "Prepare a clear first request.", 8)]),
    dict(title="Problem framing basics", section="catalog",
         description="Describe a problem clearly before looking for a solution.", footer="Illustrative", cta=None,
         modules=[("What makes a good problem statement", "Who, what, when and why it matters.", 8),
                  ("Asking better questions", "Move from symptoms to causes.", 10),
                  ("Writing the problem down", "Draft and test a one-line statement.", 8)]),
    dict(title="Working with data and evidence", section="catalog",
         description="Use simple data to support an idea without overstating it.", footer="Illustrative", cta=None,
         modules=[("What counts as evidence", "Separate observation from opinion.", 8),
                  ("Collecting a small sample", "Enough to learn, not enough to mislead.", 12),
                  ("Reading results honestly", "What the data does and does not show.", 10),
                  ("Recording what you learned", "Make learning reusable.", 8)]),
    dict(title="Storytelling for innovators", section="catalog",
         description="Explain an idea so a sponsor can decide quickly.", footer="Illustrative", cta=None,
         modules=[("Start with the client", "Lead with the problem someone has.", 8),
                  ("One page, one ask", "Make the decision easy.", 10),
                  ("Showing evidence", "Use proof, not adjectives.", 8)]),
]

IMPACT = {
    "Core": ["Efficiency", "Quality", "Adoption", "Satisfaction", "Retention"],
    "Adjacent": ["New-client growth", "Cross-sell", "Partner value", "Adoption"],
    "Transformational": ["Revenue from new business models", "Platform traction", "Strategic options created"],
}

LIBRARY = {
    "playbooks": [("Proportionate usability test checklist", "Checklist", "Steps for running a small usability test and recording what you saw."),
                  ("Assumption mapping template", "Template", "List your assumptions and mark which matter most and which you know least about."),
                  ("One-page experiment brief", "Template", "Question, method, evidence to collect, owner and decision date on a single page.")],
    "case-studies": [("Digital claims status prototype: early learning", "Illustrative case", "A sample write-up of what a status prototype test could capture."),
                     ("Automated document intake: what we adapted", "Illustrative case", "A sample write-up of adapting a test after early results."),
                     ("Partner onboarding pilot: sample write-up", "Illustrative case", "A sample of how a partner pilot might be recorded.")],
    "market-insights": [("Digital claims trends in African insurance markets", "Illustrative summary", "Placeholder summary of external trends in claims service."),
                        ("Embedded insurance and distribution partners", "Illustrative summary", "Placeholder summary of partner-led distribution models."),
                        ("Using risk data for advisory", "Illustrative summary", "Placeholder summary of data-led advisory offers.")],
    "lessons": [("Why a test was stopped early", "Illustrative lesson", "A sample lesson showing how stopping early saved time and effort."),
                ("Small samples can mislead", "Illustrative lesson", "A sample lesson on reading small test results with care."),
                ("Clear owners speed decisions", "Illustrative lesson", "A sample lesson on naming a decision owner at the start.")],
}


def seed(db: Session) -> None:
    horizons = {n: Horizon(name=n, description=d, short_description=s, sort_order=i)
                for i, (n, d, s) in enumerate(HORIZONS, 1)}
    types = {n: InnovationType(name=n, short_description=d, sort_order=i)
             for i, (n, d) in enumerate(TYPES, 1)}
    stages = {n: Stage(name=n, description=d, sort_order=i) for i, (n, d) in enumerate(STAGES, 1)}
    users = {n: User(name=n, initials=i, email=n.lower().replace(" ", ".") + "@example.com", role="Employee")
             for n, i in USERS}
    db.add_all([*horizons.values(), *types.values(), *stages.values(), *users.values()])
    db.flush()

    # Challenges
    for i, c in enumerate(CHALLENGES, 1):
        db.add(Challenge(title=c["title"], how_might_we=c["hmw"], source=c["source"],
                         horizon_id=horizons[c["horizon"]].id, sponsor=c["sponsor"], status="OPEN",
                         is_illustrative=True, is_featured=c["featured"], background=c["background"],
                         success_looks_like=c["success"], sort_order=i,
                         types=[types[t] for t in c["types"]]))
    db.flush()
    challenge_ids = {c.title: c.id for c in db.scalars(select(Challenge))}

    alex = users["Alex Mwangi"]
    sponsor = "Operations lead (illustrative role)"

    def new_idea(owner, **kw) -> Idea:
        type_names = kw.pop("type_names", [])
        idea = Idea(owner_id=owner.id, types=[types[t] for t in type_names], **kw)
        db.add(idea)
        db.flush()
        if idea.status != "Draft":
            idea.reference_id = f"IDEA-2026-{idea.id:04d}"
        return idea

    # Alex's own records (ids 1 and 2 are the two ideas in the wireframe)
    idea1 = new_idea(
        alex, title="Simplify claims status updates", status="In review", stage_id=stages["Assess"].id,
        horizon_id=horizons["Core"].id, type_names=["Service", "Process"], sponsor=sponsor,
        problem="Clients often chase for claim updates by phone or email and cannot see where a claim sits.",
        solution="Send short status updates at each claims milestone, with a clear next step.",
        expected_value="Fewer status calls and clearer service for clients.",
        evidence="Illustrative: service teams report frequent status requests.",
        next_label="Next action", next_text="Review customer insight",
        challenge_id=challenge_ids["Improve claims experience"], is_illustrative=True,
        created_at=datetime(2026, 10, 6, 9, 30), submitted_at=datetime(2026, 10, 6, 9, 30))
    new_idea(
        alex, title="Customer onboarding checklist", status="Needs clarification", stage_id=stages["Assess"].id,
        horizon_id=horizons["Adjacent"].id, type_names=["Channel", "Network"],
        problem="New clients and partners get different onboarding steps depending on who they speak to.",
        solution="Offer one shared checklist that shows each step and who owns it.",
        expected_value="Faster, more consistent onboarding.",
        evidence="Illustrative: partners ask for a clear list of onboarding steps.",
        next_label="Next action", next_text="Clarify partner onboarding insight",
        action_label="Clarify customer onboarding insight",
        challenge_id=challenge_ids["Smarter distribution"], is_illustrative=True,
        created_at=datetime(2026, 10, 14, 11, 0), submitted_at=datetime(2026, 10, 14, 11, 0))

    notes = {
        "Strategic alignment": "Core claims experience",
        "Customer value": "Clearer service visibility",
        "Feasibility": "Check integration needs",
        "Risk and compliance": "Confirm consent, privacy and data access",
        "Potential impact": "Service quality and satisfaction; evidence still needed",
    }
    exp1 = Experiment(
        title="Digital claims status prototype", owner_id=alex.id, horizon_id=horizons["Core"].id,
        stage_id=stages["Test"].id, status="Testing", sponsor=sponsor, idea_id=idea1.id,
        next_label="Next decision", next_text="Review evidence, 18 Nov",
        next_decision_date=date(2026, 11, 18), action_label="Review claims test on 18 Nov",
        evidence_learning=("Illustrative insight: clients need clearer status and next-step information.\n"
                           "Evidence to collect: task completion and comprehension in a small usability test.\n"
                           "Learning is provisional; no business benefit has been validated."),
        resource_decision="Request a proportionate usability test; funding approval pending.",
        review_notes=notes, is_illustrative=True, types=[types["Service"], types["Process"]])
    exp2 = Experiment(
        title="Automated document intake", owner_id=alex.id, horizon_id=horizons["Core"].id,
        stage_id=stages["Test"].id, status="Learning captured", sponsor=sponsor,
        next_label="Next action", next_text="Adapt test; decision pending",
        evidence_learning=("Illustrative insight: missing documents cause most intake delays.\n"
                           "Evidence to collect: how often documents arrive incomplete after the new prompt.\n"
                           "Learning is provisional; no business benefit has been validated."),
        resource_decision="No additional resources requested yet.",
        review_notes={**notes, "Strategic alignment": "Core operational efficiency",
                      "Customer value": "Faster turnaround on new business"},
        is_illustrative=True, types=[types["Process"]])
    db.add_all([exp1, exp2])
    db.flush()

    # Colleague ideas (counts drive the sample ideas leaderboard)
    n = 0
    htypes = list(horizons)
    statuses = ["Submitted", "In review", "In review", "Needs clarification"]
    for name, (_, submitted, drafts, dups) in COLLEAGUES.items():
        owner = users[name]
        for k in range(submitted + drafts + dups):
            title = STUB_TITLES[n % len(STUB_TITLES)]
            n += 1
            is_draft, is_dup = k >= submitted and k < submitted + drafts, k >= submitted + drafts
            status = "Draft" if is_draft else statuses[k % 4]
            stage = "Source" if status in ("Draft", "Submitted") else "Assess"
            created = datetime(2026, 10, 1) + timedelta(days=(n * 3) % 38, hours=n % 9)
            new_idea(owner, title=title, status=status, stage_id=stages[stage].id,
                     horizon_id=horizons[htypes[n % 3]].id,
                     type_names=list({TYPES[n % 10][0], TYPES[(n * 3) % 10][0]}),
                     problem="Illustrative sample idea.", is_duplicate=is_dup, is_illustrative=True,
                     created_at=created, submitted_at=None if is_draft else created,
                     next_text="Illustrative sample")

    # Learning paths
    for i, p in enumerate(PATHS, 1):
        mods = ([(t, d, 6) for t, d in TYPES] if p["modules"] == "TYPES" else p["modules"])
        path = LearningPath(
            title=p["title"], description=p["description"], section=p["section"], badge=p.get("badge"),
            footer_label=p["footer"], cta_label=p["cta"], recommended_for=p.get("recommended_for"),
            action_label=p.get("action"), linked_experiment_id=exp1.id if p.get("experiment") else None,
            sort_order=i,
            modules=[LearningModule(title=t, summary=s, minutes=m, sort_order=j)
                     for j, (t, s, m) in enumerate(mods, 1)])
        db.add(path)
    db.flush()
    paths = list(db.scalars(select(LearningPath).order_by(LearningPath.sort_order)))

    # Alex: path 1 is 2 of 5 modules (40%); path 6 completed (1 completed path)
    db.add(UserPathProgress(user_id=alex.id, path_id=paths[0].id, completed_modules=2))
    db.add(UserPathProgress(user_id=alex.id, path_id=paths[5].id, completed_modules=len(paths[5].modules),
                            completed_at=datetime(2026, 10, 20, 15, 0)))
    for name, (done, *_rest) in COLLEAGUES.items():
        for path in paths[:done]:
            db.add(UserPathProgress(user_id=users[name].id, path_id=path.id,
                                    completed_modules=len(path.modules),
                                    completed_at=datetime(2026, 10, 25, 10, 0)))
    for name in ("Wanjiku Otieno", "Brian Kamau", "Faith Njeri"):
        db.add(CommunityMember(user_id=users[name].id))

    # Impact metrics: all pending, as the wireframe states
    for hname, metrics in IMPACT.items():
        for j, m in enumerate(metrics, 1):
            db.add(ImpactMetric(horizon_id=horizons[hname].id, name=m, status="To be measured", sort_order=j))

    for i, (k, label, v) in enumerate([("ideas_submitted", "Ideas submitted", 86),
                                       ("experiments_underway", "Experiments underway", 12),
                                       ("pilots_launched", "Pilots launched", 4),
                                       ("validated_outcomes", "Validated business outcomes", None)], 1):
        db.add(PortfolioStat(key=k, label=label, value=v, sort_order=i))

    for cat, items in LIBRARY.items():
        for j, (t, kind, s) in enumerate(items, 1):
            db.add(LibraryItem(category=cat, title=t, kind=kind, summary=s, sort_order=j))
    db.commit()

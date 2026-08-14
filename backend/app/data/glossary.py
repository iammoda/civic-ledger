"""Hand-written plain-language glossary for parliamentary jargon.

Written to grade-8 readability by hand — zero LLM cost, instantly
available, and reviewable in a diff like any other code.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.readability import reading_grade
from app.models import GlossaryTerm

TERMS: list[tuple[str, str]] = [
    ("bill", "A proposed law. It only becomes a real law after both the House and Senate pass it and it gets royal assent."),
    ("first reading", "A bill's introduction. No debate, no vote — the bill is simply presented and printed."),
    ("second reading", "The first big vote on a bill's main idea. Passing here sends it to a committee for detailed study."),
    ("committee stage", "A small group of MPs studies the bill line by line, hears witnesses, and can change it."),
    ("report stage", "The whole House reviews the committee's changes and can make more of them."),
    ("third reading", "The final House vote on a bill. Passing here sends it to the Senate (or to royal assent if it started there)."),
    ("royal assent", "The final step that makes a bill a law. The Governor General signs off — in practice, always."),
    ("prorogation", "The Prime Minister ends the parliamentary session early. Every unfinished bill dies on the spot."),
    ("dissolution", "Parliament is shut down for an election. All unfinished business dies."),
    ("order paper", "Parliament's to-do list. A bill 'dies on the Order Paper' when the session ends before it finishes."),
    ("whipped vote", "MPs are told how to vote by their party. Voting differently can get them punished."),
    ("free vote", "MPs may vote however they want, without party orders. Rare."),
    ("confidence vote", "A vote the government must win. Losing it usually triggers an election."),
    ("voice vote", "A vote decided by MPs shouting 'yea' or 'nay' — no record of who voted which way."),
    ("recorded division", "A vote where every MP's choice is written down. These are the votes you can hold MPs to."),
    ("hoist amendment", "A motion to delay a bill by six months. In practice, voting Yes on it kills the bill."),
    ("reasoned amendment", "A motion that replaces a bill's approval with a statement of why it shouldn't proceed. Voting Yes blocks the bill."),
    ("time allocation", "The government limits how long a bill can be debated. Speeds the bill up; critics call it silencing debate."),
    ("closure", "A motion to end debate right away and force a vote."),
    ("omnibus bill", "One bill that changes many unrelated laws at once. Hard to study and hard to vote on honestly."),
    ("private member's bill", "A bill from a regular MP, not the government. Most never become law."),
    ("government bill", "A bill from cabinet. These get priority and usually pass when the government has the votes."),
    ("riding", "The area an MP speaks for. Each riding elects one MP."),
    ("caucus", "All the MPs from one party, as a group."),
    ("crossing the floor", "An MP leaves their party to join another — without an election."),
    ("question period", "The daily 45 minutes when MPs question the government. More theatre than answers, but on the record."),
    ("hansard", "The official record of every word said in Parliament."),
    ("paired vote", "Two MPs from opposite sides both agree to skip a vote, cancelling each other out."),
    ("designated traveller", "One person (often a spouse) an MP can name to travel at public expense."),
    ("e-petition", "An official online petition. With enough signatures and an MP's sponsorship, the government must respond within 45 days."),
    ("motion", "A formal proposal MPs vote on. Motions state a position or manage House business — they don't change the law by themselves."),
    ("lobbying contact", "A meeting, call, or arranged communication between a paid lobbyist and an office holder like an MP. Lobbyists must report each one to the federal registry, with the subjects discussed. It's evidence of access, not wrongdoing."),
    ("lobbyist", "A person paid to push the government toward choices that help their client or employer. It is legal, but they must register and report what they do."),
    ("members' office budget", "The annual, taxpayer-funded budget every MP gets to run their office: staff, riding office, travel, mail. Set by the House's Board of Internal Economy."),
    ("board of internal economy", "The group of MPs from all parties that sets the House's own spending rules. It also sets each MP's office budget."),
    ("sessional allowance", "An MP's base salary, set by law. Extra pay comes with extra roles: ministers, the Speaker, party leaders, committee chairs, whips."),
]


def seed_glossary(db: Session) -> int:
    """Idempotently insert/update definitions; records reading grade."""
    count = 0
    for term, definition in TERMS:
        row = db.scalar(select(GlossaryTerm).where(GlossaryTerm.term == term))
        if row is None:
            row = GlossaryTerm(term=term, definition_en=definition)
            db.add(row)
            count += 1
        row.definition_en = definition
        row.reading_grade = reading_grade(definition)
    db.commit()
    return count

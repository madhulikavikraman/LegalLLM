"""
Rule-based detector for risky / tenant-unfriendly lease clauses.
Each rule is a regex/keyword pattern + severity + plain-English explanation.
This runs independently of the LLM so results are fast, deterministic, and auditable;
the LLM (see llm_engine.py) is used afterwards only to summarize/explain in plain language.
"""
import re
from nltk.tokenize import sent_tokenize

# severity: 3 = high risk, 2 = medium, 1 = low / worth reviewing
RISK_RULES = [
    dict(
        id="auto_renewal",
        label="Automatic Renewal / Evergreen Clause",
        severity=3,
        patterns=[r"automatically renew", r"auto-renew", r"evergreen", r"shall renew unless"],
        why="The lease renews itself unless you take action by a deadline, which can trap you into another term if you miss the notice window."
    ),
    dict(
        id="unilateral_rent_increase",
        label="Unilateral / Uncapped Rent Increase",
        severity=3,
        patterns=[r"landlord may increase (the )?rent", r"rent (may|shall) be increased at (the )?landlord'?s? (sole )?discretion", r"rent increase.{0,40}without limit"],
        why="The landlord can raise rent at will, with no cap and possibly no advance notice requirement."
    ),
    dict(
        id="non_refundable_deposit",
        label="Non-Refundable Deposit Language",
        severity=3,
        patterns=[r"non-refundable deposit", r"deposit is non-refundable", r"forfeit.{0,20}deposit"],
        why="Framing a security deposit as non-refundable may conflict with state landlord-tenant law in many jurisdictions and should be checked carefully."
    ),
    dict(
        id="acceleration_clause",
        label="Rent Acceleration on Default",
        severity=3,
        patterns=[r"entire (remaining )?(balance|rent).{0,30}due (immediately|upon default)", r"acceleration of rent", r"all remaining rent.{0,20}(shall become|becomes) due"],
        why="A single missed/late payment could make ALL remaining rent for the lease term immediately due in full."
    ),
    dict(
        id="joint_several_liability",
        label="Joint & Several Liability",
        severity=2,
        patterns=[r"joint and several liability", r"jointly and severally liable"],
        why="If you have roommates, you can each be held responsible for 100% of damages or unpaid rent, not just your share."
    ),
    dict(
        id="waiver_of_rights",
        label="Waiver of Legal Rights",
        severity=3,
        patterns=[r"waives?.{0,20}(right to|any right)", r"tenant waives", r"waiver of jury trial", r"waives? the right to a jury"],
        why="You may be giving up statutory rights (e.g. to a jury trial, to certain notices, or to withhold rent for repairs)."
    ),
    dict(
        id="indemnification",
        label="Broad Tenant Indemnification",
        severity=2,
        patterns=[r"tenant shall indemnify", r"tenant agrees to indemnify and hold harmless", r"hold landlord harmless"],
        why="You may be agreeing to cover the landlord's legal costs/liability even for issues that weren't your fault."
    ),
    dict(
        id="excessive_late_fee",
        label="Excessive / Uncapped Late Fees",
        severity=2,
        patterns=[r"late fee of \$?\d{2,4}", r"late charge.{0,20}per day", r"\d{1,2}%\s*(late fee|penalty)"],
        why="Some jurisdictions cap late fees (often 5% of rent or a flat reasonable amount) — check this against local law; daily-compounding fees can snowball quickly."
    ),
    dict(
        id="unrestricted_entry",
        label="Landlord Entry Without Notice",
        severity=3,
        patterns=[r"landlord may enter (the premises )?at any time", r"without (prior )?notice.{0,20}enter", r"enter.{0,20}without (prior )?notice"],
        why="Most states require 24-48 hours' notice before non-emergency entry; a clause allowing entry any time without notice may violate your right to quiet enjoyment."
    ),
    dict(
        id="no_repair_withholding",
        label="No Right to Withhold Rent for Repairs",
        severity=2,
        patterns=[r"tenant (may not|shall not) withhold rent", r"no right to withhold rent"],
        why="This attempts to block a legal remedy (rent withholding/repair-and-deduct) available to tenants in many states when landlords fail to make required repairs."
    ),
    dict(
        id="attorney_fees_one_sided",
        label="One-Sided Attorney's Fees Clause",
        severity=2,
        patterns=[r"tenant shall pay.{0,20}landlord'?s? attorney'?s? fees", r"tenant (is|shall be) responsible for all legal fees"],
        why="If only the tenant (not both parties) pays legal fees in a dispute, it discourages tenants from ever challenging the landlord, even when they're right."
    ),
    dict(
        id="mandatory_arbitration",
        label="Mandatory Arbitration Clause",
        severity=1,
        patterns=[r"binding arbitration", r"disputes.{0,20}shall be (resolved|settled) by arbitration"],
        why="You may be giving up the right to sue in court or join a class action; arbitration can favor repeat-player landlords."
    ),
    dict(
        id="as_is_condition",
        label="'As-Is' Property Condition",
        severity=1,
        patterns=[r"accepts? the premises .{0,10}as.?is", r"leased in .as is. condition"],
        why="The landlord may be disclaiming responsibility for existing defects — do a move-in inspection and document everything in photos."
    ),
    dict(
        id="excess_fees_pets_misc",
        label="Vague / Open-Ended Additional Fees",
        severity=1,
        patterns=[r"additional fees? (may|as) determined by (the )?landlord", r"other charges? as landlord deems (necessary|appropriate)"],
        why="Open-ended language lets the landlord invent new charges after you've signed, with no ceiling defined up front."
    ),
    dict(
        id="early_termination_penalty",
        label="Steep Early Termination Penalty",
        severity=2,
        patterns=[r"early termination fee", r"break(ing)? the lease.{0,30}(pay|forfeit)", r"liquidated damages"],
        why="Confirm the penalty amount is reasonable and proportionate — excessive liquidated-damages clauses can be unenforceable in some states."
    ),
]


NEGATION_WORDS = re.compile(
    r"\b(does not|do not|doesn't|don't|shall not|will not|won't|"
    r"is not required to|no right to|never)\s+waive", re.IGNORECASE
)


def _is_negated_waiver(sentence: str) -> bool:
    """Guards against matching 'Landlord does NOT waive the right to...' as a risky waiver."""
    return bool(NEGATION_WORDS.search(sentence))


def scan_risky_clauses(full_text: str):
    """
    Returns a list of findings: each with rule metadata + matched sentence(s).
    """
    sentences = sent_tokenize(full_text)
    findings = []
    for rule in RISK_RULES:
        matched_sentences = []
        combined = "|".join(rule["patterns"])
        for sent in sentences:
            if re.search(combined, sent, re.IGNORECASE):
                if rule["id"] == "waiver_of_rights" and _is_negated_waiver(sent):
                    continue
                matched_sentences.append(sent.strip())
        if matched_sentences:
            findings.append({
                **rule,
                "matches": matched_sentences[:3],
            })
    findings.sort(key=lambda f: -f["severity"])
    return findings


def risk_score(findings) -> int:
    """
    0-100 risk score with diminishing returns per additional finding, so a couple
    of flagged clauses don't automatically read as "near-maximum risk."
    Each finding contributes its severity weight, but later findings count less.
    """
    if not findings:
        return 5
    weights = {3: 18, 2: 10, 1: 5}  # base points per severity level
    findings_sorted = sorted(findings, key=lambda f: -f["severity"])
    score = 0.0
    for i, f in enumerate(findings_sorted):
        decay = 0.65 ** i  # each subsequent finding adds less (diminishing returns)
        score += weights[f["severity"]] * decay
    return min(95, round(score))


def severity_label(score: int) -> str:
    if score >= 70:
        return "High Risk"
    if score >= 35:
        return "Moderate Risk"
    return "Low Risk"

"""Transparent keyword-lexicon topic identification.

Every topic rule is human-readable and inspectable. Rules are ordered so that
more specific matches win. Negation is handled explicitly in both directions:
- fraud keywords preceded by a negation ("not a victim of fraud") do NOT match
  the fraud rule;
- negated-safety phrases ("no fraudulent activity") match the safety rule.

Matched keywords are returned as evidence attached to the analysis record.
"""
import re
from dataclasses import dataclass

NEGATION_WORDS = r"\b(no|not|never|without|wasn't|weren't|isn't|aren't|didn't|don't|doesn't|neither)\b"


@dataclass
class TopicRule:
    topic: str
    refined_category: str
    keywords: list[str]
    negated_phrase: bool = False  # the keyword itself contains its own negation
    require_any: list[str] | None = None  # subject terms that must also appear


# Order matters: first match wins.
TOPIC_RULES: list[TopicRule] = [
    TopicRule(
        "Fraud & Scam Reports",
        "Trust & Safety",
        ["scam", "scammed", "fraud", "fraudulent", "counterfeit", "not authentic",
         "stole", "took my money", "never sent", "never received", "additional payment",
         "charged multiple times", "not as advertised", "not related to my order"],
    ),
    TopicRule(
        "Transaction Safety (No Issues Reported)",
        "Trust & Safety",
        ["no fraudulent activity", "no signs of fraudulent", "not a victim of fraud",
         "no fraudulent", "not a victim"],
        negated_phrase=True,
    ),
    TopicRule(
        "Website & Checkout Experience",
        "Digital Experience",
        ["website", "checkout", "glitches", "crashing", "crashed",
         "website was unresponsive", "site was unresponsive", "technical issues",
         "placing my order", "online store"],
    ),
    TopicRule(
        "Delivery Delays",
        "Fulfilment",
        ["delivery was delayed", "delivery delayed", "delayed", "delay", "late",
         "took too long", "weeks", "shipment"],
    ),
    TopicRule(
        "Order & Packaging Problems",
        "Fulfilment",
        ["wrong items", "processed incorrectly", "packaging was damaged",
         "damaged upon arrival", "items were missing", "missing from my order"],
    ),
    TopicRule(
        "On-Time Delivery & Packaging",
        "Fulfilment",
        ["delivery was on time", "on time", "packaging was in excellent",
         "packaging was in good", "packaging was intact", "arrived in perfect condition",
         "perfect condition", "pristine condition", "excellent condition",
         "good condition"],
    ),
    TopicRule(
        "Product Defects & Quality Problems",
        "Product Quality",
        ["defects", "defective", "stopped working", "low-quality", "low quality",
         "did not function", "did not meet my expectations", "does not meet my expectations",
         "do not meet my expectations", "not meet my expectations",
         "did not function properly", "poor quality", "damaged"],
    ),
    TopicRule(
        "Customer Service Complaints",
        "Support",
        ["unresponsive", "not helpful", "unhelpful", "did not provide a satisfactory",
         "remains unresolved", "terrible experience", "not provide a satisfactory solution",
         "wait for a long time", "long time to get a response", "frustrating"],
        require_any=["customer service", "support team", "support staff", "the support",
                     "service team", "support agent"],
    ),
    TopicRule(
        "Customer Service Praise",
        "Support",
        ["helpful", "knowledgeable", "resolved my issue", "excellent assistance",
         "quick resolution", "friendly", "patient", "professional", "went above and beyond",
         "great assistance", "satisfactory solution", "guided me", "outstanding"],
        require_any=["customer service", "support team", "support staff", "the support",
                     "service team", "support agent"],
    ),
    TopicRule(
        "Refunds & Compensation",
        "Policy",
        ["refund", "compensation", "reimbursement", "money back"],
    ),
    TopicRule(
        "Product Quality Praise",
        "Product Quality",
        ["exceeded my expectations", "exceeds my expectations", "excellent quality",
         "high quality", "great value", "excellent value", "worth the price", "worth it",
         "impressed", "impressive", "satisfied", "highly recommend", "game-changer",
         "durable", "reliable", "performs well", "top-notch", "innovative", "useful",
         "love it", "outstanding", "exceptional"],
    ),
]

FALLBACK_TOPIC = "General Feedback"


@dataclass
class TopicResult:
    topic: str
    refined_category: str
    evidence: str
    matched_keywords: list[str]


def _negated_before(text_lower: str, idx: int) -> bool:
    window = text_lower[max(0, idx - 40): idx]
    return re.search(NEGATION_WORDS, window) is not None


def identify_topic(text: str, original_category: str | None = None) -> TopicResult:
    lowered = text.lower()
    for rule in TOPIC_RULES:
        if rule.require_any and not any(s in lowered for s in rule.require_any):
            continue
        matched = []
        for kw in rule.keywords:
            idx = lowered.find(kw)
            if idx == -1:
                continue
            if rule.negated_phrase:
                # keyword carries its own negation; plain substring match
                matched.append(kw)
            elif rule.topic.startswith("Fraud"):
                # skip fraud keywords inside negated contexts
                if _negated_before(lowered, idx):
                    continue
                matched.append(kw)
            else:
                matched.append(kw)
        if matched:
            evidence = "Matched keywords: " + ", ".join(sorted(set(matched))[:6])
            return TopicResult(
                topic=rule.topic,
                refined_category=rule.refined_category,
                evidence=evidence,
                matched_keywords=sorted(set(matched)),
            )
    if original_category:
        return TopicResult(
            topic=FALLBACK_TOPIC,
            refined_category=original_category,
            evidence="No topic keywords matched; original category retained for context.",
            matched_keywords=[],
        )
    return TopicResult(
        topic=FALLBACK_TOPIC,
        refined_category="Uncategorized",
        evidence="No topic keywords matched.",
        matched_keywords=[],
    )

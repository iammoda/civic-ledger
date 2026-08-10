"""Curated topic taxonomy (~26 topics) with colloquial aliases.

Aliases bridge how people talk ("carbon tax") to how Parliament writes
("fuel charge"). Used by search, topic tagging, and follows.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Topic

TOPICS: list[dict[str, str]] = [
    {"slug": "housing", "name_en": "Housing", "aliases_en": "rent, mortgage, home prices, affordable housing, homelessness, landlord, tenant"},
    {"slug": "healthcare", "name_en": "Health Care", "aliases_en": "doctor shortage, wait times, pharmacare, dental care, mental health, drug coverage"},
    {"slug": "cost-of-living", "name_en": "Cost of Living", "aliases_en": "inflation, grocery prices, affordability, gas prices, interest rates"},
    {"slug": "climate-environment", "name_en": "Climate & Environment", "aliases_en": "carbon tax, fuel charge, emissions, pipelines, wildfires, pollution, plastics"},
    {"slug": "taxes", "name_en": "Taxes", "aliases_en": "income tax, GST, HST, capital gains, tax credit, carbon rebate"},
    {"slug": "jobs-economy", "name_en": "Jobs & Economy", "aliases_en": "unemployment, wages, minimum wage, EI, employment insurance, strikes, unions"},
    {"slug": "immigration", "name_en": "Immigration", "aliases_en": "visa, permanent residence, refugees, asylum, study permit, temporary foreign workers"},
    {"slug": "indigenous", "name_en": "Indigenous Peoples", "aliases_en": "First Nations, Inuit, Métis, reconciliation, treaty rights, drinking water advisories"},
    {"slug": "defence-security", "name_en": "Defence & National Security", "aliases_en": "military, NATO, armed forces, NORAD, foreign interference, spying"},
    {"slug": "public-safety", "name_en": "Public Safety & Crime", "aliases_en": "gun control, firearms, bail, auto theft, policing, RCMP, border"},
    {"slug": "justice-rights", "name_en": "Justice & Rights", "aliases_en": "charter, human rights, courts, sentencing, free speech, discrimination"},
    {"slug": "seniors-pensions", "name_en": "Seniors & Pensions", "aliases_en": "CPP, OAS, GIS, retirement, old age security, long-term care"},
    {"slug": "families-children", "name_en": "Families & Children", "aliases_en": "child care, daycare, child benefit, CCB, parental leave"},
    {"slug": "education-skills", "name_en": "Education & Skills", "aliases_en": "student loans, apprenticeship, training, tuition, research funding"},
    {"slug": "transport-infrastructure", "name_en": "Transport & Infrastructure", "aliases_en": "transit, highways, rail, airports, bridges, EV chargers"},
    {"slug": "agriculture-food", "name_en": "Agriculture & Food", "aliases_en": "farmers, supply management, dairy, grain, food safety"},
    {"slug": "fisheries-oceans", "name_en": "Fisheries & Oceans", "aliases_en": "fishing, salmon, lobster, coast guard, marine protected areas"},
    {"slug": "energy-resources", "name_en": "Energy & Natural Resources", "aliases_en": "oil, gas, mining, critical minerals, electricity, nuclear, hydro"},
    {"slug": "telecom-internet", "name_en": "Telecom & Internet", "aliases_en": "cell phone bills, internet prices, CRTC, streaming, broadband, rural internet"},
    {"slug": "privacy-digital", "name_en": "Privacy & Digital Rights", "aliases_en": "data protection, surveillance, AI regulation, online harms, facial recognition"},
    {"slug": "trade-industry", "name_en": "Trade & Industry", "aliases_en": "tariffs, exports, USMCA, softwood lumber, manufacturing, subsidies"},
    {"slug": "small-business", "name_en": "Small Business", "aliases_en": "entrepreneurs, credit card fees, business loans, red tape"},
    {"slug": "veterans", "name_en": "Veterans", "aliases_en": "veterans affairs, disability benefits, service records"},
    {"slug": "arts-culture", "name_en": "Arts, Culture & Media", "aliases_en": "CBC, news, broadcasting, Canadian content, artists, heritage"},
    {"slug": "official-languages", "name_en": "Official Languages", "aliases_en": "French, bilingualism, francophone, Quebec"},
    {"slug": "democracy-ethics", "name_en": "Democracy & Ethics", "aliases_en": "elections, lobbying, conflicts of interest, transparency, electoral reform"},
    {"slug": "foreign-affairs", "name_en": "Foreign Affairs & Aid", "aliases_en": "diplomacy, sanctions, foreign aid, embassies, consular"},
    {"slug": "disability-accessibility", "name_en": "Disability & Accessibility", "aliases_en": "disability benefit, accessibility, inclusion"},
]


def seed_topics(db: Session) -> int:
    """Idempotently insert/update the curated taxonomy."""
    count = 0
    for entry in TOPICS:
        topic = db.scalar(select(Topic).where(Topic.slug == entry["slug"]))
        if topic is None:
            topic = Topic(slug=entry["slug"], name_en=entry["name_en"])
            db.add(topic)
            count += 1
        topic.name_en = entry["name_en"]
        topic.aliases_en = entry.get("aliases_en")
    db.commit()
    return count

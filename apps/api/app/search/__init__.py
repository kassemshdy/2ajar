"""Plain-text property search without an LLM.

Pipeline (each step is deterministic and unit-tested):

1. ``text``      — normalise Arabic / English / Arabizi (letters, digits, spacing).
2. ``parser``    — extract hard constraints (deal type, area, budget, rooms, furnishing, property type) and
                   soft preferences (quiet, safe, 24/7 electricity, low bills, solar, parking, ...).
3. ``engine``    — hard constraints become SQL filters; preferences are scored per listing from *stored*
                   facts only (publisher-reported living factors + staff-curated area profiles). Every reason
                   shown to the user points at a real field, so nothing can be invented.
"""

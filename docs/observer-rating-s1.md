# Observer Discovery Ratings — S1 Validation

Spot-check: Ying rates 20 randomly-selected Observer discoveries at end of
the 7-day validation window. S1 exit criterion §9.4 requires ≥30% marked
`y` (useful).

Fill the table row-by-row. `discovery_id` from
`sqlite3 agent.db "SELECT id,title,category,priority FROM agent_discoveries WHERE digital_human_id='observer' ORDER BY RANDOM() LIMIT 20;"`

| discovery_id | title | priority | useful (y/n) | note |
|--------------|-------|----------|--------------|------|
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |
|              |       |          |              |      |

**Rules for `useful=y`:**
- Signal I would have missed otherwise
- Actionable within 7 days
- Specific enough to act on (not vague)

**Rules for `useful=n`:**
- Noise / obvious / already known
- Duplicate of something I already read
- Too vague to act on

Target: ≥ 6 of 20 rows marked `y` (30%).

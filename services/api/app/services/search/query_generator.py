from app.models.niche import Niche


def generate_search_queries(niche: Niche) -> list[str]:
    roles = niche.target_roles or ["Professional"]
    keywords = niche.keywords or [niche.industry]
    country = niche.country

    queries: list[str] = []
    seen: set[str] = set()

    for role in roles:
        for keyword in keywords:
            query = f'site:linkedin.com/in "{role.strip()}" "{keyword.strip()}" "{country.strip()}"'
            if query not in seen:
                seen.add(query)
                queries.append(query)

    if not queries:
        queries.append(f'site:linkedin.com/in "{niche.industry}" "{country}"')

    return queries

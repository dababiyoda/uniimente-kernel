"""Discovery by intention ranks real, installed machinery and reports its truthful state."""
from greg.discover import discover, tokens


def ids(q, n=6, **kw):
    return [r["id"] for r in discover(q, limit=n, **kw)]


def test_commerce_words_find_the_commerce_systems():
    top = ids("sell a product to a customer, take payment and reconcile the revenue")
    assert {"#38", "#54", "#37"} <= set(top) and "#39" in top


def test_founder_words_find_the_mission_paths_they_name():
    assert ids("verify a downloaded file against its published checksum")[0] == "verify-download"
    assert "engineering-brief" in ids("brief me every morning on my repositories and failing pull requests", 3)
    assert ids("find the shortest route through my delivery network")[0] == "network-in-words"
    assert ids("plan production to maximize profit under machine limits")[0] == "plan-in-words"


def test_partial_systems_are_reported_as_partial_never_upgraded():
    top = discover("isolate untrusted generated code so it cannot escape", limit=3)
    assert top[0]["id"] == "#10" and top[0]["state"] == "PARTIAL" and top[0]["gap"]


def test_empty_and_stopword_queries_find_nothing_and_kinds_filter():
    assert discover("") == [] and discover("the and of what can you do") == []
    assert all(r["kind"] == "capability" for r in discover("publish a post", kinds=("capability",)))
    assert tokens("customers") == ["customer"]                         # no over-stemming to "custom"

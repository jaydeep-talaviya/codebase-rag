"""Routes that change state must not be reachable with a safe verb.

Indexing used to be `GET /repositories/{id}/files`, and asking was
`GET /repositories/search`. Both were wrong in a way that cost real money:
a crawl, a prefetch, a restored browser tab, or a bookmarked URL could
re-trigger a multi-minute index or a paid LLM call, and asking through a GET
also refreshed the repository's idle timer, so a link followed once silently
kept a repository alive.

This module asserts the shape of the route table directly rather than issuing
requests, so it needs no database and cannot be satisfied by a route that
exists but is unreachable. It is the guard against the wart coming back.
"""

import unittest

from app.api.repository_api import router


def _routes() -> dict[tuple[str, str], str]:
    """Map (path, method) -> handler name for every registered route."""
    table: dict[tuple[str, str], str] = {}
    for route in router.routes:
        for method in getattr(route, "methods", set()) or set():
            # HEAD is always registered alongside GET by Starlette; it is not a
            # verb a caller chooses, so it does not count as a GET alias.
            if method in {"HEAD", "OPTIONS"}:
                continue
            table[(route.path, method)] = route.name
    return table


class StateChangingRoutesAreNotGetTests(unittest.TestCase):
    def setUp(self):
        self.routes = _routes()

    def assert_not_get(self, path: str):
        self.assertNotIn(
            (path, "GET"),
            self.routes,
            f"{path} is reachable by GET. It writes rows, runs the embedder, or "
            f"calls a paid LLM, so it must be a POST.",
        )

    def test_indexing_is_not_a_get(self):
        self.assert_not_get("/repositories/{repository_id}/files")
        self.assert_not_get("/repositories/{repository_id}/index")

    def test_cloning_is_not_a_get(self):
        self.assert_not_get("/repositories/{repository_id}/ingest")

    def test_asking_is_not_a_get(self):
        self.assert_not_get("/repositories/search")
        self.assert_not_get("/repositories/{repository_id}/ask")

    def test_the_mutating_routes_are_post(self):
        for path in (
            "/repositories/{repository_id}/ingest",
            "/repositories/{repository_id}/index",
            "/repositories/{repository_id}/ask",
            "/repositories/search",
        ):
            self.assertIn(
                (path, "POST"),
                self.routes,
                f"{path} should be the POST route for this operation.",
            )


class ReadOnlyRoutesAreStillGetTests(unittest.TestCase):
    """The fix must not turn genuine reads into writes.

    A file preview only reads from the clone. Turning it into a POST would
    mean a citation could not be linked, prefetched, or cached, and it would
    be a lie about what the route does.
    """

    def setUp(self):
        self.routes = _routes()

    def test_history_list_is_a_get(self):
        self.assertIn(("/repositories/", "GET"), self.routes)

    def test_single_repository_is_a_get(self):
        self.assertIn(("/repositories/{repository_id}", "GET"), self.routes)

    def test_file_preview_is_a_get(self):
        self.assertIn(
            ("/repositories/{repository_id}/files/{file_path:path}", "GET"),
            self.routes,
        )

    def test_creating_a_repository_is_a_post(self):
        self.assertIn(("/repositories/", "POST"), self.routes)


class MistypedPathsCannotReachAMutationTests(unittest.TestCase):
    """A wrong path must fail, not fall through to something that writes.

    `GET /repositories/search` is caught by `GET /repositories/{id}` and
    rejected as a non-integer id (422). That is the right outcome even though
    405 would read more clearly: the point is that no mutating handler is
    reachable by it, and this pins that.
    """

    def setUp(self):
        self.routes = _routes()

    def test_search_is_a_post_only_path(self):
        self.assertIn(("/repositories/search", "POST"), self.routes)
        self.assertNotIn(("/repositories/search", "GET"), self.routes)

    def test_id_route_rejects_non_numeric_paths(self):
        """`/repositories/search` is not repository id "search"."""
        import inspect

        route = next(
            r
            for r in router.routes
            if getattr(r, "path", None) == "/repositories/{repository_id}"
        )
        signature = inspect.signature(route.endpoint)
        annotation = signature.parameters["repository_id"].annotation
        self.assertIs(annotation, int)


class AskRequestShapeTests(unittest.TestCase):
    def test_question_is_required(self):
        from app.representations.repository import AskRequest

        with self.assertRaises(Exception):
            AskRequest()

    def test_repository_id_is_optional(self):
        from app.representations.repository import AskRequest

        payload = AskRequest(question="where is config read")
        self.assertIsNone(payload.repository_id)

"""Pure tests for explicit Next.js route-shape qualification requirements."""
import unittest

from project_next_qualification import route_shape_counts


class RouteShapeCounts(unittest.TestCase):
    def test_counts_groups_dynamic_pages_and_optional_catchall(self):
        entities = [
            {"kind": "topology:page", "attributes": {
                "repositoryPath": "app/(workspace)/[org]/page.tsx", "dynamic": True}},
            {"kind": "topology:page", "attributes": {
                "repositoryPath": "app/(workspace)/page.tsx", "dynamic": False}},
            {"kind": "topology:page", "attributes": {
                "repositoryPath": "app/page.tsx", "dynamic": False}},
            {"kind": "topology:segment", "attributes": {"segmentKind": "group"}},
            {"kind": "topology:segment", "attributes": {"segmentKind": "dynamic"}},
            {"kind": "topology:segment", "attributes": {"segmentKind": "optional-catch-all"}},
            {"kind": "topology:segment", "attributes": {"segmentKind": "static"}},
        ]
        self.assertEqual(route_shape_counts(entities), {
            "pageCount": 3,
            "pageSourcesUnderRouteGroups": 2,
            "dynamicPageCount": 1,
            "routeGroupSegments": 1,
            "dynamicSegments": 1,
            "optionalCatchAllSegments": 1,
            "segmentCount": 4,
        })

    def test_unrelated_entities_do_not_satisfy_required_route_shapes(self):
        entities = [
            {"kind": "topology:page", "attributes": {
                "repositoryPath": "app/[literal]/page.tsx", "dynamic": False}},
            {"kind": "topology:segment", "attributes": {"segmentKind": "static", "segment": "[literal]"}},
            {"kind": "routing:schema", "attributes": {"routePath": "(literal)/[id]"}},
        ]
        counts = route_shape_counts(entities)
        self.assertEqual(counts["routeGroupSegments"], 0)
        self.assertEqual(counts["dynamicSegments"], 0)
        self.assertEqual(counts["optionalCatchAllSegments"], 0)
        self.assertEqual(counts["dynamicPageCount"], 0)


if __name__ == "__main__":
    unittest.main()

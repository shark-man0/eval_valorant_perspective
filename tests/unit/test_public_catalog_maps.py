import json

from valorant_ai_coach.maps.public_catalog import load_public_map_references


def test_public_catalog_map_reference_is_explicit_and_versioned(tmp_path):
    asset = tmp_path / "Maps" / "map-id.png"
    asset.parent.mkdir()
    asset.write_bytes(b"fixture")
    catalog = tmp_path / "PublicContentCatalog.json"
    catalog.write_text(
        json.dumps(
            {
                "version": "fixture-1",
                "maps": [
                    {
                        "id": "map-id",
                        "name": {"defaultText": "Example"},
                        "xScalarToAdd": 0.5,
                        "xMultiplier": 0.01,
                        "yScalarToAdd": 0.6,
                        "yMultiplier": -0.01,
                    },
                    {
                        "id": "missing",
                        "name": {"defaultText": "Unavailable"},
                        "xScalarToAdd": 0,
                        "xMultiplier": 0,
                        "yScalarToAdd": 0,
                        "yMultiplier": 0,
                    },
                ],
            }
        )
    )
    references = load_public_map_references(catalog, tmp_path)
    assert list(references) == ["Example"]
    assert references["Example"].catalog_version == "fixture-1"
    assert references["Example"].world_to_minimap_normalized(10, 20) == (0.6, 0.39999999999999997)

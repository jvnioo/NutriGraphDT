import nutrigraphdt


def test_package_exposes_development_version() -> None:
    assert nutrigraphdt.__version__ == "0.1.0.dev0"

import numpy as np

from ltverify.config import NetworkConfig, ProfileConfig
from ltverify.network import build_network
from ltverify.profiles import generate_profiles


def test_profiles_are_deterministic_and_have_physical_shapes() -> None:
    artifacts = build_network(NetworkConfig())
    cfg = ProfileConfig(days=2, interval_minutes=15)
    first = generate_profiles(artifacts, cfg, seed=42)
    second = generate_profiles(artifacts, cfg, seed=42)
    assert first.load_p_mw.shape == (192, 24)
    assert first.load_p_mw.equals(second.load_p_mw)
    assert (first.load_p_mw >= 0).all().all()
    assert (first.load_q_mvar >= 0).all().all()
    assert (first.pv_p_mw >= 0).all().all()
    night = first.index.hour.isin([0, 1, 2, 3, 4])
    assert np.allclose(first.pv_p_mw.loc[night].to_numpy(), 0.0)


def test_seed_change_produces_different_profiles() -> None:
    artifacts = build_network(NetworkConfig())
    cfg = ProfileConfig(days=2, interval_minutes=15)
    first = generate_profiles(artifacts, cfg, seed=42)
    second = generate_profiles(artifacts, cfg, seed=43)
    assert not first.load_p_mw.equals(second.load_p_mw)
    assert first.index.equals(second.index)
    assert first.load_p_mw.columns.equals(second.load_p_mw.columns)

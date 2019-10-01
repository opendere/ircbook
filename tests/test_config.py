from config import Configuration


def test_active_channels():
    config = Configuration({'active_channels': []})
    assert not config.has_active_channel("#foo")
    config.add_active_channel("#foo")
    assert config.has_active_channel("#foo")
    config.remove_active_channel("#foo")
    assert not config.has_active_channel("#foo")


def test_channels():
    config = Configuration({'channels': []})
    assert not config.has_channel("#foo")
    assert config.get_channels() == []
    config.add_channel("#foo")
    config.add_channel('#bar')
    assert config.get_channels() == ["#foo", '#bar']
    assert config.has_channel("#foo")

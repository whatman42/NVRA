from pathlib import Path

from god.gui.notifications import NotificationSound


def test_notification_sound_defaults_enabled(tmp_path: Path):
    sound = NotificationSound(tmp_path)
    assert sound.muted is False


def test_notification_sound_mute_roundtrip(tmp_path: Path):
    sound = NotificationSound(tmp_path)
    sound.set_muted(True)
    assert sound.muted is True
    assert sound.play() is False
    sound.set_muted(False)
    assert sound.muted is False

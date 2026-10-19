from app.core.process import CREATE_NO_WINDOW, DETACHED_PROCESS, creation_flags


def test_creation_flags_are_cross_platform_and_typed() -> None:
    assert isinstance(CREATE_NO_WINDOW, int)
    assert isinstance(DETACHED_PROCESS, int)
    assert creation_flags(platform="posix") == 0
    assert creation_flags(platform="nt") == CREATE_NO_WINDOW
    assert creation_flags(detached=True, platform="nt") == (CREATE_NO_WINDOW | DETACHED_PROCESS)

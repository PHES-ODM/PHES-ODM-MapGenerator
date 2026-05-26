import logging

from odm_map_maker.utils.logger import MultiFormatter, get_logger, make_logger_bullet_list


# ---------------------------------------------------------------------------
# MultiFormatter
# ---------------------------------------------------------------------------

def test_multi_formatter_default_format():
    fmt = MultiFormatter(fmt="%(levelname)s: %(message)s")
    record = logging.LogRecord(
        name="test", level=logging.WARNING, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None
    )
    result = fmt.format(record)
    assert "WARNING" in result
    assert "hello" in result

def test_multi_formatter_alternate_format_for_level():
    fmt = MultiFormatter(
        fmt="%(levelname)s: %(message)s",
        alternate_fmts={logging.INFO: "INFO_ONLY: %(message)s"},
    )
    info_record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="info message", args=(), exc_info=None
    )
    result = fmt.format(info_record)
    assert result.startswith("INFO_ONLY:")
    assert "info message" in result

def test_multi_formatter_default_used_for_unlisted_level():
    fmt = MultiFormatter(
        fmt="DEFAULT: %(message)s",
        alternate_fmts={logging.DEBUG: "DEBUG: %(message)s"},
    )
    warning_record = logging.LogRecord(
        name="test", level=logging.WARNING, pathname="", lineno=0,
        msg="warn msg", args=(), exc_info=None
    )
    result = fmt.format(warning_record)
    assert result.startswith("DEFAULT:")

def test_multi_formatter_no_alternate_fmts():
    fmt = MultiFormatter(fmt="%(levelname)s %(message)s", alternate_fmts=None)
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="", lineno=0,
        msg="err", args=(), exc_info=None
    )
    result = fmt.format(record)
    assert "ERROR" in result


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------

def test_get_logger_returns_logger():
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)

def test_get_logger_name():
    logger = get_logger("my.test.logger")
    assert logger.name == "my.test.logger"

def test_get_logger_level():
    logger = get_logger("level_test", level=logging.WARNING)
    assert logger.level == logging.WARNING

def test_get_logger_idempotent():
    logger1 = get_logger("idempotent_logger")
    logger2 = get_logger("idempotent_logger")
    assert logger1 is logger2


# ---------------------------------------------------------------------------
# make_logger_bullet_list
# ---------------------------------------------------------------------------

def test_make_logger_bullet_list_basic():
    result = make_logger_bullet_list(["alpha", "beta", "gamma"])
    assert "alpha" in result
    assert "beta" in result
    assert "gamma" in result

def test_make_logger_bullet_list_uses_bullet():
    result = make_logger_bullet_list(["item1", "item2"], bullet="* ")
    assert "* item1" in result
    assert "* item2" in result

def test_make_logger_bullet_list_indexed_bullet():
    result = make_logger_bullet_list(["a", "b"], bullet="{idx}. ")
    assert "1. a" in result
    assert "2. b" in result

def test_make_logger_bullet_list_indent():
    result = make_logger_bullet_list(["x"], indent=2)
    assert result.startswith("  ")

def test_make_logger_bullet_list_no_trailing_newline_on_last_item():
    result = make_logger_bullet_list(["only"], end="\n", last_end="")
    assert not result.endswith("\n")

def test_make_logger_bullet_list_empty():
    result = make_logger_bullet_list([])
    assert result == ""

def test_make_logger_bullet_list_single_item():
    result = make_logger_bullet_list(["solo"], end="\n", last_end="END")
    assert result.endswith("END")

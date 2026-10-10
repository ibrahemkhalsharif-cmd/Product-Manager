import pytest

from app.config import ConfigError, Settings, validate_secret_key

GOOD = {"SECRET_KEY": "k" * 32}


def test_defaults():
    s = Settings.from_env(GOOD)
    assert (s.db_host, s.db_port, s.db_user, s.db_name) == ("127.0.0.1", 3306, "root", "shop_db")
    assert s.debug is False
    assert s.cookie_secure is False
    assert s.db_ssl_disabled is True


def test_reads_values_from_environment():
    s = Settings.from_env(
        {
            **GOOD,
            "DB_PORT": "3307",
            "DB_PASSWORD": "pw",
            "DB_NAME": "other",
            "APP_PORT": "8000",
            "APP_DEBUG": "true",
            "SESSION_COOKIE_SECURE": "1",
        }
    )
    assert (s.db_port, s.db_password, s.db_name, s.port) == (3307, "pw", "other", 8000)
    assert s.debug is True and s.cookie_secure is True


@pytest.mark.parametrize("secret", ["", "   ", "short", "change-this-to-a-long-random-text"])
def test_weak_secret_key_is_rejected(secret):
    with pytest.raises(ConfigError):
        Settings.from_env({"SECRET_KEY": secret})


def test_missing_secret_key_is_rejected():
    with pytest.raises(ConfigError):
        Settings.from_env({})


def test_secret_error_message_does_not_echo_the_value():
    with pytest.raises(ConfigError) as info:
        validate_secret_key("change-this-SECRETXYZ")
    assert "SECRETXYZ" not in str(info.value)


@pytest.mark.parametrize("port", ["abc", "0", "70000", "-1"])
def test_invalid_db_port_is_rejected(port):
    with pytest.raises(ConfigError):
        Settings.from_env({**GOOD, "DB_PORT": port})


def test_invalid_boolean_is_rejected():
    with pytest.raises(ConfigError):
        Settings.from_env({**GOOD, "APP_DEBUG": "maybe"})


def test_tls_default_depends_on_host():
    assert Settings.from_env({**GOOD, "DB_HOST": "localhost"}).db_ssl_disabled is True
    assert Settings.from_env({**GOOD, "DB_HOST": "db.example.com"}).db_ssl_disabled is False
    assert Settings.from_env({**GOOD, "DB_HOST": "db.example.com", "DB_SSL_DISABLED": "true"}).db_ssl_disabled is True
    assert Settings.from_env({**GOOD, "DB_SSL_DISABLED": "false"}).db_ssl_disabled is False


def test_repr_hides_secrets():
    s = Settings.from_env({"SECRET_KEY": "k" * 32, "DB_PASSWORD": "hunter2pw"})
    text = repr(s)
    assert "hunter2pw" not in text
    assert "kkkkkkkk" not in text
